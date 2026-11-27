"""Private CSIC-format corpus audit, not supervised training or release approval.

Parses bounded inert HTTP records without fetching their targets. Projects only
SDK-visible path/query/UA; ignores cookies and bodies. Never invents timestamps,
sessions or malicious labels from source-defined anomalies. Emits aggregates and
source offsets rather than raw requests. No model artifact is written.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.rules import evaluate
from app.rule_manifest import RULESET_RELEASE, RULES_SHA256
from detexis_shield.features import extract_features, MAX_PATH_STORED
from detexis_shield.redact import redact_query, MAX_QUERY_INPUT

REQUEST = re.compile(rb"([A-Z]{1,10}) ([^\s]+) HTTP/1\.[01]\r?\n?$")
FEATURES = ["payload_len", "special_char_ratio", "num_params", "path_depth"]


class CorpusError(ValueError):
    def __init__(self, offset, reason):
        super().__init__(f"Source byte offset {offset}: {reason}")
        self.offset = offset


def bounded_line(stream):
    offset = stream.tell()
    line = stream.readline(65537)
    if len(line) > 65536:
        raise CorpusError(offset, "line exceeds 64 KiB")
    return line


def requests(stream):
    while True:
        offset = stream.tell()
        line = bounded_line(stream)
        if not line:
            return
        if line in (b"\n", b"\r\n"):
            continue
        match = REQUEST.fullmatch(line)
        if not match:
            raise CorpusError(offset, "malformed request line; no heuristic resynchronization")
        headers, total = {}, 0
        while True:
            line = bounded_line(stream)
            if not line:
                raise CorpusError(offset, "truncated headers")
            total += len(line)
            if total > 65536:
                raise CorpusError(offset, "headers exceed 64 KiB")
            if line in (b"\n", b"\r\n"):
                break
            key, separator, value = line.rstrip(b"\r\n").partition(b":")
            if not separator:
                raise CorpusError(offset, "malformed header")
            key, value = key.lower(), value.strip()
            if key in headers:
                raise CorpusError(offset, "duplicate header not supported")
            headers[key] = value
        if b"transfer-encoding" in headers:
            raise CorpusError(offset, "transfer coding not supported in this corpus parser")
        length = headers.get(b"content-length", b"0")
        if not length.isdigit() or len(length) > 7 or int(length) > 1024 * 1024:
            raise CorpusError(offset, "invalid or oversized content length")
        length = int(length)
        if len(stream.read(length)) != length:
            raise CorpusError(offset, "truncated body")
        yield {"offset": offset, "method": match[1].decode("ascii"),
               "target": match[2].decode("latin-1"),
               "ua": headers.get(b"user-agent", b"").decode("latin-1")[:512],
               "body_bytes": length, "cookie_present": b"cookie" in headers}


def project(record):
    target = urlsplit(record["target"])
    if target.fragment or target.scheme not in ("", "http", "https"):
        raise ValueError("unsupported request target")
    if not target.netloc and not record["target"].startswith("/"):
        raise ValueError("unsupported request target")
    # ASGI/Werkzeug expose a decoded path and an undecoded query byte string.
    path = unquote(target.path or "/", encoding="utf-8", errors="replace")[:MAX_PATH_STORED]
    query = redact_query(target.query[:MAX_QUERY_INPUT])
    return {"path": path, "query_redacted": query, "ua": record["ua"],
            "features": extract_features(path, query)}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(paths):
    report = {"release_evidence": False, "model_trained": False, "complete": True,
              "rules_release": RULESET_RELEASE, "rules_source_sha256": RULES_SHA256,
              "scope": "Stateless SDK-visible corpus audit; source normal/anomalous labels, not customer FPR or malicious recall. No body/cookie analysis, stateful rules, timestamps or sessions.",
              "files": []}
    representations = {"normal": Counter(), "anomalous": Counter()}
    features = {"normal": Counter(), "anomalous": Counter()}
    for role, path in paths:
        item = {"file": path.name, "source_class": role, "bytes": path.stat().st_size,
                "sha256": file_hash(path), "parsed": 0, "projected": 0,
                "with_body": 0, "empty_query_with_body": 0, "cookie_header_records": 0,
                "methods": Counter(), "rule_matches": Counter(), "matching_requests": 0,
                "projection_exclusions": 0, "match_offsets": []}
        report["files"].append(item)
        try:
            with path.open("rb") as stream:
                for record in requests(stream):
                    item["parsed"] += 1
                    item["methods"][record["method"]] += 1
                    item["with_body"] += int(record["body_bytes"] > 0)
                    item["cookie_header_records"] += int(record["cookie_present"])
                    try:
                        observed = project(record)
                    except ValueError:
                        item["projection_exclusions"] += 1
                        continue
                    item["projected"] += 1
                    item["empty_query_with_body"] += int(bool(record["body_bytes"]) and not observed["query_redacted"])
                    representation = json.dumps([observed["path"], observed["query_redacted"]], ensure_ascii=True)
                    representations[role][hashlib.sha256(representation.encode()).hexdigest()] += 1
                    vector = json.dumps([observed["features"][name] for name in FEATURES])
                    features[role][vector] += 1
                    # Unknown response status is explicit. No synthetic failures,
                    # per-IP windows or site-specific honeytokens are asserted.
                    hits = evaluate(observed["path"], observed["query_redacted"], observed["ua"], status=None)
                    item["rule_matches"].update(hit.rule_id for hit in hits)
                    item["matching_requests"] += int(bool(hits))
                    if hits and len(item["match_offsets"]) < 20:
                        item["match_offsets"].append({"byte_offset": record["offset"], "rules": [hit.rule_id for hit in hits]})
        except CorpusError as error:
            report["complete"] = False
            item["parse_failure"] = {"offset": error.offset, "reason": str(error)}
        item["source_class_match_rate"] = item["matching_requests"] / item["projected"] if item["projected"] else None
    shared_representations = representations["normal"].keys() & representations["anomalous"].keys()
    shared_vectors = features["normal"].keys() & features["anomalous"].keys()
    report["overlap"] = {"sdk_path_query_shared_representations": len(shared_representations),
                         "shared_feature_vectors": len(shared_vectors),
                         "normal_rows_in_shared_vectors": sum(features["normal"][v] for v in shared_vectors),
                         "anomalous_rows_in_shared_vectors": sum(features["anomalous"][v] for v in shared_vectors)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal", type=Path, action="append", required=True)
    parser.add_argument("--anomalous", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing report")
    report = audit([*(('normal', p) for p in args.normal), *(('anomalous', p) for p in args.anomalous)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"complete": report["complete"], "release_evidence": False, "report": str(args.output)}))
    if not report["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

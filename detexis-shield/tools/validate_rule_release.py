"""Verify a packaged rule release before deployment; never fetch rule code."""
import argparse
import ast
from datetime import date
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.rule_manifest import manifest, release_record  # noqa: E402

SOURCE_PATH = "detexis-shield/backend/app/rules.py"


def previous_version(source):
    # Read a literal constant without importing/executing an older revision.
    for item in ast.parse(source).body:
        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RULESET_VERSION" for t in item.targets):
            value = ast.literal_eval(item.value)
            if type(value) is not int or value < 1:
                raise ValueError("Previous version must be a positive integer")
            return value
    return 1  # The original pre-manifest detector shipped as rules_version=1.


def verify(current, record, *, old_source=None, old_record=None):
    if not current["release_record_verified"]:
        raise ValueError("Release record does not match installed rule source")
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d+", current["release_id"]):
        raise ValueError("Release ID must use YYYY.MM.DD.sequence")
    stamp = date.fromisoformat(current["bundled_on"])
    if not current["release_id"].startswith(stamp.strftime("%Y.%m.%d.")):
        raise ValueError("Release ID and bundled date disagree")
    if not record.get("changes") or not record.get("references"):
        raise ValueError("A release needs change notes and source references")
    if old_record is not None and old_record != record:
        raise ValueError("Published release records are immutable; create a new release")
    if old_source is not None:
        import hashlib
        old_hash = hashlib.sha256(old_source.replace("\r\n", "\n").encode()).hexdigest()
        if old_hash != current["rules_source_sha256"] and current["rules_version"] <= previous_version(old_source):
            raise ValueError("Changed rule source requires a higher rules_version")


def git_file(ref, path):
    result = subprocess.run(["git", "show", ref + ":" + path], cwd=ROOT, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-ref")
    args = parser.parse_args()
    current, record = manifest(), release_record()
    old_source = old_record = None
    if args.previous_ref:
        # Only commit IDs, no arbitrary git options, paths or revision programs.
        if not re.fullmatch(r"[0-9a-fA-F]{40}", args.previous_ref):
            parser.error("previous-ref must be a full commit SHA")
        checked = subprocess.run(["git", "cat-file", "-e", args.previous_ref + "^{commit}"], cwd=ROOT, capture_output=True)
        if checked.returncode:
            parser.error("Previous commit is unavailable; fetch it before checking")
        old_source = git_file(args.previous_ref, SOURCE_PATH)
        old = git_file(args.previous_ref, "detexis-shield/backend/app/rule_releases/" + current["release_id"] + ".json")
        old_record = json.loads(old) if old is not None else None
    verify(current, record, old_source=old_source, old_record=old_record)
    print(json.dumps({"release_id":current["release_id"],"rules_version":current["rules_version"],
                      "rules_source_sha256":current["rules_source_sha256"],"metadata_passed":True,
                      "previous_ref_checked":args.previous_ref,
                      "scope":"Metadata/version integrity only; the rule, pipeline and false-positive regression tests must also pass. No real-traffic quality is established."}))


if __name__ == "__main__":
    main()

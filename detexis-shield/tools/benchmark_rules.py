"""Synthetic in-process detector cost, not host-site overhead or throughput SLA."""
import argparse
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter_ns
from urllib.parse import urlencode
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.rules import evaluate  # noqa: E402
from app.rule_manifest import manifest  # noqa: E402

PROFILES = {
    "ordinary_search": ("/search", "q=holiday+plans&page=2", "Mozilla/5.0"),
    "canary_path": ("/.env", "", "browser"),
    "comment_separated_sql": ("/search", urlencode({"q":"UNION/**/ALL/*!50000SELECT*/ name"}), "browser"),
    "maximum_query_fields": ("/search", "&".join("p"+str(n)+"="+"x"*30 for n in range(50)), "browser"),
    "bounded_unterminated_comments": ("/"+"/*"*1023, "q="+"/*"*10000, "x"*512),
    "bounded_separator_flood": ("/search", "&"*10000, "x"*512),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--output", type=Path, default=Path("rule-cpu-benchmark.json"))
    args = parser.parse_args()
    if not 200 <= args.samples <= 10000:
        parser.error("samples must be between 200 and 10000")
    profiles = {}
    for name, fields in PROFILES.items():
        for _ in range(100):
            [finding.json() for finding in evaluate(*fields, honeytokens=["/.env"])]
        timings = []
        for _ in range(args.samples):
            started = perf_counter_ns()
            [finding.json() for finding in evaluate(*fields, honeytokens=["/.env"])]
            timings.append((perf_counter_ns()-started)/1000000)
        timings.sort()
        profiles[name] = {"samples":len(timings), "median_ms":median(timings),
                          "p95_ms":timings[int((len(timings)-1)*.95)], "max_ms":max(timings)}
    value = manifest()
    report = {"checked_at":datetime.now(timezone.utc).isoformat(),"release_id":value["release_id"],
              "rules_source_sha256":value["rules_source_sha256"],"profiles":profiles,
              "scope":"Repeated synthetic in-process evaluation and finding serialization on this computer. Excludes SDK, HTTP, DB, queue, worker concurrency, malware engine and ML. No real-traffic FPR/recall or end-to-end throughput claim."}
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

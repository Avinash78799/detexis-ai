"""Controlled software smoke test, never a real-data performance benchmark."""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "backend")
sys.path.insert(0, "ml")
from train import train
from app.ml_runtime import classify
from detexis_shield.features import extract_features


def main():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(2000):
        malicious = int(index % 5 == 0)
        rows.append({"path": "/../../private/secret" if malicious else "/home",
                     "query_redacted": "q=%3Cscript%3E" if malicious else "q=hello",
                     "ts": (start + timedelta(minutes=index)).isoformat(),
                     "session_id": str(index), "dataset": "primary-fixture", "label": malicious})
    rows.extend([{**row, "dataset": "cross-fixture"} for row in rows[:500]])
    report = {"evidence_type": "controlled software fixture; not real-data FPR"}
    with tempfile.TemporaryDirectory() as folder:
        for kind in ("logistic", "xgboost"):
            target = Path(folder) / kind
            metadata = train(rows, target, "cross-fixture", target_fpr=.05, model_kind=kind)
            assert metadata["evaluation_status"] == "validated", metadata
            os.environ["SHIELD_MODEL_DIR"] = str(target)
            benign = classify(extract_features("/home", "q=hello"))
            attack = classify(extract_features("/../../private/secret", "q=%3Cscript%3E"))
            assert benign is not None and benign["alert"] is False
            assert attack is not None and attack["alert"] is True
            report[kind + "_artifact_runtime"] = "passed"
            if kind == "xgboost":
                assert len(attack["reasons"]) == 3, attack
                report["shap_reasons"] = "passed"
    Path("ml-smoke-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

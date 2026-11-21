"""Train/evaluate trusted canonical JSONL records; never invent dataset metrics."""
import argparse
import hashlib
import json
import math
import sys
import uuid
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

from detexis_shield.features import FEATURE_SCHEMA_VERSION, extract_features

NAMES = ["payload_len", "special_char_ratio", "num_params", "path_depth"]


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def prepare(rows, held_out_dataset):
    if not rows or not held_out_dataset:
        raise ValueError("request records and a separate cross-dataset holdout are required")
    for row in rows:
        if type(row["label"]) is not int or row["label"] not in (0, 1) or not row["session_id"] or not row["dataset"]:
            raise ValueError("label, session_id and dataset provenance are required")
        row["_time"] = timestamp(row["ts"])
        features = extract_features(row["path"], row["query_redacted"])
        row["_x"] = [features[name] for name in NAMES]
    main = sorted([r for r in rows if r["dataset"] != held_out_dataset], key=lambda r: r["_time"])
    cross = [r for r in rows if r["dataset"] == held_out_dataset]
    if len(main) < 20 or not cross:
        raise ValueError("not enough primary and cross-dataset records")
    cut1, cut2 = main[int(len(main) * .6)]["_time"], main[int(len(main) * .8)]["_time"]
    groups = {}
    for row in main:
        key = (row["dataset"], row["session_id"])
        groups.setdefault(key, []).append(row)
    partitions = [[], [], []]
    purged = 0
    for group in groups.values():
        positions = {0 if r["_time"] < cut1 else 1 if r["_time"] < cut2 else 2 for r in group}
        if len(positions) != 1:
            purged += len(group)  # Sessions crossing time boundaries are excluded.
        else:
            partitions[positions.pop()].extend(group)
    if any(not partition for partition in partitions):
        raise ValueError("temporal partitions empty after session purge")
    # Exact duplicate request representations cannot straddle evaluation boundaries.
    fingerprints = []
    for partition in [*partitions, cross]:
        fingerprints.append({hashlib.sha256(json.dumps([r["path"], r["query_redacted"]], ensure_ascii=True).encode()).hexdigest() for r in partition})
    # Real sites legitimately repeat URLs. Report overlap; do not silently delete benign traffic.
    overlap = {f"{a}-{b}": len(fingerprints[a] & fingerprints[b]) for a in range(4) for b in range(a + 1, 4)}
    return *partitions, cross, {"purged_session_rows": purged, "duplicate_request_overlap": overlap,
                              "temporal_cutoffs": [cut1.isoformat(), cut2.isoformat()]}


def upper_fpr(fp, negatives):
    if negatives == 0:
        return 1.0
    # Wilson 95% upper confidence bound, reported beside the empirical FPR.
    z = 1.959963984540054
    p = fp / negatives
    return (p + z*z/(2*negatives) + z*math.sqrt(p*(1-p)/negatives + z*z/(4*negatives*negatives))) / (1 + z*z/negatives)


def checked_scores(labels, probabilities):
    labels, probabilities = list(labels), list(probabilities)
    if not labels or len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must be nonempty and have equal lengths")
    if any(type(label) is not int or label not in (0, 1) for label in labels):
        raise ValueError("evaluation labels must be integer 0 or 1")
    probabilities = [float(value) for value in probabilities]
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError("probabilities must be finite and between zero and one")
    return labels, probabilities


def metrics(labels, probabilities, threshold):
    labels, probabilities = checked_scores(labels, probabilities)
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("invalid operating threshold")
    tp = fp = tn = fn = 0
    for label, probability in zip(labels, probabilities):
        alert = probability > threshold
        tp += int(label == 1 and alert)
        fp += int(label == 0 and alert)
        tn += int(label == 0 and not alert)
        fn += int(label == 1 and not alert)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "fpr": fp/(fp+tn) if fp+tn else None,
            "fpr_upper_95": upper_fpr(fp, fp+tn), "recall": tp/(tp+fn) if tp+fn else None,
            "alerts_per_1000_requests": 1000*(tp+fp)/len(labels) if labels else None}


def choose_threshold(labels, probabilities, target):
    if not 0 < target < 1:
        raise ValueError("invalid target FPR")
    labels, probabilities = checked_scores(labels, probabilities)
    benign = sorted(probability for label, probability in zip(labels, probabilities) if label == 0)
    candidates = sorted({0.0, 1.0, *(float(p) for p in probabilities)})
    for value in candidates:
        # Strict `score > threshold` means ties at the threshold do not alert.
        # Binary search counts the benign scores above it without rescanning all
        # records for every candidate: O(n log n), instead of quadratic work.
        false_positives = len(benign) - bisect_right(benign, value)
        if upper_fpr(false_positives, len(benign)) <= target:
            return value
    raise ValueError("insufficient benign calibration evidence for target FPR")


def train(rows, output, cross_dataset, target_fpr=.01, model_kind="logistic", min_recall=.1):
    if not 0 < target_fpr < 1 or not 0 <= min_recall <= 1:
        raise ValueError("invalid evaluation thresholds")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("use a new, empty artifact directory for each model version")
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    fit, calibration, test, cross, audit = prepare(rows, cross_dataset)
    if {r["label"] for r in fit} != {0, 1}:
        raise ValueError("training must contain both classes")
    if model_kind == "xgboost":
        from xgboost import XGBClassifier
        model = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=.05, random_state=42, n_jobs=1)
    elif model_kind == "logistic":
        model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000))
    else:
        raise ValueError("unsupported model")
    model.fit([r["_x"] for r in fit], [r["label"] for r in fit])
    calibration_prob = model.predict_proba([r["_x"] for r in calibration])[:, 1]
    threshold = choose_threshold([r["label"] for r in calibration], calibration_prob, target_fpr)
    evaluations = {}
    for name, partition in [("calibration", calibration), ("temporal_test", test), ("cross_dataset", cross)]:
        evaluations[name] = metrics([r["label"] for r in partition], model.predict_proba([r["_x"] for r in partition])[:, 1], threshold)
    validated = all(m["fpr_upper_95"] <= target_fpr and m["recall"] is not None and m["recall"] >= min_recall for m in evaluations.values())
    metadata = {"schema_version": FEATURE_SCHEMA_VERSION, "feature_names": NAMES,
                "threshold": threshold, "target_fpr": target_fpr, "min_recall": min_recall,
                "model_version": str(uuid.uuid4()), "model_kind": model_kind,
                "evaluation_status": "validated" if validated else "rejected",
                "metrics": evaluations, "audit": audit,
                "fpr_bound_method": "Wilson 95%; assumes independent Bernoulli requests",
                "training_records": len(fit), "cross_dataset_name": cross_dataset,
                "dataset_sha256": hashlib.sha256(json.dumps([
                    [r["path"], r["query_redacted"], r["ts"], r["session_id"], r["dataset"], r["label"]]
                    for r in rows], sort_keys=True).encode()).hexdigest()}
    output.mkdir(parents=True, exist_ok=True)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if validated:
        joblib.dump(model, output / "model.joblib")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cross-dataset", required=True)
    parser.add_argument("--target-fpr", type=float, default=.01)
    parser.add_argument("--model", choices=["logistic", "xgboost"], default="logistic")
    args = parser.parse_args()
    records = [json.loads(line) for line in args.records.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(json.dumps(train(records, args.output, args.cross_dataset, args.target_fpr, args.model), indent=2))

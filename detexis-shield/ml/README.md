# ML evaluation before deployment

No real-data model or FPR result ships with this change. The runtime defaults to
rules only. Controlled fixtures test pipeline mechanics and are not portfolio
accuracy claims.

Install `ml/requirements.txt` in a dedicated training/ML-worker environment and
install `sensor-sdk`. Canonical JSONL rows require:

```json
{"path":"/search","query_redacted":"q=hello","ts":"2026-11-01T10:00:00+00:00","session_id":"pseudonymous-reviewed-session","dataset":"own-site-a","label":0}
```

Labels must be operator-reviewed 0/1 values. Do not turn rule matches into ground
truth. For own traffic, `python -m app.export_training` exports only explicitly
labeled event IDs, scoped to one site. Daily IP hashes are conservative grouping
proxies, not authenticated sessions. Document NAT limitations and review labels.

CIC-IDS2017's published CSVs are **network-flow features**, not this SDK's URL
features. They cannot be renamed into compatible inputs. Compatible request-level
records would need extraction and label alignment from the original captures;
encrypted traffic cannot yield URLs without suitable plaintext evidence. See the
[primary dataset description](https://www.unb.ca/cic/datasets/ids-2017.html).
CSIC request corpora also need provenance review and conversion to the canonical
representation. Never invent timestamps or sessions when a source lacks them.
Keep dataset licenses/citations, conversion scripts and exclusions with the data.

```sh
python ml/train.py canonical.jsonl artifacts/logistic-v1 --cross-dataset held-out-source --target-fpr 0.01
python ml/train.py canonical.jsonl artifacts/xgboost-v1 --cross-dataset held-out-source --target-fpr 0.01 --model xgboost
```

The pipeline fits on the earliest 60%, chooses a threshold on the next 20%, and
evaluates the last 20%; sessions crossing boundaries are purged. A separate named
dataset is entirely held out. Reports include empirical FPR, a Wilson 95% upper
bound, recall, alerts per 1,000 requests, session purges, exact-request overlap,
cutoffs, dataset hash, feature schema and a model version. Repeated benign URLs are
not silently removed; overlap is reported for review. Similar attack templates
and cross-corpus duplicates still require manual leakage review before claims.

The default 1% target is judged against the confidence bound, so tiny benign test
sets cannot justify it. Artifacts are rejected when temporal or cross-dataset
results fail the FPR/recall gates. Choose data, thresholds and minimum recall before
opening the final test set; do not tune repeatedly on the held-out set.

Threshold search sorts scores and counts benign values above each candidate with
binary search, preserving the runtime's strict `score > threshold` comparison,
including ties. It requires O(n log n) work rather than rescanning every record
for every score. Unequal score/label lengths, empty evaluation sets, nonbinary
labels and nonfinite/out-of-range probabilities are rejected instead of silently
truncating metrics or treating invalid scores as non-alerts.

The Wilson bound assumes independent Bernoulli requests. Session grouping reduces
split leakage but does not make requests within sessions independent. Metadata
records this assumption; the bound is not a guarantee for correlated production
traffic. Representative site/session-level uncertainty analysis remains required
before real-world FPR claims. Public benchmark labels are not customer evidence.

Use a new artifact directory for each run. Only a validated artifact contains
`model.joblib`. After independently reviewing its report, mount it read-only in the
worker, install compatible ML dependencies, set `SHIELD_MODEL_DIR`, and restart the
worker. Never accept uploaded joblib files. Schema/load/prediction failures fall
back to rules. XGBoost alerts attempt SHAP reasons in raw model-output units (log
odds for its default binary objective); contributions are not causal explanations.
See [SHAP's TreeExplainer documentation](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html).

For Docker, set `SHIELD_MODEL_PATH` to the absolute directory of the reviewed
artifact and add `-f docker-compose.ml.yml` to the Compose invocation. It builds
the worker with the pinned ML dependencies and mounts the artifact read-only;
the normal API and scanner images do not need ML packages. This override is
optional and is not enabled by default.

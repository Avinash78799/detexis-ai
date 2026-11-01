# Shared request features, schema version 1

Both Python sensors call `detexis_shield.features.extract_features(path,
query_redacted)` after redaction. Workers and training code can import the same
function by installing `sensor-sdk`. Inputs must be the event's stored path and
redacted query; raw datasets must first be converted to this representation.

| Field | Definition |
| --- | --- |
| `schema_version` | Metadata value `1`; do not include it as a model input. |
| `payload_len` | UTF-8 byte length of the stored path plus `?` and stored query when present. It is **not** the HTTP body size or original request size. |
| `special_char_ratio` | Fraction of characters that are neither alphanumeric nor whitespace in the path followed by decoded query names and values. Structural query separators are omitted; sensitive values and redaction markers are excluded. Unicode letters are alphanumeric. |
| `num_params` | Number of parsed query pairs, including repeated names, empty names and blank values. Empty separator-only fields are ignored. |
| `path_depth` | Number of nonempty slash-separated segments in the stored path. |

The output is a dictionary of JSON-compatible numbers. Ratios are in `[0, 1]`;
empty input gives zero. Query values are percent-decoded once for the character
ratio. Framework-decoded paths are not decoded again. WSGI path bytes are converted
from their Latin-1 transport representation to UTF-8 to match ASGI paths.

Parsing is bounded: redaction considers the first 8,192 raw query bytes and at most
50 fields. Events retain at most 2,048 path characters and 1,024 query characters.
Feature extraction applies those stored-field limits too, so offline callers
cannot accidentally process unbounded input. Long inputs describe only the
retained portion. The request body and Content-Length are not used.

Redaction now re-encodes query pairs, preserving `%26` and `%3D` inside values,
duplicate keys and blanks. Consumers must parse the stored query rather than
searching only its encoded text. Password/token values are replaced before feature
calculation. Only the configured sensitive-key list is masked; arbitrary queries
can still contain personal data and the sensor does not capture request bodies.

These are detection inputs, not attack verdicts. Punctuation-heavy search terms,
international paths and repeated parameters can all be legitimate. Evaluate false
positives on real benign traffic before choosing model thresholds.

The backend currently stores sensor-provided features. Future workers must
recompute from stored fields and validate the version, rather than trusting a
client-provided feature dictionary. Training artifacts must record version `1`
and the ordered four model input names. Version mismatch handling belongs with
the future worker/model loader; no classifier is included in this change.

Use these checks from this directory:

```sh
python -m pytest -q -p no:cacheprovider
python benchmark_sensor.py
python benchmark_sensor.py --profile large-query
```

The benchmark uses a real sender thread with simulated backend failure. It is an
in-process ASGI microbenchmark, not a server or production load test.

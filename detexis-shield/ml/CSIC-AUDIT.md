# CSIC corpus audit: 18 November 2026

This is a representation and stateless-rule audit, **not** a trained model,
deployment FPR, attack recall or release approval. ML remains disabled. No raw
requests, cookies, credentials, bodies or dataset files are committed.

## Source and semantics

The [CSIC authors' archived description](https://petescully.co.uk/wp-content/uploads/2018/04/http_dataset_csic_2010.pdf)
describes generated e-commerce traffic, with normal-training, normal-test and
anomalous-test subsets. Its anomalous class includes non-malicious invalid
requests. Therefore `anomalous` cannot be silently relabeled `malicious`.

The original CSIC landing page timed out in the current check, and the academic
mirror returned 404. The audit used a third-party raw-file mirror at
[`msudol/Web-Application-Attack-Datasets`](https://github.com/msudol/Web-Application-Attack-Datasets/tree/424c6e1c1951570473d9d6c0227eaaac6fdd6d02/OriginalDataSets/csic_2010),
pinned to commit `424c6e1c1951570473d9d6c0227eaaac6fdd6d02`. No author-provided
checksum was verified against it. Upstream license terms remain unverified;
files are retained privately for this diagnostic and are not redistributed or
used to authorize a model release. The private manifest records URLs and hashes.

| File | Bytes | Parsed/projected records | Records with bodies |
| --- | ---: | ---: | ---: |
| normalTrafficTraining.txt | 20,148,988 | 36,000 | 8,000 |
| normalTrafficTest.txt | 20,151,204 | 36,000 | 8,000 |
| anomalousTrafficTest.txt | 15,734,523 | 25,065 | 9,977 |

SHA256, in table order:

```text
d51de812d9201ef2b173b6ae3e3e740c309047ac85545c06c51d6fb1ddbc1e63
f05dfc312d5d14fd1ed8371de27a9e4deab3dc09265f5d7f9df2643df8385089
12fa4f0d496ceb859bb2652abf7f0f0ed8c59e1d9ce501b8a9a0ef38a625c046
```

## Projection and results

`ml/audit_csic.py` parses bounded inert HTTP records using declared body lengths,
so request-looking text inside a body cannot become a new record. It never
fetches request targets. Unsupported framing fails explicitly; it does not
heuristically skip malformed records and claim complete coverage.

The projection decodes the path as ASGI/Werkzeug do, applies the SDK's actual
query redaction/truncation and shared feature extractor, and retains bounded UA
for stateless rules. Cookies and bodies are omitted. Response status is unknown;
no timestamps, sessions, site-specific canaries or request-rate windows are
invented. All 97,065 records parsed and projected with zero exclusions.

Rule release `2026.11.14.1` matched **zero of 36,000** records in each source-normal
file. The observed source-normal stateless match rate was zero, not a confidence
bound or production FPR. Generated repeated requests are not independent customer
observations. The 25,065 source-anomalous records produced **1,009** matching
requests: XSS 358, SQL delay 522, command injection 93, SQL boolean 36. Counts
refer to patterns in the projected URL/UA; **4.026% is not attack recall** because
the source labels and missing body visibility do not support that interpretation.

Across source-normal/anomalous classes, **19** projected path/query
representations were identical. **819** four-feature vectors occurred in both
classes, covering 66,473 normal and 12,764 anomalous rows. Identical numeric inputs
cannot receive distinct deterministic scores solely because their source labels
differ. This is an observability limitation, not proof of universal model failure.

All body-bearing records had empty query strings, including 9,977 anomalous rows.
This does not prove every such body contains an attack. It does establish that
their form content is absent from the current SDK/model input. A classifier
cannot infer unseen payload content reliably; body-aware detection needs a
separate privacy-reviewed design, rather than pretending URL metrics cover it.

Private report: `outputs/ml-datasets/csic-audit-20261118.json`, SHA256
`dd26b3e6c72818ca01cb066b4a6583e7f0b748fdee52f46bad8acc7c5347acfb`.
Private source manifest: `outputs/ml-datasets/csic-mirror-424c6e1/manifest.json`.
Reports contain aggregate counts, hashes and source offsets, not raw examples.

## Remaining model evidence

CSIC request capture times have not been established. File order must not be
converted into invented chronological timestamps to satisfy the existing trainer.
Cookie presence alone is not proof of real user sessions. Source anomaly labels
need explicit task/ground-truth review before supervised threat claims.

[CIC's primary description](https://www.unb.ca/cic/datasets/ids-2017.html) distinguishes
flow CSVs from original PCAPs and documents timestamp/IP/port-based flow labels.
Those CSV features cannot be renamed into SDK URL inputs. A compatible extraction
needs actual plaintext HTTP reconstruction, capture timestamps, conservative
session grouping and auditable label alignment; HTTPS alone does not expose URLs.
The official download form requires contact details, which the operator must
provide. No personal details were submitted by the agent.

The [Engelen/Rimmer/Joosen primary study](https://intrusion-detection.distrinet-research.be/WTMC2021/)
identifies traffic-generation, flow-construction and labeling problems in the
original CIC corpus. Its corrected tools and labels must be reviewed when
aligning extracted requests. Corrected flow labels still do not automatically
become request-level malicious ground truth. The operator supplied a download
browse link, but it returned HTTP 403 in this environment; no cookies were copied
and no access-control workaround was attempted. Local downloaded files are the
next requested input, while unrelated product work can continue.

Next gates remain: provenance-reviewed request data, reviewed benign/malicious
labels, real temporal/session separation, independent source holdout and leakage
review, fixed FPR/recall targets and production-representative uncertainty. This
audit does not weaken the trainer, manufacture metadata or produce an approved
model artifact. The rules-only runtime remains the current supported mode.

## Reproduce with privately obtained files

```powershell
python ml/audit_csic.py --normal C:\PRIVATE\normalTrafficTraining.txt --normal C:\PRIVATE\normalTrafficTest.txt --anomalous C:\PRIVATE\anomalousTrafficTest.txt --output C:\PRIVATE\new-corpus-audit.json
```

Keep source files unchanged. Use a new report path; the tool refuses overwrite.
The audit neither downloads files nor trains/publishes/loads models. Review
source rights and provenance separately before redistribution or release use.

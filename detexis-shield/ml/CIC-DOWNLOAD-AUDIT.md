# CIC-IDS2017 download audit: 21 November 2026

The owner supplied `Monday-WorkingHours.pcap` and `MachineLearningCSV.zip`.
The raw downloads remain outside the repository. No model was trained or enabled.

## Files and transfer checks

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| Monday-WorkingHours.pcap | 10,822,507,416 | `f6eac599358f216b074338813a1cf7be3cc4e91d116e13efc0dc71f2cca11972` |
| MachineLearningCSV.zip | 235,102,953 | `c3f26274b36c837ccf28ffd2dbf4582941c30b3ee70a635c6e5b2f87c4727928` |

The CSV ZIP's MD5 matches the owner's downloaded manifest:
`4f83860afbf29cac8163854095bf6cf7`. That manifest names
`MachineLearningCVE.zip`; the local ZIP is named `MachineLearningCSV.zip`.
The comparison is over file bytes, regardless of the name. MD5 here checks
transfer consistency, not authenticity. No author-supplied Monday checksum was
available for comparison; its SHA-256 identifies the inspected local copy.

## What the files actually contain

Despite its `.pcap` suffix, Monday is **pcapng**. A full `capinfos` pass using
TShark/Wireshark **4.4.19** completed successfully and reported **11,709,971**
Ethernet packets over **29,135.874581 seconds**. This establishes readable capture
structure, not complete HTTP conversations or correct labels.

The ZIP contains eight CSVs and **2,830,743 flow rows**. Each CSV has 79 columns,
including a duplicated `Fwd Header Length` column. All lack timestamp, source-IP,
destination-IP and flow-ID columns. The audit records duplicate column names;
it does not choose one or feed them to Shield's URL-feature model.

| CSV subset | Flow rows | Source labels relevant here |
| --- | ---: | --- |
| Monday | 529,918 | All `BENIGN` |
| Thursday morning web attacks | 170,366 | 168,186 benign; 1,507 brute force; 652 XSS; 21 SQL injection |

These are **flow counts, not HTTP request counts**. The source web-attack label
strings contain mojibake; the private report preserves them rather than silently
rewriting label names. Source labeling does not establish independent ground
truth for every request or successful exploitation.

The [official CIC description](https://www.unb.ca/cic/datasets/ids-2017.html)
identifies Monday as a benign day and Thursday morning as the web-attack period.
It distinguishes packet captures, `GeneratedLabelledFlows.zip` and the ML CSV
download. The downloaded ML CSVs cannot reliably join labels back to requests:
their source/destination addresses and times are absent. The next relevant
downloads are Thursday's capture and the generated labeled flows. Further label,
clock/time-zone and flow-boundary review remains necessary even with those files.

## Reproduce the read-only download audit

```powershell
python ml/audit_cic_downloads.py `
  --capture 'C:\private-datasets\Monday-WorkingHours.pcap' `
  --csv-zip 'C:\private-datasets\MachineLearningCSV.zip' `
  --csv-md5 'C:\private-datasets\MachineLearningCSV.md5' `
  --report 'C:\private-outputs\cic-download-audit.json'
```

This streams hashes, reads CSVs directly from the ZIP and emits aggregate schema,
row and label counts. It does not unpack files, print requests, execute payloads,
assign request labels or train a classifier. An existing report is never replaced.
CSV width errors and ambiguous label columns stop the audit. Complete member reads
also exercise ZIP CRC checks.

Private evidence: `outputs/ml-datasets/cic-download-audit-20261121.json`,
`monday-capinfos-20261121.txt` and `tshark-version-20261121.txt`.

## HTTP representation audit

`audit_cic_http.py` aggregates selected TShark EK fields, projects the same bounded
path/query/UA representation as the CSIC audit, redacts named query secrets and
evaluates stateless rules with unknown response status. It retains no request
targets, user agents, bodies, cookies or addresses in its report. Ambiguous
multi-request frames and non-ASCII strings needing byte-fidelity review are
explicit exclusions. The caller must check the analyzer's actual exit status;
partial output is not a completed run.

The analyzer runs unprivileged with no network, no capture capabilities and a
read-only container filesystem. It reads the existing 10.82 GB file without making
another capture copy. TCP/HTTP reassembly and out-of-order TCP
reassembly are enabled. No Windows capture driver or system certificate change is
required.

Two early full-file HTTP attempts **failed** their memory budgets: general
dissection at 768 MiB, then a port-filtered bidirectional stream at an initial
768 MiB increased to 1,536 MiB after checking app memory. Actual container state
confirmed OOM termination. Their incomplete/truncated output is not a result.
Both private failure reports are retained; no rule-match percentage is taken from
either attempt.

The subsequent approach streams the client request direction into TShark using
`tcpdump -n -r <capture> -U -w -` with this exact BPF expression:

```text
(tcp dst port 80 or tcp dst port 8080 or tcp dst port 8000 or tcp dst port 8888) or (ip[6:2] & 0x3fff != 0) or ip6
```

IPv4 fragments and IPv6 packets are retained to avoid selectively removing IP
reassembly pieces. Other ports and ordinary response streams are outside this
audit. Filtered frame ordinals are not original capture frame numbers. Both the
filter and analyzer must exit zero; no pipeline-tail-only success check is used.
The analyzer enables `tcp.desegment_tcp_streams`, `tcp.reassemble_out_of_order`,
`http.desegment_headers` and `http.desegment_body`; `-n` disables name resolution.
Its `http.request` EK output selects only frame number/time, TCP stream, request
method/URI and user agent. `audit_ek()` consumes that output without saving it.

A seven-packet synthetic capture passed this request-direction pipeline: two
requests were each split over TCP segments, one body contained a request-like
line, and one query matched the SQL UNION rule. Exactly two requests and one
matching frame were reported. The body was not turned into another request, and
query secret/cookie/target strings were absent from the aggregate report. This
fixture establishes the exercised framing behavior, not corpus quality.

## Completed request-stream result

The final run streamed the read-only Windows source file through local Docker
stdin instead of repeatedly reading its shared-folder mount. It completed in
555.266 seconds with a **768 MiB memory limit and two CPU cores**. The packet
filter, analyzer and container all exited zero; actual container state reports
no OOM kill. An earlier request-direction run through the shared-folder mount was
stopped when switching to this validated input method and is retained as
incomplete. No count is combined across attempts.

| Measure | Result |
| --- | ---: |
| Analyzer-recognized HTTP request frames | 54,719 |
| Unambiguous projected single-request frames | 54,713 |
| Excluded ambiguous/missing-field frames | 6 |
| GET / POST / HEAD / OPTIONS | 38,524 / 15,965 / 78 / 146 |
| Frames matching any stateless rule | 140 |
| Matching rule | `command_injection` (140) |

These **140 matches need case review** against the source benign-day description.
They are potential false positives, not confirmed attacks. The approximately
0.256% matching fraction applies only to the projected plaintext subset and this
stateless rule release. It is not production FPR: source labeling is not an
independent request review; encrypted/other-port traffic, ambiguous frames,
response status, bodies and stateful detection are outside the measurement.
No rule was suppressed and no model was enabled to improve these counts.

The rule source SHA-256 is
`d39123a7a05e7c29bfd1e29976edd5d22b9eae2710b39159d5e6fdb6fd2bdf80`.
The HTTP aggregate helper SHA-256 is
`ca5c3c4516667819ba301762437189d90f306ccebf5a81058e40322fad12c477`.
Private full-run evidence: `outputs/ml-datasets/monday-http-streamed-audit-20261121.json`.
Its finalized report SHA-256 is
`88939ca140a42ef5a87fcf1498773ae5dba87c4604231e9c36337fc3d39f66c9`.
The local app's CA-verified readiness check still passed afterward.

## Assignment-boundary correction

Masked review of the first five matching frames found `;cat` in path parameters
and `&&id` in query inputs, immediately followed by assignment `=` characters.
The report retained trigger words, numeric frame/stream/time references and
masked nearby syntax, not raw targets, queries or cookies. This identified the
old command regex's word-boundary error. A fixed Bash assignment fixture and
independent executable-command regressions check the intended distinction.

Version 3 (`2026.11.21.1`) was then evaluated alongside the hash-verified old
source in **one complete replay** of the same request-direction stream. The old
implementation again matched 140 frames, while the corrected implementation
matched **zero**; projected/excluded counts and method counts stayed identical.
Both the filter and analyzer exited zero; the container completed without OOM.
The paired run took 737.125 seconds with the same 768 MiB/two-core limits.

This corpus informed the change, so the result is **regression evidence on a
development corpus**, not independent validation, general attack recall or a
production zero-FPR claim. No labels were rewritten, no request history was
reprocessed and ML remains disabled. Source hashes distinguish the comparisons:

- Previous rule source: `d39123a7a05e7c29bfd1e29976edd5d22b9eae2710b39159d5e6fdb6fd2bdf80`.
- Corrected source: `3ff122d2223ebc19229a0d307d2bace1571d75a7b1ac9be4db9406bf1ddc7f84`.
- Private paired report: `outputs/ml-datasets/monday-http-candidate-v3-audit-20261121.json`.
- Report SHA-256: `885cff9aeda2789edb0b24da89bd51e5d3eebcab82ea61f3628eff4b79c5fded`.

The corrected release is now activated locally; `RULE-RELEASES.md` records
backup/source/role consistency and the unchanged owner-data checks. Compatible
Thursday attack/request labels, independent real benign traffic and actual ML
evaluation are still required.

[Wireshark's reassembly documentation](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvReassemblySection.html)
explains why missing segments, capture boundaries and reassembly timing matter.
Encrypted HTTPS is outside this audit. Recognized plaintext HTTP is a selected
subset of network traffic; stateless rule counts on that subset are not a claim
of production false-positive rate, ML quality or modern-attack coverage.

## Generated-label archive found and audited on 21 November

The supplied Downloads folder also contains `GeneratedLabelledFlows.zip`
(283,876,488 bytes). Its MD5 matches the supplied manifest,
`5ca3f8f69e3514950681615824149973`; this checks transfer consistency, not source
authenticity. SHA256:
`7bdbef286f8893f31c6db12105fa097fa5c2dcc6733179037a08129d150ea27a`.

All eight CSV members were read directly without extraction, with complete CRC
checks, schema/row-width checks and bounded label vocabularies. They contain
**2,830,743 labeled rows**, each with 85 columns including flow ID, timestamp,
source/destination addresses and Label. Thursday morning has 170,366 labeled
rows: 168,186 BENIGN, 1,507 source brute-force labels, 652 XSS and 21 SQL injection.
Unlike the earlier MachineLearningCSV archive, joining metadata is present.
Timestamp interpretation, flow/request alignment, ambiguity and label quality
still need validation; column presence alone establishes none of these.

The default strict UTF-8 audit stopped on byte `0x96`. Explicit `cp1252` decoding
reads the archive without replacement characters; source labels still include
mojibake and are not silently normalized or treated as authoritative attack
ground truth. This explicit, reversible decoding is an audit choice, not proof
of a single intended encoding for every member. The next strict attempt rejected
an entirely blank record after the Thursday-morning labeled rows. A reviewed
opt-in now counts blank records separately while continuing to reject partially
populated unlabeled rows. The completed run excluded **288,602 entirely blank
records**, all in the Thursday-morning member; these are not labeled examples.
Both preliminary failures remain recorded rather than supplying partial totals.

`audit_cic_downloads.py` defaults remain strict; `--csv-encoding cp1252` and
`--exclude-blank-records` explicitly select these audit policies. Unit tests cover
default refusal, exact legacy-label decoding, counted blank exclusions and
continued rejection of nonblank unlabeled rows. The complete generated-label
audit took 34.485 seconds. Private report:
`outputs/ml-datasets/generated-flows-full-audit-20261121.json`.
SHA256: `21d0d6712adb271abf7a0a64ad7f434b70f46d30704274330c7535c900bc246f`.

`Thursday-WorkingHours.pcap` was absent at the expected path when checked. No
attack request was extracted, flow label joined, timestamp invented or model
trained/enabled. Independent benign traffic and cross-dataset ML evaluation
remain separate release requirements.

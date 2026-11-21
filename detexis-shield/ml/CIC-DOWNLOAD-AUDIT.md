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

The analyzer runs unprivileged with no network, no capture capabilities, a read-only
input bind and a read-only container filesystem. It reads the existing 10.82 GB
file without making another capture copy. TCP/HTTP reassembly and out-of-order TCP
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

[Wireshark's reassembly documentation](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvReassemblySection.html)
explains why missing segments, capture boundaries and reassembly timing matter.
Encrypted HTTPS is outside this audit. Recognized plaintext HTTP is a selected
subset of network traffic; stateless rule counts on that subset are not a claim
of production false-positive rate, ML quality or modern-attack coverage.

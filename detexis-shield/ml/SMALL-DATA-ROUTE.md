# Evaluation without more full-day packet downloads

Owner decision, 22 November: remaining multi-gigabyte downloads are impractical.
Do not require the owner to download the rest of CIC's full-day captures. Existing
Monday/CSV/CSIC files and their completed audits remain retained.

The official [CIC-IDS2017 description](https://www.unb.ca/cic/datasets/ids-2017.html)
lists Thursday's capture as 7.8 GB and identifies the web-attack periods. This is
smaller than some reported downloads, but still large; neither the other capture
days nor the entire dataset is needed just to investigate HTTP attacks. No
replacement download or remote packet extraction has yet been validated.

Use the already-audited CSIC request corpus and Monday replay for development
regressions, preserving their provenance/label limitations. Do not invent session
timestamps or treat source anomalies as uniformly malicious. Generated flow CSVs
have joining columns but cannot reconstruct missing HTTP request content.

The authors' [WAF-A-MoLE dataset](https://github.com/zangobot/wafamole_dataset)
provides SQL-query samples in chunks. It is a candidate for focused SQL-pattern
evaluation, **not** a substitute for representative HTTP traffic or a broad web
classifier. Its README says individual chunks are untested and queries may span
newlines, so naive line sampling is invalid. Check license/provenance, record
immutable source hashes and validate record boundaries before acquiring/using it.
No samples from this source have been downloaded, executed, trained on or scored.

Independent normal-request evaluation still needs permissioned traffic from real
applications. The current monitor/rule product can be exercised while collecting
that evidence; it must not advertise a calibrated ML classifier meanwhile.
Time/session separation, cross-dataset testing and false-positive confidence
bounds stay required. No threshold or label requirement is relaxed to avoid a
large download. ML remains disabled until those gates actually pass.

"""Identify the rules actually installed; no remote rule code is downloaded."""
import hashlib
import json
from pathlib import Path

from .rules import (RULES, RULESET_VERSION, RULESET_RELEASE, RULESET_DATE,
                    MAX_PATH, MAX_QUERY, MAX_FIELDS, MAX_UA)

ROOT = Path(__file__).parent
RULES_SHA256 = hashlib.sha256((ROOT / "rules.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def release_record():
    return json.loads((ROOT / "rule_releases" / (RULESET_RELEASE + ".json")).read_text(encoding="utf-8"))


def manifest():
    try:
        record = release_record()
        verified = (record["release_id"] == RULESET_RELEASE and record["rules_version"] == RULESET_VERSION
                    and record["rules_source_sha256"] == RULES_SHA256 and record["released_on"] == RULESET_DATE)
    except (OSError, ValueError, KeyError, TypeError):
        verified = False
    return {"release_id":RULESET_RELEASE, "rules_version":RULESET_VERSION,
            "bundled_on":RULESET_DATE, "rules_source_sha256":RULES_SHA256,
            "release_record_verified":verified, "mode":"monitor",
            "delivery":"bundled_with_deployment", "remote_update_status":"not_configured",
            "limits":{"path_characters":MAX_PATH,"query_characters":MAX_QUERY,
                      "query_fields":MAX_FIELDS,"user_agent_characters":MAX_UA},
            "rules":[{"id":name,"severity":values[0],"cwe":values[1],"owasp":values[2],
                      "reason":values[3],"scope":("traffic_history" if name in {"login_brute_force","request_flood"}
                          else "site_configuration" if name == "honeytoken" else "single_request")}
                     for name,values in RULES.items()],
            "limitations":["Findings are review signals, not proof of exploitation.",
                "Raw bodies, cookies and authorization headers are not inspected.",
                "Named secret query fields are redacted; unrecognized fields may still contain sensitive data.",
                "This is a bounded heuristic engine, not a complete WAF or a SQL parser.",
                "A bundled release date does not prove coverage of all threats disclosed afterward."]}

import pytest
from urllib.parse import urlencode
from app.rules import RULES, evaluate

CASES = {
    "sqli_boolean": (["or 1=1", "AND 42=42", "or 'x'='x'"], ["order 1", "or 1=2", "rock and roll"]),
    "sqli_union": (["union select a", "UNION ALL SELECT b", "union\nselect c"], ["trade union", "select a", "unionized workforce"]),
    "sqli_time": (["sleep(5)", "pg_sleep(1)", "waitfor delay '0:0:1'"], ["sleep well", "benchmark results", "time delay"]),
    "xss": (["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "<svg onload=alert(1)>"], ["<b>hello</b>", "script writing", "<img src=photo.jpg>"]),
    "path_traversal": (["../../etc/passwd", "..\\..\\windows", "../config"], ["version..txt", "folder/file", ".well-known/security.txt"]),
    "command_injection": ([";whoami", "&& cat /etc/passwd", "$(curl example.com)"], ["cat pictures", "hello; world", "fish && chips"]),
    "ssrf_params": (["http://127.0.0.1/a", "http://169.254.169.254/", "http://[::1]/"], ["https://example.com", "https://8.8.8.8", "ordinary text"]),
    "scanner_ua": (["sqlmap/1.0", "Mozilla nikto", "nuclei scanner"], ["Mozilla/5.0", "Googlebot/2.1", "MyApp/1.0"]),
    "sensitive_path": (["/.git/config", "/wp-config.php", "/backup.sql"], ["/settings", "/.well-known/security.txt", "/docs/env"]),
    "honeytoken": (["/canary", "/canary", "/canary"], ["/", "/canary-info", "/real-admin"]),
    "login_brute_force": ([10, 11, 100], [0, 3, 9]),
    "request_flood": ([300, 301, 1000], [0, 30, 299]),
}


@pytest.mark.parametrize("rule_id", list(CASES))
@pytest.mark.parametrize("positive", [True, False])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_each_rule_has_three_positive_and_negative_cases(rule_id, positive, index):
    value = CASES[rule_id][0 if positive else 1][index]
    kwargs = {"path": "/search", "query": "", "ua": "browser"}
    if rule_id == "ssrf_params":
        kwargs["query"] = urlencode({"url": value})
    elif rule_id == "scanner_ua":
        kwargs["ua"] = value
    elif rule_id in {"sensitive_path", "honeytoken"}:
        kwargs["path"] = value
        kwargs["honeytokens"] = ["/canary"]
    elif rule_id == "login_brute_force":
        kwargs.update(path="/login", status=401, failed_logins=value)
    elif rule_id == "request_flood":
        kwargs["request_count"] = value
    else:
        kwargs["query"] = urlencode({"q": value})
    assert (rule_id in {f.rule_id for f in evaluate(**kwargs)}) == positive
    assert RULES[rule_id][1].startswith("CWE-")
    assert RULES[rule_id][2].endswith(":2025")


def test_hostile_separator_count_is_bounded():
    assert evaluate("/", "&" * 10000) == []

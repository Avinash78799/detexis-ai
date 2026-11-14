"""Defensive fixtures only; nothing is sent to or executed by a target site."""
from urllib.parse import urlencode
import pytest
from app.rules import evaluate


@pytest.mark.parametrize("value,rule", [
    ("UNION/**/SELECT username", "sqli_union"),
    ("UNION/* note\nline */ALL/**/SELECT name", "sqli_union"),
    ("OR/**/1=1", "sqli_boolean"),
    ("SLEEP/**/(5)", "sqli_time"),
    ("WAITFOR/**/DELAY/**/'0:0:1'", "sqli_time"),
    ("UNION/*!50000SELECT*/ name", "sqli_union"),
    ("/*!50000UNION SELECT*/ name", "sqli_union"),
    ("OR/*!50000 1=1*/", "sqli_boolean"),
])
def test_comment_separated_sql_patterns_are_detected(value, rule):
    assert rule in {f.rule_id for f in evaluate("/search", urlencode({"q":value}))}


@pytest.mark.parametrize("value", [
    "/* union select */ documentation", "/* or 1=1 */ documentation",
    "/* sleep(5) */ documentation", "un/**/ion select", "union/* note */membership",
    "sleep/* help */ tips", "union membership", "select a holiday", "rock and roll",
])
def test_comment_and_normalization_regressions_do_not_invent_sql(value):
    assert not {f.rule_id for f in evaluate("/search", urlencode({"q":value}))} & {
        "sqli_union", "sqli_boolean", "sqli_time"}


@pytest.mark.parametrize("path,query", [
    ("/docs/union", "select=example"),
    ("/help/or", "1=1"),
    ("/search", "q=UNION%2F%2A&note=%2A%2FSELECT"),
])
def test_separate_input_fields_are_not_combined_into_an_attack(path, query):
    assert not {f.rule_id for f in evaluate(path, query)} & {"sqli_union", "sqli_boolean"}


def test_sql_normalization_does_not_remove_html_evidence():
    findings = evaluate("/search", urlencode({"q":"<script>/* ordinary comment */alert(1)</script>"}))
    assert "xss" in {f.rule_id for f in findings}


def test_unterminated_comments_and_repeated_separators_remain_bounded():
    assert evaluate("/docs", "q=" + "/*" * 10000) == []
    assert evaluate("/docs", "&" * 10000 + "q=union select") == []

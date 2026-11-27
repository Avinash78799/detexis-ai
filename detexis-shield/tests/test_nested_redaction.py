from urllib.parse import parse_qsl, urlencode

import pytest
from detexis_shield.redact import redact_query
from detexis_shield.features import extract_features


@pytest.mark.parametrize("key", ["credentials[password]", "auth.token", "Password[]",
    "users[0][passwd]", "auth[access_token]", "headers.authorization", "client[api_key]",
    "payment.card", "auth.session.sid", "credentials[OTP]"])
def test_nested_named_secret_values_are_masked(key):
    query = urlencode([(key, "synthetic-private-value"), ("q", "union select name"), (key, "another-private-value")])
    result = redact_query(query)
    assert parse_qsl(result) == [(key, "[REDACTED]"), ("q", "union select name"), (key, "[REDACTED]")]
    assert "private-value" not in result
    first = redact_query(urlencode({key:"short"}))
    second = redact_query(urlencode({key:"much-longer-secret-value"}))
    assert extract_features("/login", first) == extract_features("/login", second)


@pytest.mark.parametrize("key", ["password_policy", "tokenizer", "sidereal", "cardinality", "filters[query]"])
def test_similar_benign_field_names_preserve_detection_values(key):
    assert parse_qsl(redact_query(urlencode({key:"union select name"}))) == [(key,"union select name")]

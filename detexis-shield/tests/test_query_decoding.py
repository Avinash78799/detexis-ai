"""Differential privacy/representation checks against the standard decoder."""
import random
from urllib.parse import parse_qsl, urlencode

import pytest
from detexis_shield.redact import _parse_query, redact_query, SENSITIVE_KEYS


@pytest.mark.parametrize('suffix', [
    '&&flag&=empty-name&blank=&x=a=b', 'x=%E2%82%AC+%F0%9F%98%80',
    'x=%FF%C0%AF%E2%82&y=%ZZ%2%&z=%2526%253D',
    'x=%26%3D%2B+&password=secret&%50ASSWORD=also-secret',
    'x=literal-é&token=secret', 'x=\ud800',
])
def test_long_escape_runs_preserve_utf8_errors_delimiters_and_secrets(suffix):
    query = 'q='+'%3c%3E%27%22'*80+'&'+suffix
    assert _parse_query(query) == parse_qsl(query, keep_blank_values=True)
    if '\ud800' in query:
        with pytest.raises(UnicodeEncodeError):
            redact_query(query)
        return
    pairs = parse_qsl(query, keep_blank_values=True)
    expected = urlencode([(k, '[REDACTED]' if k.lower() in SENSITIVE_KEYS else v) for k,v in pairs])[:1024]
    assert redact_query(query) == expected


def test_seeded_mixed_encodings_match_stdlib_without_skipping_fields():
    randomizer = random.Random(20261122)
    tokens = ['a', 'Z', '+', '=', '%', '%2', '%ZZ', '%ff', '%E2%82%AC', '%26', '%3D', '%25', '%00', '%41']
    for _ in range(1000):
        query = 'q='+'%41'*64+'&'+'&'.join(''.join(randomizer.choices(tokens,k=20)) for _ in range(5))
        assert _parse_query(query) == parse_qsl(query, keep_blank_values=True)

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('audit_cic_http', Path(__file__).parents[1] / 'ml/audit_cic_http.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def packet(**changes):
    fields = {'frame_number':['12'], 'frame_time_epoch':['1499083200.125'], 'tcp_stream':['1'],
              'http_request_method':['GET'], 'http_request_uri':['/products?password=secret-fixture'],
              'http_user_agent':['synthetic-agent']}
    fields.update(changes)
    return json.dumps({'layers':fields})


def test_fields_are_projected_redacted_and_not_retained_in_report(monkeypatch):
    seen = []
    monkeypatch.setattr(audit, 'evaluate', lambda *args: seen.append(args) or [])
    result = audit.audit_ek([json.dumps({'index':{}}), packet()])
    assert result['projected_single_request_frames'] == 1
    assert seen[0][0] == '/products'
    assert 'secret-fixture' not in seen[0][1]
    assert seen[0][3] is None
    assert result['first_projected_packet_epoch'] == '1499083200.125'
    assert not any(value in json.dumps(result) for value in ['secret-fixture', 'products', 'synthetic-agent'])
    assert result['model_trained'] is False


def test_ambiguous_multiple_requests_are_not_incorrectly_paired():
    result = audit.audit_ek([packet(http_request_uri=['/first','/second'], http_request_method=['GET','POST'])])
    assert result['projected_single_request_frames'] == 0
    assert result['excluded_frames'] == {'ambiguous_or_missing_fields':1}


def test_real_rules_receive_decoded_path_and_redacted_query():
    result = audit.audit_ek([packet(http_request_uri=['/search?q=1%20UNION%20SELECT%20id'])])
    assert result['matching_frames'] == 1
    assert result['rule_matches']['sqli_union'] == 1
    assert 'UNION' not in json.dumps(result)


@pytest.mark.parametrize('change,reason', [
    ({'frame_time_epoch':['NaN']}, 'invalid_timestamp'),
    ({'http_request_uri':['/café']}, 'non_ascii_requires_byte_review'),
    ({'http_request_uri':['*']}, 'unsupported_request_target'),
])
def test_uncertain_metadata_is_excluded_explicitly(change, reason):
    result = audit.audit_ek([packet(**change)])
    assert result['excluded_frames'] == {reason:1}
    assert result['projected_single_request_frames'] == 0


def test_truncated_analyzer_output_is_not_a_successful_audit():
    with pytest.raises(ValueError, match='Malformed analyzer JSON'):
        audit.audit_ek([packet(), '{"layers":'])

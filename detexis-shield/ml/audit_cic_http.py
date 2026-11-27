"""Aggregate selected TShark EK HTTP fields without retaining request content.

The caller must verify analyzer exit status before publishing a report. These
stateless rule counts are not ML evaluation or proof that all traffic is benign.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_csic import project
from app.rules import evaluate
from app.rule_manifest import RULESET_RELEASE, RULES_SHA256


def values(layers, name):
    value = layers.get(name, [])
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError('Unexpected analyzer field type')
    return value


def audit_ek(lines):
    exclusions, methods, matches = Counter(), Counter(), Counter()
    frames = projected = matching = 0
    first = last = None
    for line in lines:
        if len(line) > 1024 * 1024:
            raise ValueError('Analyzer record exceeds limit')
        try:
            packet = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError('Malformed analyzer JSON') from None
        if not isinstance(packet, dict):
            raise ValueError('Unexpected analyzer record')
        if 'index' in packet and 'layers' not in packet:
            continue
        layers = packet.get('layers')
        if not isinstance(layers, dict):
            raise ValueError('Missing analyzer fields')
        frames += 1
        required = [values(layers, name) for name in
                    ['frame_number', 'frame_time_epoch', 'tcp_stream', 'http_request_method', 'http_request_uri']]
        ua = values(layers, 'http_user_agent')
        if any(len(value) != 1 for value in required) or len(ua) > 1:
            exclusions['ambiguous_or_missing_fields'] += 1
            continue
        frame, timestamp, stream, method, target = [value[0] for value in required]
        if not frame.isdigit() or not stream.isdigit() or not re.fullmatch(r'[A-Z]{1,10}', method):
            exclusions['invalid_request_metadata'] += 1
            continue
        try:
            epoch = Decimal(timestamp)
            if not epoch.is_finite() or epoch < 0 or epoch > 4102444800:
                raise InvalidOperation
        except InvalidOperation:
            exclusions['invalid_timestamp'] += 1
            continue
        agent = ua[0] if ua else ''
        # TShark's decoded non-ASCII strings need a separate byte-fidelity review
        # before comparing them to ASGI/Werkzeug's Latin-1 query/header mapping.
        if not target.isascii() or not agent.isascii():
            exclusions['non_ascii_requires_byte_review'] += 1
            continue
        try:
            observed = project({'target':target, 'ua':agent[:512]})
        except ValueError:
            exclusions['unsupported_request_target'] += 1
            continue
        findings = evaluate(observed['path'], observed['query_redacted'], observed['ua'], None)
        projected += 1
        methods[method] += 1
        matching += bool(findings)
        matches.update(finding.rule_id for finding in findings)
        first = epoch if first is None else min(first, epoch)
        last = epoch if last is None else max(last, epoch)
    return {'release_evidence':False, 'model_trained':False, 'http_request_frames':frames,
            'projected_single_request_frames':projected, 'excluded_frames':dict(exclusions),
            'methods':dict(methods), 'matching_frames':matching, 'rule_matches':dict(matches),
            'first_projected_packet_epoch':str(first) if first is not None else None,
            'last_projected_packet_epoch':str(last) if last is not None else None,
            'rules_release':RULESET_RELEASE, 'rules_source_sha256':RULES_SHA256,
            'scope':'Stateless SDK path/query/UA projection of analyzer-recognized single HTTP requests. Status unknown; no body/cookie inspection, site honeytokens, stateful rules, TLS decryption, ML, request labels or production FPR claim. Packet timestamps are not asserted to be request-start timestamps.'}

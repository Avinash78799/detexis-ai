"""Deterministic URL features shared by sensors, workers and training code.

Input is the stored, redacted event representation, never a raw request body.
"""
from urllib.parse import parse_qsl

from .redact import MAX_QUERY_FIELDS, MAX_QUERY_STORED, SENSITIVE_KEYS

FEATURE_SCHEMA_VERSION = 1
MAX_PATH_STORED = 2048


def extract_features(path: str, query_redacted: str) -> dict:
    path = path[:MAX_PATH_STORED]
    query = query_redacted[:MAX_QUERY_STORED]
    bounded = "&".join(query.split("&", MAX_QUERY_FIELDS)[:MAX_QUERY_FIELDS])
    pairs = parse_qsl(bounded, keep_blank_values=True)
    # Mask markers would otherwise add synthetic punctuation to the ML signal.
    text = path + "".join(k + ("" if k.lower() in SENSITIVE_KEYS or v == "[REDACTED]" else v)
                          for k, v in pairs)
    special = sum(not (char.isalnum() or char.isspace()) for char in text)
    target = path + ("?" + query if query else "")
    return {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "payload_len": len(target.encode("utf-8", errors="replace")),
        "special_char_ratio": special / len(text) if text else 0.0,
        "num_params": len(pairs),
        "path_depth": sum(bool(segment) for segment in path.split("/")),
    }

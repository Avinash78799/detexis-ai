"""Deterministic URL features shared by sensors, workers and training code.

Input is the stored, redacted event representation, never a raw request body.
"""
from .redact import MAX_QUERY_FIELDS, MAX_QUERY_STORED, is_sensitive_key, _parse_query

FEATURE_SCHEMA_VERSION = 1
MAX_PATH_STORED = 2048


def extract_features(path: str, query_redacted: str) -> dict:
    path = path[:MAX_PATH_STORED]
    query = query_redacted[:MAX_QUERY_STORED]
    bounded = "&".join(query.split("&", MAX_QUERY_FIELDS)[:MAX_QUERY_FIELDS])
    pairs = _parse_query(bounded)
    # Mask markers would otherwise add synthetic punctuation to the ML signal.
    text = path + "".join(k + ("" if is_sensitive_key(k) or v == "[REDACTED]" else v)
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

"""Small, explainable heuristics. A match is evidence, not proof of exploitation."""
import ipaddress
import re
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, unquote, urlsplit


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    cwe: str
    owasp: str
    reason: str

    def json(self):
        return asdict(self)


RULES = {
    "sqli_boolean": ("high", "CWE-89", "A05:2025", "SQL boolean tautology"),
    "sqli_union": ("high", "CWE-89", "A05:2025", "UNION SELECT syntax"),
    "sqli_time": ("high", "CWE-89", "A05:2025", "SQL delay function syntax"),
    "xss": ("high", "CWE-79", "A05:2025", "Executable HTML or JavaScript pattern"),
    "path_traversal": ("high", "CWE-22", "A01:2025", "Parent-directory traversal syntax"),
    "command_injection": ("high", "CWE-78", "A05:2025", "Shell separator followed by executable"),
    "ssrf_params": ("high", "CWE-918", "A01:2025", "URL parameter points at nonpublic destination"),
    "scanner_ua": ("low", "CWE-200", "A02:2025", "Known automated scanning client; may be authorized"),
    "sensitive_path": ("medium", "CWE-200", "A02:2025", "Probe for a commonly exposed sensitive file"),
    "login_brute_force": ("high", "CWE-307", "A07:2025", "Repeated failed logins from the same daily IP hash"),
    "honeytoken": ("high", "CWE-200", "A02:2025", "Configured canary path accessed; verify scanner context"),
    "request_flood": ("medium", "CWE-400", "A06:2025", "Request rate exceeds the site's configured threshold"),
}

PATTERNS = {
    "sqli_boolean": re.compile(r"\b(?:or|and)\s+(?:(\d{1,6})\s*=\s*\1\b|'([^']{1,20})'\s*=\s*'\2')", re.I),
    "sqli_union": re.compile(r"\bunion\s+(?:all\s+)?select\b", re.I),
    "sqli_time": re.compile(r"\b(?:sleep|pg_sleep|benchmark)\s*\(\s*\d|\bwaitfor\s+delay\s+'", re.I),
    "xss": re.compile(r"<\s*script\b|<\s*(?:svg|img)\b[^>]{0,300}\bon(?:load|error)\s*=|\bjavascript\s*:", re.I),
    "path_traversal": re.compile(r"\.\.[\\/]"),
    "command_injection": re.compile(r"(?:;|\|\||&&|\$\()\s*(?:id|whoami|cat|curl|wget|bash|sh)\b", re.I),
}
URL_FIELDS = {"url", "uri", "target", "redirect", "callback", "webhook", "dest", "host"}
LOGIN_PATHS = {"/login", "/signin", "/auth/login", "/api/login"}
SENSITIVE_PATHS = {"/.env", "/.git/config", "/wp-config.php", "/etc/passwd", "/backup.sql"}


def private_target(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            return False
        host = (parsed.hostname or "").lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".internal", ".local")) or host == "metadata.google.internal":
            return True
        try:
            return not ipaddress.ip_address(host).is_global
        except ValueError:
            return False  # No outbound DNS requests are made by detection rules.
    except ValueError:
        return False


def evaluate(path, query="", ua="", status=200, *, honeytokens=(), failed_logins=0,
             request_count=0, login_threshold=10, flood_threshold=300):
    path = path[:2048]
    pairs = parse_qsl("&".join(query[:2048].split("&", 50)[:50]), keep_blank_values=True)
    # One query decoding pass; bounded second path decoding catches common encodings.
    text = unquote(path) + " " + " ".join(k + "=" + v for k, v in pairs)
    hits = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
    if any(k.lower() in URL_FIELDS and private_target(v) for k, v in pairs):
        hits.append("ssrf_params")
    if re.search(r"\b(?:sqlmap|nikto|nuclei|masscan|zgrab)\b", ua[:512], re.I):
        hits.append("scanner_ua")
    if path.lower().rstrip("/") in SENSITIVE_PATHS:
        hits.append("sensitive_path")
    if path in honeytokens:
        hits.append("honeytoken")
    if path.rstrip("/").lower() in LOGIN_PATHS and status in {401, 403} and failed_logins >= login_threshold:
        hits.append("login_brute_force")
    if request_count >= flood_threshold:
        hits.append("request_flood")
    return [Finding(name, *RULES[name]) for name in hits]

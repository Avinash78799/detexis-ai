"""Minimal checklist scanner. Runs in a separate credential-free container."""
import re
import time

import dns.resolver

from .safe_fetch import domain_name, fetch


def txt(name, deadline=None):
    resolver = dns.resolver.Resolver()
    remaining = 2 if deadline is None else deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("scan deadline exceeded")
    resolver.timeout, resolver.lifetime = min(1, remaining), min(2, remaining)
    try:
        return [b"".join(row.strings).decode("utf-8", errors="replace") for row in resolver.resolve(name, "TXT")]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return []


def scan(domain, selectors=(), fetcher=fetch, lookup=None):
    domain = domain_name(domain)
    deadline = time.monotonic() + 20
    if lookup is None:
        lookup = lambda name: txt(name, deadline=deadline)
    findings = []

    def check(name, passed, weight, detail):
        findings.append({"check": name, "passed": passed, "weight": weight, "detail": detail})

    root = fetcher(f"https://{domain}/", domain, deadline=deadline)
    headers = {k.lower(): v for k, v in root["headers"]}
    check("tls", bool(root["tls"]), 20, "Validated hostname/certificate and negotiated TLS" if root["tls"] else "No TLS metadata")
    for name, weight in [("strict-transport-security", 10), ("content-security-policy", 10),
                          ("x-content-type-options", 5), ("referrer-policy", 5)]:
        value = headers.get(name, "")
        passed = bool(value)
        if name == "x-content-type-options":
            passed = value.lower() == "nosniff"
        if name == "strict-transport-security":
            passed = bool(re.search(r"(?:^|;)\s*max-age\s*=\s*[1-9]\d*", value, re.I))
        check(name, passed, weight, "Header present with basic syntax check; policy effectiveness requires review")
    check("frame_policy", "frame-ancestors" in headers.get("content-security-policy", "").lower() or headers.get("x-frame-options", "").upper() in {"DENY", "SAMEORIGIN"}, 5, "Frame embedding policy")
    cookies = [v for k, v in root["headers"] if k.lower() == "set-cookie" and re.match(r"(?:session\w*|sid|auth\w*|token)\s*=", v, re.I)]
    safe_cookies = all(all(flag in value.lower() for flag in ("secure", "httponly", "samesite=")) for value in cookies)
    check("session_cookie_flags", safe_cookies if cookies else None, 5, "Only observed session-like cookies; no login was attempted")
    exposed = []
    for path, signature in [("/.env", rb"(?m)^(?:DB_PASSWORD|SECRET_KEY|DATABASE_URL)\s*="),
                             ("/.git/HEAD", rb"^ref: refs/"), ("/backup.sql", rb"(?i)(?:CREATE TABLE|INSERT INTO)")]:
        response = fetcher(f"https://{domain}{path}", domain, deadline=deadline)
        if response["status"] == 200 and re.search(signature, response["body"]):
            exposed.append(path)
    # Never retain or return response bodies or discovered secret values.
    check("exposed_files", not exposed, 25, "Signature found at: " + ", ".join(exposed) if exposed else "No signature in three configured probes")
    for name, record in [("spf", domain), ("dmarc", "_dmarc." + domain)]:
        try:
            values = lookup(record)
            good = any(v.lower().startswith("v=spf1 ") for v in values) if name == "spf" else any(v.lower().startswith("v=dmarc1") and re.search(r"(?:^|;)\s*p=(?:reject|quarantine)(?:;|$)", v, re.I) for v in values)
            check(name, good, 5, "Basic DNS policy presence check; mail delivery was not tested")
        except Exception:
            check(name, None, 5, "DNS lookup unavailable")
    try:
        valid_selectors = [s for s in selectors[:5] if re.fullmatch(r"[a-zA-Z0-9_-]{1,63}", s)]
        dkim = any(any("p=" in value for value in lookup(f"{s}._domainkey.{domain}")) for s in valid_selectors)
        check("dkim", dkim if valid_selectors else None, 5, "Only configured selectors checked; selectors cannot be enumerated reliably")
    except Exception:
        check("dkim", None, 5, "DNS lookup unavailable")
    assessed = sum(f["weight"] for f in findings if f["passed"] is not None)
    earned = sum(f["weight"] for f in findings if f["passed"] is True)
    return {"score": round(100 * earned / assessed) if assessed else None, "assessed_weight": assessed,
            "findings": findings, "tls": root["tls"], "scope": "Limited configuration checklist; not a vulnerability-free guarantee"}

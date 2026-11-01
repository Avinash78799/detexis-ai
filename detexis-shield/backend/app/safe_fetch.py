"""SSRF-safe, pinned-IP HTTP fetching for the isolated scanner process."""
import http.client
import io
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

import dns.resolver

MAX_RESPONSE = 512 * 1024
MAX_BODY = 256 * 1024
BLOCKED_V6 = [ipaddress.ip_network(n) for n in ("64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/32")]


class UnsafeTarget(ValueError):
    pass


def domain_name(value):
    if not isinstance(value, str) or len(value) > 253 or value != value.strip():
        raise UnsafeTarget("invalid domain")
    try:
        host = value.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise UnsafeTarget("invalid domain")
    if "." not in host or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in host.split(".")):
        raise UnsafeTarget("use a DNS domain, not a URL or IP")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise UnsafeTarget("IP literals are not accepted")


def public_ip(value):
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or address.is_reserved or address.is_unspecified:
        return False
    if address.version == 6:
        if address.ipv4_mapped is not None:
            return address.ipv4_mapped.is_global
        if any(address in network for network in BLOCKED_V6):
            return False
    return True


def resolve_public(host):
    resolver = dns.resolver.Resolver()
    resolver.timeout, resolver.lifetime = 1, 3
    values = []
    for kind in ("A", "AAAA"):
        try:
            values.extend(str(answer) for answer in resolver.resolve(host, kind))
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            continue
    if not values or any(not public_ip(value) for value in values):
        raise UnsafeTarget("DNS contains an unavailable or nonpublic destination")
    return values


def validate_url(url, verified_domain):
    parsed = urlsplit(url)
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise UnsafeTarget("invalid port")
    if parsed.scheme not in {"http", "https"} or port not in {80, 443} or parsed.username is not None or parsed.password is not None:
        raise UnsafeTarget("unsupported URL")
    if domain_name(parsed.hostname or "") != verified_domain or parsed.fragment or any(c in url for c in "\r\n\\"):
        raise UnsafeTarget("redirect leaves the verified domain")
    return parsed, port


class _Reader(io.RawIOBase):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def readable(self):
        return True

    def close(self):
        if not self.closed:
            self.owner.files -= 1
            if self.owner.closing and not self.owner.files:
                self.owner.sock.close()
        super().close()

    def readinto(self, buffer):
        owner = self.owner
        owner.check()
        n = owner.sock.recv_into(buffer)
        owner.received += n
        if owner.received > MAX_RESPONSE:
            raise UnsafeTarget("response exceeds transfer cap")
        return n


class _Socket:
    def __init__(self, sock, deadline):
        self.sock, self.deadline, self.received = sock, deadline, 0
        self.files, self.closing = 0, False

    def check(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("scan deadline exceeded")
        self.sock.settimeout(min(2, remaining))

    def sendall(self, data):
        self.check()
        self.sock.sendall(data)

    def makefile(self, *args, **kwargs):
        self.files += 1
        return io.BufferedReader(_Reader(self))

    def close(self):
        self.closing = True
        if not self.files:
            self.sock.close()


def pinned_request(parsed, port, address, deadline):
    # The vetted IP is used for the connection. Host/SNI retain the verified name.
    sock = socket.create_connection((address, port), timeout=min(2, max(.01, deadline - time.monotonic())))
    tls = None
    connection = http.client.HTTPConnection(parsed.hostname, port, timeout=2)
    try:
        if parsed.scheme == "https":
            sock.settimeout(min(2, max(.01, deadline - time.monotonic())))
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
            cert = sock.getpeercert()
            tls = {"version": sock.version(), "expires": cert.get("notAfter")}
        connection.sock = _Socket(sock, deadline)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        host = parsed.hostname + (f":{port}" if port != (443 if parsed.scheme == "https" else 80) else "")
        connection.request("GET", target, headers={"Host": host, "User-Agent": "DetexisShield-VerifiedScanner/1.0",
                            "Accept-Encoding": "identity", "Connection": "close"})
        response = connection.getresponse()
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise UnsafeTarget("body exceeds scan cap")
        return {"status": response.status, "headers": response.getheaders(), "body": body, "tls": tls}
    finally:
        connection.close()
        sock.close()


def fetch(url, verified_domain, *, deadline=None, resolver=None, transport=None):
    deadline = time.monotonic() + 12 if deadline is None else deadline
    resolver = resolve_public if resolver is None else resolver
    transport = pinned_request if transport is None else transport
    verified_domain = domain_name(verified_domain)
    for _ in range(4):
        if time.monotonic() >= deadline:
            raise TimeoutError("scan deadline exceeded")
        parsed, port = validate_url(url, verified_domain)
        addresses = resolver(verified_domain)
        if time.monotonic() >= deadline:
            raise TimeoutError("scan deadline exceeded during DNS resolution")
        # Validate injected resolver outputs too; no mixed public/private RRset allowed.
        if not addresses or any(not public_ip(address) for address in addresses):
            raise UnsafeTarget("nonpublic DNS answer")
        result = transport(parsed, port, addresses[0], deadline)
        if result["status"] not in {301, 302, 303, 307, 308}:
            return result
        location = next((v for k, v in result["headers"] if k.lower() == "location"), None)
        if not location:
            raise UnsafeTarget("redirect has no destination")
        following = urljoin(url, location)
        if parsed.scheme == "https" and urlsplit(following).scheme != "https":
            raise UnsafeTarget("HTTPS downgrade refused")
        url = following
    raise UnsafeTarget("too many redirects")

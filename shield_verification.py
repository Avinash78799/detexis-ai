"""Optional ownership proof for Vercel subdomains, with no sensor dependency."""
import os
from flask import Blueprint

blueprint = Blueprint("shield_verification", __name__)


@blueprint.get("/.well-known/detexis-shield.txt")
def verification():
    token = os.environ.get("SHIELD_VERIFICATION_TOKEN", "")
    if not token.startswith("dxs-verification=") or len(token) > 256 or "\n" in token or "\r" in token:
        return "Not found", 404
    return token, 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}

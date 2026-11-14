"""Usage: python create_site.py example.com  -> prints the API key ONCE."""
import sys
import secrets
sys.path.insert(0, ".")
from app.auth import new_api_key
from app.db import SessionLocal
from app.models import ApiKey, Site
from app.safe_fetch import domain_name

domain = domain_name(sys.argv[1])
raw, prefix, key_hash = new_api_key()
with SessionLocal() as db:
    site = Site(domain=domain)
    db.add(site)
    db.flush()
    db.add(ApiKey(site_id=site.id, prefix=prefix, key_hash=key_hash))
    db.commit()
    print(f"site_id={site.id}\nAPI key (save it, shown once): {raw}\nSite salt (save it on the monitored app): {secrets.token_urlsafe(32)}")

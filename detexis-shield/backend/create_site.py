"""Usage: python create_site.py example.com  -> prints the API key ONCE."""
import sys
sys.path.insert(0, ".")
from app.auth import new_api_key
from app.db import Base, SessionLocal, engine
from app.models import ApiKey, Site

Base.metadata.create_all(engine)
domain = sys.argv[1]
raw, prefix, key_hash = new_api_key()
with SessionLocal() as db:
    site = Site(domain=domain)
    db.add(site)
    db.flush()
    db.add(ApiKey(site_id=site.id, prefix=prefix, key_hash=key_hash))
    db.commit()
    print(f"site_id={site.id}\nAPI key (save it, shown once): {raw}")

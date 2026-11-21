import os
from fastapi import FastAPI
from detexis_shield import ShieldMiddleware

app = FastAPI()
app.add_middleware(
    ShieldMiddleware,
    api_url=os.getenv("SHIELD_URL", "http://localhost:8000"),
    api_key=os.environ["SHIELD_API_KEY"],
    site_salt=os.getenv("SHIELD_SALT", "demo-salt"),
)


@app.get("/")
def home():
    return {"hello": "world"}


@app.get("/search")
def search(q: str = ""):
    return {"q": q}


@app.get("/.env")
def fake_env():  # A probe signal; legitimate security scanners can also hit this.
    return {"detail": "not found"}

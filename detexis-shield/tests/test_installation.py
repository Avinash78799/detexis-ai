from html.parser import HTMLParser
from types import SimpleNamespace

from fastapi.testclient import TestClient
from app.main import app


class Examples(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.snippets = {}

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.current = dict(attrs).get("data-python")
            if self.current:
                self.snippets[self.current] = ""

    def handle_endtag(self, tag):
        if tag == "pre":
            self.current = None

    def handle_data(self, data):
        if self.current:
            self.snippets[self.current] += data


def test_published_installation_examples_run_and_emit_redacted_events(monkeypatch):
    page = TestClient(app).get("/app/install")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    examples = Examples()
    examples.feed(page.text)
    assert set(examples.snippets) == {"fastapi", "flask"}
    for key, value in {"SHIELD_URL": "https://shield.example", "SHIELD_API_KEY": "dxs_test_synthetic",
                       "SHIELD_SALT": "synthetic-stable-site-salt"}.items():
        monkeypatch.setenv(key, value)
    events, configurations = [], []

    def sender(api_url, api_key, **kwargs):
        configurations.append((api_url, api_key))
        return SimpleNamespace(submit=events.append)

    monkeypatch.setattr("detexis_shield.middleware.ShieldClient", sender)
    for framework, snippet in examples.snippets.items():
        namespace = {"__name__": "__main__"}
        exec(compile(snippet, f"install-{framework}.py", "exec"), namespace)
        example = namespace["app"]
        if framework == "fastapi":
            with TestClient(example) as browser:
                response = browser.get("/?password=never-send-this-value")
        else:
            with example.test_client() as browser:
                response = browser.get("/?password=never-send-this-value")
                response.close()
        assert response.status_code == 200
        assert events[-1]["path"] == "/"
        assert events[-1]["status"] == 200
        assert "never-send-this-value" not in str(events[-1])
    assert len(events) == 2
    assert configurations == [("https://shield.example", "dxs_test_synthetic")] * 2


def test_public_data_guide_renders_without_an_account():
    page = TestClient(app).get("/app/data")
    assert page.status_code == 200
    assert "Data handling" in page.text
    assert "self-service deletion/export" in page.text
    assert page.headers["cache-control"] == "no-store"

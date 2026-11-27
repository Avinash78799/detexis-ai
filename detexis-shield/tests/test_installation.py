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
    assert "SDK 0.1.3" in page.text
    assert "@eb28bffa48d0b0499b5bc692302b737e229309a2#subdirectory=" in page.text

    examples = Examples()
    examples.feed(page.text)
    assert set(examples.snippets) == {"fastapi", "flask"}
    for key, value in {"SHIELD_URL": "https://shield.example", "SHIELD_API_KEY": "dxs_test_synthetic",
                       "SHIELD_SALT": "synthetic-stable-site-salt"}.items():
        monkeypatch.setenv(key, value)
    events, configurations = [], []

    def sender(api_url, api_key, **kwargs):
        configurations.append((api_url, api_key, kwargs["outage_retry_window"]))
        return SimpleNamespace(submit=events.append)

    monkeypatch.setattr("detexis_shield.middleware.ShieldClient", sender)
    for framework, snippet in examples.snippets.items():
        namespace = {"__name__": "__main__"}
        exec(compile(snippet, f"install-{framework}.py", "exec"), namespace)
        example = namespace["app"]
        if framework == "fastapi":
            with TestClient(example) as browser:
                response = browser.get("/?password=never-send-this-value&credentials%5Bpassword%5D=nested-private-value")
        else:
            with example.test_client() as browser:
                response = browser.get("/?password=never-send-this-value&credentials%5Bpassword%5D=nested-private-value")
                response.close()
        assert response.status_code == 200
        assert events[-1]["path"] == "/"
        assert events[-1]["status"] == 200
        assert "never-send-this-value" not in str(events[-1])
        assert "nested-private-value" not in str(events[-1])
    assert len(events) == 2
    assert configurations == [("https://shield.example", "dxs_test_synthetic", 30)] * 2


def test_public_data_guide_renders_without_an_account():
    page = TestClient(app).get("/app/data")
    assert page.status_code == 200
    assert "Data handling" in page.text
    assert 'href="/app#delete-account"' in page.text
    assert "current password and an explicit confirmation" in page.text
    assert "Export requests and removal from operational logs require the deployment operator" in page.text
    assert page.headers["cache-control"] == "no-store"


def test_public_data_guide_reports_recent_retention_and_stays_available_when_offline(isolated_redis, monkeypatch):
    from redis.exceptions import ConnectionError
    from app.maintenance_health import RETENTION_STATUS_KEY, record_success

    with TestClient(app) as client:
        record_success(isolated_redis, 7)
        page = client.get("/app/data")
        assert "latest successful maintenance cycle used a 7-day telemetry retention window" in page.text
        isolated_redis.expire(RETENTION_STATUS_KEY, -1)
        assert "Shield has no recent retention report" in client.get("/app/data").text

        def offline(*_args):
            raise ConnectionError("Synthetic Redis outage")

        monkeypatch.setattr(isolated_redis, "get", offline)
        page = client.get("/app/data")
        assert page.status_code == 200
        assert "Shield has no recent retention report" in page.text


def test_operator_contact_is_optional_validated_and_visible_without_signin(monkeypatch):
    monkeypatch.setenv("SHIELD_SUPPORT_EMAIL", "shield.org787@gmail.com")
    with TestClient(app) as client:
        for path in ["/app", "/app/data"]:
            assert 'href="mailto:shield.org787@gmail.com"' in client.get(path).text
        for address in ["", "bad@example.test?subject=injected", 'x@example.test\" onclick="bad()']:
            monkeypatch.setenv("SHIELD_SUPPORT_EMAIL", address)
            page = client.get("/app/data")
            assert 'href="mailto:' not in page.text
            assert "support contact has not been configured" in page.text

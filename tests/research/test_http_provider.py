from agent.research.discovery.http_provider import fetch_provider_json


class FakeResponse:
    def __init__(self, status_code: int, text: str = "{}"):
        self.status_code = status_code
        self.headers = {}
        self.text = text

    def raise_for_status(self):
        return None


def test_fetch_provider_json_clamps_negative_backoff_before_sleep(monkeypatch):
    responses = iter([FakeResponse(500), FakeResponse(200, '{"ok": true}')])
    sleeps = []

    def fake_get(url, params=None, headers=None, timeout=None):
        return next(responses)

    monkeypatch.setattr("agent.research.discovery.http_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)

    payload = fetch_provider_json(
        "https://example.test/provider",
        params={"q": "test"},
        headers={},
        timeout=1,
        provider_name="TestProvider",
        max_retries=1,
        base_backoff_seconds=-2,
        max_backoff_seconds=-1,
    )

    assert payload == '{"ok": true}'
    assert sleeps == [0.0]

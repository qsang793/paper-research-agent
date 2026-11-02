from agent.citation_validator import validate_citation_sources


def test_validate_citation_sources_annotates_existing_source_shape(monkeypatch):
    monkeypatch.setattr("agent.citation_validator.is_alive", lambda url, timeout=5.0: "ok" in url)
    sources = [
        {"id": "source_0", "title": "OK", "url": "https://ok.example", "alive_status": "unchecked"},
        {"id": "source_1", "title": "Bad", "url": "https://bad.example", "alive_status": "unchecked"},
    ]

    result = validate_citation_sources("See [OK](https://ok.example)", sources, max_workers=1)

    assert result["total"] == 2
    assert result["ok"] == 1
    assert result["dead"] == ["https://bad.example"]
    assert result["sources"][0]["alive_status"] == "ok"
    assert result["sources"][1]["alive_status"] == "dead"

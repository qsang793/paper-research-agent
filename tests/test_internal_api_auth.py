from fastapi.testclient import TestClient

from api.main import app
from api.main import get_allowed_origins


def test_production_api_rejects_missing_internal_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BACKEND_INTERNAL_TOKEN", "unit-test-placeholder")

    response = TestClient(app).get("/api/features")

    assert response.status_code == 401


def test_production_api_rejects_missing_internal_token_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("BACKEND_INTERNAL_TOKEN", raising=False)

    response = TestClient(app).get("/api/features")

    assert response.status_code == 503


def test_production_api_accepts_matching_internal_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BACKEND_INTERNAL_TOKEN", "unit-test-placeholder")

    response = TestClient(app).get(
        "/api/features",
        headers={"X-Internal-Token": "unit-test-placeholder"},
    )

    assert response.status_code == 200


def test_health_remains_public_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BACKEND_INTERNAL_TOKEN", "unit-test-placeholder")

    response = TestClient(app).get("/health")

    assert response.status_code == 200


def test_legacy_password_auth_routes_are_not_exposed(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("BACKEND_INTERNAL_TOKEN", raising=False)

    response = TestClient(app).get("/api/auth/signup")

    assert response.status_code == 404


def test_production_cors_uses_only_configured_origins(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://research.example.com")

    assert get_allowed_origins() == ["https://research.example.com"]

from fastapi.testclient import TestClient

from agent.memory.store import InMemoryMemoryStore
from api.main import app
from api.routes import chat as chat_route
from api.routes.chat import sessions


def _reset_memory_state(monkeypatch):
    monkeypatch.setattr(chat_route, "memory_store", None)
    monkeypatch.setattr(chat_route, "memory_store_backend", "disabled")
    monkeypatch.setattr(chat_route, "memory_store_error", None)
    monkeypatch.delenv("MEMORY_DATABASE_URL", raising=False)
    sessions.clear()


def test_memory_features_endpoint_reports_flags(monkeypatch):
    _reset_memory_state(monkeypatch)
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("SESSION_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("LONG_TERM_MEMORY_ENABLED", "false")
    monkeypatch.setenv("RESEARCH_MEMORY_ENABLED", "false")

    client = TestClient(app)
    response = client.get("/api/memory/features")

    assert response.status_code == 200
    assert response.json() == {
        "persistent_transcript_enabled": True,
        "session_summary_enabled": False,
        "long_term_memory_enabled": False,
        "research_memory_enabled": False,
        "memory_store_backend": "inmemory",
        "memory_store_error": None,
    }


def test_memory_session_delete_removes_local_and_persistent_state(monkeypatch):
    _reset_memory_state(monkeypatch)
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    store = InMemoryMemoryStore()
    store.append_message(session_id="test-session", role="user", content="remember LoRA")
    monkeypatch.setattr(chat_route, "memory_store", store)
    sessions["test-session"] = object()

    client = TestClient(app)
    response = client.delete("/api/memory/session/test-session")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "test-session",
        "deleted_local_session": True,
        "deleted_persistent_session": True,
    }
    assert "test-session" not in sessions
    assert store.get_recent_messages("test-session", limit=5) == []


def test_memory_session_delete_returns_404_when_missing(monkeypatch):
    _reset_memory_state(monkeypatch)

    client = TestClient(app)
    response = client.delete("/api/memory/session/missing-session")

    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found"}


def test_memory_session_delete_returns_503_when_persistent_store_unavailable(monkeypatch):
    _reset_memory_state(monkeypatch)
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://memory.example/test")

    class FailingPostgresMemoryStore:
        def __init__(self, database_url):
            self.database_url = database_url

        def setup(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(chat_route, "PostgresMemoryStore", FailingPostgresMemoryStore)

    client = TestClient(app)
    response = client.delete("/api/memory/session/maybe-persisted-session")

    assert response.status_code == 503
    assert response.json() == {"detail": "Memory deletion failed"}


def test_memory_session_delete_keeps_local_state_when_persistent_store_unavailable(monkeypatch):
    _reset_memory_state(monkeypatch)
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://memory.example/test")
    sessions["maybe-persisted-session"] = object()

    class FailingPostgresMemoryStore:
        def __init__(self, database_url):
            self.database_url = database_url

        def setup(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(chat_route, "PostgresMemoryStore", FailingPostgresMemoryStore)

    client = TestClient(app)
    response = client.delete("/api/memory/session/maybe-persisted-session")

    assert response.status_code == 503
    assert "maybe-persisted-session" in sessions


def test_legacy_session_delete_returns_503_when_persistent_store_unavailable(monkeypatch):
    _reset_memory_state(monkeypatch)
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://memory.example/test")

    class FailingPostgresMemoryStore:
        def __init__(self, database_url):
            self.database_url = database_url

        def setup(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(chat_route, "PostgresMemoryStore", FailingPostgresMemoryStore)

    client = TestClient(app)
    response = client.delete("/api/session/maybe-persisted-session")

    assert response.status_code == 503
    assert response.json() == {"detail": "Memory deletion failed"}


def test_memory_features_reports_unavailable_backend_when_store_init_fails(monkeypatch):
    _reset_memory_state(monkeypatch)
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://memory.example/test")

    class FailingPostgresMemoryStore:
        def __init__(self, database_url):
            self.database_url = database_url

        def setup(self):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(chat_route, "PostgresMemoryStore", FailingPostgresMemoryStore)

    client = TestClient(app)
    response = client.get("/api/memory/features")

    assert response.status_code == 200
    body = response.json()
    assert body["memory_store_backend"] == "unavailable"
    assert "database unavailable" in body["memory_store_error"]


def test_memory_features_reports_postgres_backend_when_store_initializes(monkeypatch):
    _reset_memory_state(monkeypatch)
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://memory.example/test")

    class WorkingPostgresMemoryStore:
        def __init__(self, database_url):
            self.database_url = database_url

        def setup(self):
            return None

    monkeypatch.setattr(chat_route, "PostgresMemoryStore", WorkingPostgresMemoryStore)

    client = TestClient(app)
    response = client.get("/api/memory/features")

    body = response.json()
    assert body["memory_store_backend"] == "postgres"
    assert body["memory_store_error"] is None

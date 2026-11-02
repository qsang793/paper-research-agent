from agent.memory.config import MemoryConfig


def test_memory_config_defaults_are_safe(monkeypatch):
    for key in [
        "PERSISTENT_TRANSCRIPT_ENABLED",
        "SESSION_SUMMARY_ENABLED",
        "LONG_TERM_MEMORY_ENABLED",
        "RESEARCH_MEMORY_ENABLED",
        "CONVERSATIONAL_MEMORY_ENABLED",
        "MEMORY_DATABASE_URL",
        "MEMORY_RECENT_MESSAGE_LIMIT",
        "MEMORY_MAX_CONTEXT_CHARS",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = MemoryConfig.from_env()

    assert config.persistent_transcript_enabled is False
    assert config.session_summary_enabled is False
    assert config.long_term_memory_enabled is False
    assert config.research_memory_enabled is False
    assert config.conversational_memory_enabled is False
    assert config.database_url is None
    assert config.recent_message_limit == 8
    assert config.max_context_chars == 12000


def test_memory_config_parses_enabled_flags(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("SESSION_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("LONG_TERM_MEMORY_ENABLED", "yes")
    monkeypatch.setenv("RESEARCH_MEMORY_ENABLED", "on")
    monkeypatch.setenv("CONVERSATIONAL_MEMORY_ENABLED", "true")
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://user:pass@localhost:5432/research")
    monkeypatch.setenv("MEMORY_RECENT_MESSAGE_LIMIT", "6")
    monkeypatch.setenv("MEMORY_MAX_CONTEXT_CHARS", "9000")

    config = MemoryConfig.from_env()

    assert config.persistent_transcript_enabled is True
    assert config.session_summary_enabled is True
    assert config.long_term_memory_enabled is True
    assert config.research_memory_enabled is True
    assert config.conversational_memory_enabled is True
    assert config.database_url == "postgresql://user:pass@localhost:5432/research"
    assert config.recent_message_limit == 6
    assert config.max_context_chars == 9000

from agent.memory.store import InMemoryMemoryStore
from agent.memory.writer import MemoryWriter


def test_memory_writer_stores_research_preference():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    source_message = store.append_message(
        session_id="s1",
        role="user",
        content="I prefer comparison tables.",
    )
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User prefers answers with paper comparison tables.",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
    )

    assert item is not None
    results = store.search_memory_items("comparison tables", session_id="s1", user_id="u1", limit=5)
    assert [result.id for result in results] == [item.id]


def test_user_scoped_memory_is_available_across_sessions():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    source_message = store.append_message(
        session_id="s1",
        role="user",
        content="Please remember my answer preference.",
    )
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User prefers concise technical answers.",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
        scope="user",
    )
    store.ensure_session("s2", user_id="u1")

    assert item is not None
    assert item.scope == "user"
    assert item.session_id is None
    results = store.search_memory_items(
        "concise technical answers",
        session_id="s2",
        user_id="u1",
        limit=5,
    )
    assert [result.id for result in results] == [item.id]


def test_user_scoped_memory_is_not_visible_to_another_user():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    source_message = store.append_message("s1", "user", "Remember my preference")
    item = MemoryWriter(store).write_candidate(
        text="User prefers concise technical answers.",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
        scope="user",
    )
    store.ensure_session("other", user_id="u2")

    assert item is not None
    assert store.search_memory_items(
        "concise technical answers",
        session_id="other",
        user_id="u2",
        limit=5,
    ) == []


def test_user_scoped_memory_deduplicates_exact_normalized_text():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    source_message = store.append_message("s1", "user", "Remember my preference")
    writer = MemoryWriter(store)

    first = writer.write_candidate(
        text="User prefers concise technical answers.",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
        scope="user",
    )
    second = writer.write_candidate(
        text="  User   prefers concise technical answers.  ",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
        scope="user",
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id


def test_memory_writer_skips_sensitive_candidate():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    source_message = store.append_message(
        session_id="s1",
        role="user",
        content="Do not retain this.",
    )
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User password is hunter2.",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
    )

    assert item is None
    assert store.search_memory_items("password", session_id="s1", user_id="u1", limit=5) == []


def test_memory_writer_skips_sensitive_candidate_with_punctuation():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    source_message = store.append_message(
        session_id="s1",
        role="user",
        content="Do not retain this.",
    )
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User pasted an API-key for OpenAlex.",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
    )

    assert item is None
    assert store.search_memory_items("OpenAlex", session_id="s1", user_id="u1", limit=5) == []


def test_memory_writer_does_not_skip_research_terms_containing_sensitive_substrings():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    source_message = store.append_message(
        session_id="s1",
        role="user",
        content="I study tokenization.",
    )
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User prefers papers about tokenization methods.",
        session_id="s1",
        user_id="u1",
        source_message_id=source_message.id,
    )

    assert item is not None
    results = store.search_memory_items("tokenization", session_id="s1", user_id="u1", limit=5)
    assert [result.id for result in results] == [item.id]


def test_memory_writer_skips_session_candidate_for_different_user():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User prefers answers with paper comparison tables.",
        session_id="s1",
        user_id="u2",
        source_message_id=None,
    )

    assert item is None
    assert store.search_memory_items("comparison tables", session_id="s1", user_id="u1", limit=5) == []


def test_memory_writer_skips_user_candidate_without_user_id():
    store = InMemoryMemoryStore()
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User prefers LoRA papers.",
        session_id=None,
        user_id=None,
        source_message_id=None,
        scope="user",
    )

    assert item is None

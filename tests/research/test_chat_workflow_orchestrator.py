from api.chat_orchestrator import ResearchChatWorkflow


class _Memory:
    def __init__(self):
        self.add_calls = []

    def add(self, query, answer, citations):
        self.add_calls.append((query, answer, citations))


def test_research_chat_workflow_keeps_memory_out_of_retrieval_query():
    memory = _Memory()
    preview_calls = []

    def inject(query, memory_obj):
        assert memory_obj is memory
        return f"{query}\nSHOULD_NOT_ENTER_RETRIEVAL", "conversation context"

    def run_preview(
        query,
        *,
        top_k,
        providers,
        generate,
        question,
        memory_context,
    ):
        preview_calls.append(
            (query, top_k, providers, generate, question, memory_context)
        )
        return {
            "answer": "research answer",
            "citations": [
                {"title": "Paper", "url": "https://example.test/paper"},
                {"title": "No URL", "url": ""},
            ],
            "answerability": {"can_answer": True},
        }

    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=inject,
        run_preview_fn=run_preview,
    )

    response = workflow.run_chat_response(
        "What about it?",
        session_id="s1",
        top_k=3,
        memory=memory,
        start_time=0,
        research_query="GraphRAG limitations",
        memory_context="conversation context",
        now_fn=lambda: 0.2,
    )

    assert response.answer == "research answer"
    assert preview_calls == [
        (
            "GraphRAG limitations",
            3,
            None,
            True,
            "What about it?",
            "conversation context",
        )
    ]
    assert "SHOULD_NOT_ENTER_RETRIEVAL" not in preview_calls[0][0]
    assert memory.add_calls == [
        ("What about it?", "research answer", ["https://example.test/paper"])
    ]


def test_research_chat_workflow_builds_legacy_context_without_using_enhanced_query():
    memory = _Memory()

    def inject(query, memory_obj):
        assert memory_obj is memory
        return f"{query}\nlegacy enhanced blob", "legacy context only"

    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=inject,
        run_preview_fn=lambda *args, **kwargs: {},
    )

    context = workflow.build_memory_context(
        "question",
        session_id="s1",
        user_id=None,
        memory=memory,
    )

    assert context == "legacy context only"


def test_research_chat_workflow_resolves_default_source_event_adapter_at_construction(monkeypatch):
    memory = _Memory()

    def inject(query, memory_obj):
        return query, ""

    def run_preview(query, *, top_k, providers, generate, question, memory_context):
        return {
            "answer": "stream answer",
            "citations": [{"title": "Original", "url": "https://example.test/original"}],
            "answerability": {"can_answer": True},
        }

    monkeypatch.setattr(
        "api.chat_orchestrator.research_preview_to_source_events",
        lambda preview: [{"url": "https://example.test/patched"}],
    )

    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=inject,
        run_preview_fn=run_preview,
    )
    workflow.run_stream_preview(
        "question",
        session_id="s1",
        top_k=3,
        memory=memory,
        research_query="clean question",
        memory_context="context",
    )

    assert memory.add_calls == [
        ("question", "stream answer", ["https://example.test/patched"])
    ]


def test_research_chat_workflow_skips_legacy_memory_for_no_answer_preview():
    memory = _Memory()

    def inject(query, memory_obj):
        return query, ""

    def run_preview(query, *, top_k, providers, generate, question, memory_context):
        return {
            "answer": "Khong tim thay paper phu hop cho cau hoi nay.",
            "citations": [],
            "answerability": {"can_answer": False},
        }

    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=inject,
        run_preview_fn=run_preview,
    )
    response = workflow.run_chat_response(
        "question",
        session_id="s1",
        top_k=3,
        memory=memory,
        start_time=0,
        research_query="question",
        memory_context="",
        now_fn=lambda: 0.2,
    )

    assert response.answer == "Khong tim thay paper phu hop cho cau hoi nay."
    assert memory.add_calls == []

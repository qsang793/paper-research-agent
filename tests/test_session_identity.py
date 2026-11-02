from api.models import ChatRequest


def test_chat_request_accepts_session_id():
    request = ChatRequest(
        query="What is RAG?",
        session_id="chat-abc",
        mode="auto",
        top_k=6,
    )

    assert request.session_id == "chat-abc"

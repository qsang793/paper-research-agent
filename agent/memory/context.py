from __future__ import annotations

from typing import Optional

from agent.memory.conversation import ConversationMemory


def inject_memory_context(query: str, memory: Optional[ConversationMemory]) -> tuple[str, str]:
    """
    Inject relevant previous context into a query.

    Args:
        query: Original user query.
        memory: Conversation memory instance, when available.

    Returns:
        Tuple of (enhanced_query, memory_context_string).
    """
    if not memory:
        return query, ""

    # Recent turns preserve continuity; similar turns recover older relevant context.
    recent_entries = memory.get_recent(n=5)
    similar_entries = memory.search_similar(query, top_k=2)

    seen_queries = set()
    all_entries = []

    for entry in recent_entries:
        if entry.query not in seen_queries:
            all_entries.append(entry)
            seen_queries.add(entry.query)

    for entry in similar_entries:
        if entry.query not in seen_queries:
            all_entries.append(entry)
            seen_queries.add(entry.query)

    if not all_entries:
        return query, ""

    context_parts = [
        f"Previous Q: {entry.query}\nPrevious A: {entry.answer[:300]}..."
        for entry in all_entries
    ]
    context = "\n\n".join(context_parts)
    memory_context = f"[Previous context for reference:]\n{context}"

    return f"{query}\n\n{memory_context}", memory_context

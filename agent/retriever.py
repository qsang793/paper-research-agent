from typing import Dict, Iterable, List, Tuple


def rrf_merge(ranked_lists: Iterable[Iterable[Tuple[str, float]]], k: int = 60) -> List[Tuple[str, float]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion (RRF).

    Each list is an iterable of (doc_id, score) in ranked order (best first).
    Returns a list of (doc_id, fused_score) sorted descending by fused_score.
    """
    fused: Dict[str, float] = {}
    for lst in ranked_lists:
        for rank, (doc_id, _score) in enumerate(lst, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)


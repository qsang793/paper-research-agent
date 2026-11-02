import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.generator import generate_answer
from agent.citation_validator import validate_citations

# Global caches for models and clients
_EMBED_MODEL_CACHE: Dict[str, SentenceTransformer] = {}
_CHROMA_CLIENT_CACHE: Dict[str, chromadb.PersistentClient] = {}


def get_embed_model(embed_model: str) -> SentenceTransformer:
    """Get cached embedding model."""
    if embed_model not in _EMBED_MODEL_CACHE:
        _EMBED_MODEL_CACHE[embed_model] = SentenceTransformer(embed_model)
    return _EMBED_MODEL_CACHE[embed_model]


def get_chroma_client(chroma_path: str) -> chromadb.PersistentClient:
    """Get cached ChromaDB client."""
    if chroma_path not in _CHROMA_CLIENT_CACHE:
        _CHROMA_CLIENT_CACHE[chroma_path] = chromadb.PersistentClient(
            path=chroma_path, settings=Settings(anonymized_telemetry=False)
        )
    return _CHROMA_CLIENT_CACHE[chroma_path]


TEST_QUESTIONS = [
    "Tóm tắt các tiến triển RAG đáng chú ý 2024–2025 theo arXiv",
    "Các kỹ thuật RAG mới năm 2025",
    "Sự khác nhau giữa RAG và fine-tune cho cập nhật tri thức",
    "Graph-RAG so với RAG chuẩn: ưu và nhược điểm",
    "Hybrid search (dense+BM25) cho RAG: lợi ích và thách thức",
]

THRESHOLDS = {
    "min_citations_ok": 2,
    "retrieve_latency_ms": 2000,  # 2s cho retrieve
    "generate_latency_ms": 60000,  # 60s cho Ollama generate (local)
    "total_latency_ms": 60000,  # 60s tổng cho Ollama local
    "p95_latency_ms": 60000,  # Alias for backward compatibility
    "must_say_insufficient_if_no_context": True,
}


def run_answer_pipeline(chroma_path: str, embed_model: str, question: str, k: int = 6) -> Dict:
    t0 = time.perf_counter()
    client = get_chroma_client(chroma_path)
    col = client.get_or_create_collection("knowledge_base")
    model = get_embed_model(embed_model)
    q_emb = model.encode([question], convert_to_numpy=True).tolist()[0]
    res = col.query(query_embeddings=[q_emb], n_results=k, include=["documents", "metadatas", "distances"])
    docs: List[str] = (res.get("documents") or [[]])[0]
    metas: List[dict] = (res.get("metadatas") or [[]])[0]
    snippets = [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
    retrieve_ms = int((time.perf_counter() - t0) * 1000)
    t1 = time.perf_counter()
    answer = generate_answer(question, snippets)
    gen_ms = int((time.perf_counter() - t1) * 1000)
    total_ms = retrieve_ms + gen_ms
    snippet_urls = [(s.get("metadata") or {}).get("source_url") or "" for s in snippets]
    val = validate_citations(answer, snippet_urls)
    return {
        "question": question,
        "answer": answer,
        "retrieve_ms": retrieve_ms,
        "generate_ms": gen_ms,
        "total_ms": total_ms,
        "citations_ok": val["ok"],
        "citations_total": val["total"],
        "citations_dead": val["dead"],
        "snippets_count": len(snippets),
    }


def check_pass(result: Dict) -> Tuple[bool, List[str]]:
    reasons = []
    passed = True
    if result["citations_ok"] < THRESHOLDS["min_citations_ok"]:
        passed = False
        reasons.append(f"citations_ok={result['citations_ok']} < {THRESHOLDS['min_citations_ok']}")
    if result["retrieve_ms"] > THRESHOLDS["retrieve_latency_ms"]:
        passed = False
        reasons.append(f"retrieve_latency={result['retrieve_ms']}ms > {THRESHOLDS['retrieve_latency_ms']}ms")
    if result["generate_ms"] > THRESHOLDS["generate_latency_ms"]:
        passed = False
        reasons.append(f"generate_latency={result['generate_ms']}ms > {THRESHOLDS['generate_latency_ms']}ms")
    if result["total_ms"] > THRESHOLDS["total_latency_ms"]:
        passed = False
        reasons.append(f"total_latency={result['total_ms']}ms > {THRESHOLDS['total_latency_ms']}ms")
    if result["snippets_count"] == 0:
        if THRESHOLDS["must_say_insufficient_if_no_context"]:
            if "chưa đủ nguồn" not in result["answer"].lower() and "insufficient" not in result["answer"].lower():
                passed = False
                reasons.append("no context but answer didn't say 'insufficient'")
    return passed, reasons


def main():
    chroma_path = os.getenv("CHROMA_PATH", "./chroma")
    embed_model = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    k = int(os.getenv("TOP_K", "6"))
    print("=" * 80)
    print("Sanity Tests for MVP")
    print("=" * 80)
    print(f"Chroma: {chroma_path}")
    print(f"Embed model: {embed_model}")
    print(f"Top-k: {k}")
    print(f"Questions: {len(TEST_QUESTIONS)}")
    print()
    results: List[Dict] = []
    for q in TEST_QUESTIONS:
        print(f"Running: {q[:60]}...")
        try:
            r = run_answer_pipeline(chroma_path, embed_model, q, k)
            passed, reasons = check_pass(r)
            r["passed"] = passed
            r["reasons"] = reasons
            results.append(r)
            status = "PASS" if passed else "FAIL"
            print(f"  {status} | Total: {r['total_ms']}ms (Retrieve: {r['retrieve_ms']}ms, Generate: {r['generate_ms']}ms) | citations: {r['citations_ok']}/{r['citations_total']}")
            if reasons:
                for reason in reasons:
                    print(f"    - {reason}")
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append({"question": q, "passed": False, "error": str(exc)})
        print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    passed_count = sum(1 for r in results if r.get("passed") is True)
    total_count = len(results)
    latencies = [r.get("total_ms", 0) for r in results if "total_ms" in r]
    p95_ms = int(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0)
    print(f"Passed: {passed_count}/{total_count}")
    print(f"P95 latency: {p95_ms}ms (threshold: {THRESHOLDS['p95_latency_ms']}ms)")
    print()
    print("Details:")
    print(f"{'Question':<50} {'Status':<6} {'Time(ms)':<10} {'Citations':<15}")
    print("-" * 80)
    for r in results:
        q_short = (r.get("question", "?")[:47] + "...") if len(r.get("question", "")) > 50 else r.get("question", "?")
        status = "PASS" if r.get("passed") else "FAIL"
        t_ms = r.get("total_ms", 0)
        cit = f"{r.get('citations_ok', 0)}/{r.get('citations_total', 0)}"
        print(f"{q_short:<50} {status:<6} {t_ms:<10} {cit:<15}")
    print("=" * 80)
    if passed_count == total_count and p95_ms <= THRESHOLDS["p95_latency_ms"]:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed or P95 exceeded threshold")
        return 1


if __name__ == "__main__":
    sys.exit(main())


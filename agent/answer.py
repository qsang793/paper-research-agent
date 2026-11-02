import argparse
import os
from typing import List

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .generator import generate_answer
from .citation_validator import validate_citations


def main():
    parser = argparse.ArgumentParser(description="Answer a question using top-k context from Chroma + Ollama")
    parser.add_argument("--chroma", required=True, help="Chroma persistence directory path")
    parser.add_argument("--q", required=True, help="User question")
    parser.add_argument("--k", type=int, default=int(os.getenv("TOP_K", "6")))
    parser.add_argument("--collection", default="knowledge_base")
    parser.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=args.chroma, settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name=args.collection)

    model = SentenceTransformer(args.embed_model)
    q_emb = model.encode([args.q], convert_to_numpy=True).tolist()[0]

    res = collection.query(query_embeddings=[q_emb], n_results=args.k, include=["documents", "metadatas", "distances"])

    docs: List[str] = (res.get("documents") or [[]])[0]
    metas: List[dict] = (res.get("metadatas") or [[]])[0]
    snippets = []
    for doc, md in zip(docs, metas):
        snippets.append({"text": doc, "metadata": md})

    answer = generate_answer(args.q, snippets)
    # Collect snippet URLs for validation
    snippet_urls = []
    for s in snippets:
        md = s.get("metadata") or {}
        u = md.get("source_url") or ""
        if u:
            snippet_urls.append(u)
    val = validate_citations(answer, snippet_urls)
    print("\n=== Answer ===\n")
    print(answer)
    print("\n=== Citations ===")
    print(f"valid {val['ok']} / total {val['total']}")
    if val["dead"]:
        print("dead:")
        for u in val["dead"]:
            print(f" - {u}")


if __name__ == "__main__":
    main()



import argparse
import os
from typing import List

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


def main():
    parser = argparse.ArgumentParser(description="Query Chroma collection and print top-k results")
    parser.add_argument("--chroma", required=True, help="Chroma persistence directory path")
    parser.add_argument("--q", required=True, help="User query")
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
    dists: List[float] = (res.get("distances") or [[]])[0]

    for i, (doc, md, dist) in enumerate(zip(docs, metas, dists), start=1):
        title = (md or {}).get("title") or "(no title)"
        url = (md or {}).get("source_url") or ""
        print(f"{i}. score={1.0 - dist:.4f} | {title}\n   {url}")


if __name__ == "__main__":
    main()



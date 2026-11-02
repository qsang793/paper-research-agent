import argparse
import glob
import json
import os
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


def chunk_list(items: List[str], batch_size: int) -> List[List[str]]:
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def _sanitize_metadata(md: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for k, v in (md or {}).items():
        if v is None:
            # drop None to satisfy Chroma's primitive requirement
            continue
        if isinstance(v, (str, int, float, bool)):
            sanitized[k] = v
        elif isinstance(v, list):
            try:
                # join list of primitives into comma-separated string
                sanitized[k] = ", ".join(map(str, v))
            except Exception:
                sanitized[k] = str(v)
        elif isinstance(v, dict):
            try:
                sanitized[k] = json.dumps(v, ensure_ascii=False)
            except Exception:
                sanitized[k] = str(v)
        else:
            sanitized[k] = str(v)
    return sanitized


def main():
    parser = argparse.ArgumentParser(description="Index cleaned JSON into Chroma with embeddings")
    parser.add_argument("--input", required=True, help="Directory of cleaned JSON files")
    parser.add_argument("--chroma", required=True, help="Chroma persistence directory path")
    parser.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    parser.add_argument("--collection", default="knowledge_base")
    parser.add_argument("--batch", type=int, default=int(os.getenv("INDEX_BATCH_SIZE", "64")))
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=args.chroma, settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name=args.collection)

    model = SentenceTransformer(args.embed_model)

    files = glob.glob(os.path.join(args.input, "*.json"))
    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[dict] = []

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                obj = json.load(f)
            ids.append(obj["id"])
            texts.append(obj.get("text", ""))
            metadatas.append(_sanitize_metadata(obj.get("metadata", {})))
        except Exception:
            continue

    total = 0
    for id_batch, text_batch, meta_batch in zip(chunk_list(ids, args.batch), chunk_list(texts, args.batch), chunk_list(metadatas, args.batch)):
        embeddings = model.encode(text_batch, convert_to_numpy=True).tolist()
        collection.upsert(ids=id_batch, documents=text_batch, embeddings=embeddings, metadatas=meta_batch)
        total += len(id_batch)

    print(f"Upserted {total} documents into collection '{args.collection}' at {args.chroma}")


if __name__ == "__main__":
    main()



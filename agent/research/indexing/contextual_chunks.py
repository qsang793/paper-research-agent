from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol

from agent.research.indexing.paper_store import StoredPaper
from agent.research.indexing.section_parser import ParsedPaper, Section


@dataclass
class ContextualChunk:
    chunk_id: str
    paper_id: str
    title: str
    section_title: str
    text: str
    source_url: str
    chunk_text: str = ""
    score: float = 0.0


class ChunkWriter(Protocol):
    def add(self, documents: List[str], metadatas: List[dict], ids: List[str]) -> None:
        ...


def _split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    text = " ".join(text.split())
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        chunks.append(text[start : start + chunk_size].strip())
        start += step
    return [chunk for chunk in chunks if chunk]


def _contextual_text(paper: StoredPaper, section: Section, chunk_text: str) -> str:
    authors = ", ".join(paper.authors)
    return (
        f"Paper: {paper.title}\n"
        f"Authors: {authors}\n"
        f"Year: {paper.year or ''}\n"
        f"Section: {section.title}\n"
        f"Context: {paper.abstract}\n\n"
        f"{chunk_text}"
    ).strip()


def create_contextual_chunks(
    paper: StoredPaper,
    parsed: ParsedPaper,
    *,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> List[ContextualChunk]:
    sections = parsed.sections or [Section(title="Abstract", text=paper.abstract)]
    chunks: List[ContextualChunk] = []
    for section_index, section in enumerate(sections):
        for chunk_index, chunk_text in enumerate(_split_text(section.text, chunk_size, overlap)):
            chunk_id = f"{paper.paper_id}:{section_index}:{chunk_index}"
            chunks.append(
                ContextualChunk(
                    chunk_id=chunk_id,
                    paper_id=paper.paper_id,
                    title=paper.title,
                    section_title=section.title,
                    text=_contextual_text(paper, section, chunk_text),
                    source_url=paper.source_url,
                    chunk_text=chunk_text,
                )
            )
    return chunks


def write_contextual_chunks(chunks: Iterable[ContextualChunk], writer: ChunkWriter) -> int:
    chunk_list = list(chunks)
    writer.add(
        documents=[chunk.text for chunk in chunk_list],
        metadatas=[
            {
                "paper_id": chunk.paper_id,
                "title": chunk.title,
                "section_title": chunk.section_title,
                "source_url": chunk.source_url,
            }
            for chunk in chunk_list
        ],
        ids=[chunk.chunk_id for chunk in chunk_list],
    )
    return len(chunk_list)

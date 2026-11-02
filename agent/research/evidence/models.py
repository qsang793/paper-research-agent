from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceSpan:
    paper_id: str
    title: str
    url: str
    quote: str
    score: float = 0.0
    claim: str = ""
    section_title: str = ""
    chunk_id: str = ""

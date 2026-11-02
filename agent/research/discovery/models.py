from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def normalize_doi(doi: str) -> str:
    value = doi.strip().lower()
    value = value.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    value = value.removeprefix("doi:")
    return value


@dataclass
class PaperCandidate:
    title: str
    abstract: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    published_at: Optional[str] = None
    source_provider: str = ""
    source_providers: List[str] = field(default_factory=list)
    source_url: str = ""
    pdf_url: Optional[str] = None
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    openalex_id: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    venue: Optional[str] = None
    citation_count: Optional[int] = None
    provider_rank: int = 0
    score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    raw: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.doi:
            self.doi = normalize_doi(self.doi)
        if self.source_provider and self.source_provider not in self.source_providers:
            self.source_providers.append(self.source_provider)

    def stable_key(self) -> str:
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id.lower()}"
        if self.doi:
            return f"doi:{normalize_doi(self.doi)}"
        if self.semantic_scholar_id:
            return f"s2:{self.semantic_scholar_id}"
        if self.openalex_id:
            return f"openalex:{self.openalex_id}"
        return f"title:{normalize_title(self.title)}"

    def identity_values(self) -> List[str]:
        values = []
        if self.arxiv_id:
            values.append(f"arxiv:{self.arxiv_id.lower()}")
        if self.doi:
            values.append(f"doi:{normalize_doi(self.doi)}")
        if self.semantic_scholar_id:
            values.append(f"s2:{self.semantic_scholar_id}")
        if self.openalex_id:
            values.append(f"openalex:{self.openalex_id}")
        values.append(f"title:{normalize_title(self.title)}")
        return values

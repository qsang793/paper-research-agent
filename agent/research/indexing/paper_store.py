from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agent.research.discovery.models import PaperCandidate


@dataclass
class StoredPaper:
    paper_id: str
    title: str
    abstract: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    source_url: str = ""
    pdf_url: Optional[str] = None
    source_provider: str = ""
    source_providers: List[str] = field(default_factory=list)
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    openalex_id: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    retrieved_at: float = field(default_factory=time.time)


class PaperStore:
    """Small in-memory paper metadata store with provider-id indexes."""

    def __init__(self) -> None:
        self._papers: Dict[str, StoredPaper] = {}
        self._identity_index: Dict[str, str] = {}
        self._provider_index: Dict[tuple[str, str], str] = {}

    def _find_existing_id(self, candidate: PaperCandidate) -> Optional[str]:
        for identity in candidate.identity_values():
            paper_id = self._identity_index.get(identity)
            if paper_id:
                return paper_id
        return None

    def _index(self, paper: StoredPaper) -> None:
        identities = []
        if paper.arxiv_id:
            identities.append(f"arxiv:{paper.arxiv_id.lower()}")
            self._provider_index[("arxiv", paper.arxiv_id)] = paper.paper_id
        if paper.doi:
            identities.append(f"doi:{paper.doi.lower()}")
        if paper.semantic_scholar_id:
            identities.append(f"s2:{paper.semantic_scholar_id}")
            self._provider_index[("semantic_scholar", paper.semantic_scholar_id)] = paper.paper_id
        if paper.openalex_id:
            identities.append(f"openalex:{paper.openalex_id}")
            self._provider_index[("openalex", paper.openalex_id)] = paper.paper_id
        identities.append(f"title:{paper.title.lower()}")
        for identity in identities:
            self._identity_index[identity] = paper.paper_id

    def upsert_candidate(self, candidate: PaperCandidate) -> StoredPaper:
        paper_id = self._find_existing_id(candidate) or candidate.stable_key()
        existing = self._papers.get(paper_id)
        if not existing:
            existing = StoredPaper(
                paper_id=paper_id,
                title=candidate.title,
                abstract=candidate.abstract,
                authors=list(candidate.authors),
                year=candidate.year,
                source_url=candidate.source_url,
                pdf_url=candidate.pdf_url,
                source_provider=candidate.source_provider,
                source_providers=list(candidate.source_providers),
                arxiv_id=candidate.arxiv_id,
                doi=candidate.doi,
                semantic_scholar_id=candidate.semantic_scholar_id,
                openalex_id=candidate.openalex_id,
                categories=list(candidate.categories),
            )
            self._papers[paper_id] = existing
        else:
            if not existing.abstract and candidate.abstract:
                existing.abstract = candidate.abstract
            for attr in ["arxiv_id", "doi", "semantic_scholar_id", "openalex_id", "pdf_url", "source_url", "year"]:
                if not getattr(existing, attr) and getattr(candidate, attr):
                    setattr(existing, attr, getattr(candidate, attr))
            for author in candidate.authors:
                if author not in existing.authors:
                    existing.authors.append(author)
            for provider in candidate.source_providers:
                if provider not in existing.source_providers:
                    existing.source_providers.append(provider)
            for category in candidate.categories:
                if category not in existing.categories:
                    existing.categories.append(category)

        self._index(existing)
        return existing

    def get(self, paper_id: str) -> Optional[StoredPaper]:
        return self._papers.get(paper_id)

    def get_by_provider_id(self, provider: str, provider_id: str) -> Optional[StoredPaper]:
        paper_id = self._provider_index.get((provider, provider_id))
        return self._papers.get(paper_id) if paper_id else None

    def all(self) -> List[StoredPaper]:
        return list(self._papers.values())

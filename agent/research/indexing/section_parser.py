from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from agent.research.discovery.models import PaperCandidate


@dataclass
class Section:
    title: str
    text: str


@dataclass
class ParsedPaper:
    title: str = ""
    abstract: str = ""
    sections: List[Section] = field(default_factory=list)


HEADING_RE = re.compile(r"^\s*(?:(\d+(?:\.\d+)*)\s+)?([A-Z][A-Za-z0-9 ,:/-]{2,80})\s*$")
KNOWN_HEADINGS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "method",
    "methods",
    "experiments",
    "evaluation",
    "results",
    "discussion",
    "conclusion",
    "references",
}


def _heading_title(line: str) -> Optional[str]:
    stripped = line.strip()
    match = HEADING_RE.match(stripped)
    if not match:
        return None
    raw = match.group(2).strip()
    if match.group(1) or raw.lower() in KNOWN_HEADINGS:
        return raw
    return None


def _join(lines: List[str]) -> str:
    return " ".join(line.strip() for line in lines if line.strip()).strip()


def parse_paper_text(text: str, *, candidate: PaperCandidate | None = None) -> ParsedPaper:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = candidate.title if candidate else ""
    if lines and lines[0].lower().startswith("title:"):
        title = lines.pop(0).split(":", 1)[1].strip()
    elif lines and not title and not _heading_title(lines[0]):
        title = lines.pop(0)

    headings = [(idx, _heading_title(line)) for idx, line in enumerate(lines)]
    headings = [(idx, heading) for idx, heading in headings if heading]

    abstract = candidate.abstract if candidate else ""
    sections: List[Section] = []
    for pos, (idx, heading) in enumerate(headings):
        next_idx = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines)
        body = _join(lines[idx + 1 : next_idx])
        if not body:
            continue
        if heading.lower() == "abstract":
            abstract = body
            continue
        if heading.lower() == "references":
            continue
        sections.append(Section(title=heading, text=body))

    if not sections and abstract:
        sections.append(Section(title="Abstract", text=abstract))

    if not title and candidate:
        title = candidate.title

    return ParsedPaper(title=title, abstract=abstract, sections=sections)

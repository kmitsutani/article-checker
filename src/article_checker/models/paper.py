"""Paper and Author data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Author:
    """Represents a paper author with optional Semantic Scholar metrics."""

    name: str
    h_index: Optional[int] = None
    citation_count: Optional[int] = None
    paper_count: Optional[int] = None
    semantic_scholar_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "h_index": self.h_index,
            "citation_count": self.citation_count,
            "paper_count": self.paper_count,
            "semantic_scholar_url": self.semantic_scholar_url,
        }


@dataclass
class Paper:
    """
    Unified paper representation across different sources.

    This dataclass provides a common interface for papers from arXiv,
    APS journals, Nature, and other sources.
    """

    # Required fields
    id: str  # Unique identifier (arXiv ID, DOI, or URL hash)
    title: str
    url: str
    source: str  # e.g., "arXiv:hep-th", "PRX Quantum", "Nature QI"

    # Optional fields with defaults
    abstract: str = ""
    authors: List[Author] = field(default_factory=list)
    published: Optional[datetime] = None
    keywords_matched: List[str] = field(default_factory=list)

    # Source-specific fields
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    pdf_url: Optional[str] = None
    is_open_access: bool = True

    # Computed fields (set after author evaluation)
    max_h_index: int = 0
    score_label: str = ""
    score_class: str = ""

    def compute_score(self) -> None:
        """Compute score based on max h-index of authors."""
        if self.authors:
            h_indices = [a.h_index for a in self.authors if a.h_index is not None]
            self.max_h_index = max(h_indices) if h_indices else 0

        # Set score label and class based on max h-index
        if self.max_h_index >= 100:
            self.score_label = "世界的権威"
            self.score_class = "score-s-plus"
        elif self.max_h_index >= 50:
            self.score_label = "トップ研究者"
            self.score_class = "score-s"
        elif self.max_h_index >= 20:
            self.score_label = "中核研究者"
            self.score_class = "score-a"
        elif self.max_h_index >= 10:
            self.score_label = "注目研究者"
            self.score_class = "score-b"
        else:
            self.score_label = "若手研究者"
            self.score_class = "score-c"

    def get_score_emoji(self) -> str:
        """Get emoji based on score."""
        if self.max_h_index >= 100:
            return "🏆"
        elif self.max_h_index >= 50:
            return "🏅"
        elif self.max_h_index >= 20:
            return "🟢"
        elif self.max_h_index >= 10:
            return "🔵"
        else:
            return "⚪"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "abstract": self.abstract,
            "authors": [a.to_dict() for a in self.authors],
            "published": self.published.isoformat() if self.published else None,
            "keywords_matched": self.keywords_matched,
            "arxiv_id": self.arxiv_id,
            "doi": self.doi,
            "pdf_url": self.pdf_url,
            "is_open_access": self.is_open_access,
            "max_h_index": self.max_h_index,
            "score_label": self.score_label,
        }

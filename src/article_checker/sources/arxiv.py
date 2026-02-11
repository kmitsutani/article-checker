"""arXiv RSS feed source implementation."""

import re
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import feedparser

from .base import BaseSource
from ..models import Paper, Author, parse_author_name

logger = logging.getLogger(__name__)


class ArxivSource(BaseSource):
    """
    Fetches papers from arXiv RSS feeds.

    arXiv RSS format has specific quirks:
    - Authors are comma-separated in a single 'name' field
    - IDs are in format http://arxiv.org/abs/XXXX.XXXXX
    """

    def fetch(self) -> List[Paper]:
        """Fetch and filter papers from arXiv RSS feed."""
        papers = []
        url = self.config["url"]
        category = self.config.get("category", "unknown")

        logger.info(f"Fetching arXiv feed: {url}")
        feed = feedparser.parse(url)

        if feed.bozo:
            logger.warning(f"Feed parsing warning for {url}: {feed.bozo_exception}")

        filters = self.config.get("filters", {})
        keyword_config = filters.get("keywords", {})
        include_keywords = keyword_config.get("include", [])
        exclude_keywords = keyword_config.get("exclude", [])

        for entry in feed.entries:
            try:
                paper = self._parse_entry(entry)
                paper.source = f"arXiv:{category}"
                paper.source_symbol = self.config.get("symbol", f"arxiv/{category}")

                # Apply keyword filter if enabled
                if keyword_config.get("enabled", False):
                    text = f"{paper.title} {paper.abstract}"
                    passes, matched = self._apply_keyword_filter(
                        text, include_keywords, exclude_keywords
                    )
                    if not passes:
                        continue
                    paper.keywords_matched = matched

                papers.append(paper)

            except Exception as e:
                logger.warning(f"Failed to parse entry: {e}")
                continue

        logger.info(f"Found {len(papers)} papers from arXiv:{category}")
        return papers

    def _parse_entry(self, entry: Any) -> Paper:
        """Parse an arXiv RSS entry into a Paper object."""
        # Extract arXiv ID from URL
        arxiv_id = self._extract_arxiv_id(entry.get("id", ""))

        # Parse authors (comma-separated in single field)
        authors = self._parse_authors(entry)

        # Parse publication date
        published = self._parse_date(entry)

        return Paper(
            id=entry.get("id", ""),
            title=self._clean_title(entry.get("title", "")),
            url=entry.get("link", entry.get("id", "")),
            source="arXiv",
            abstract=entry.get("summary", ""),
            authors=authors,
            published=published,
            arxiv_id=arxiv_id,
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None,
            is_open_access=True,
        )

    def _extract_arxiv_id(self, url: str) -> Optional[str]:
        """Extract arXiv ID from URL."""
        match = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
        if match:
            return match.group(1)
        return None

    def _parse_authors(self, entry: Any) -> List[Author]:
        """Parse authors from arXiv RSS entry."""
        authors = []

        if hasattr(entry, "authors") and entry.authors:
            # arXiv RSS puts all authors in first element, comma-separated
            author_string = entry.authors[0].get("name", "")
            author_names = [name.strip() for name in author_string.split(",")]

            for name in author_names:
                if name:
                    authors.append(Author(name=parse_author_name(name)))

        return authors

    def _parse_date(self, entry: Any) -> Optional[datetime]:
        """Parse publication date from entry."""
        date_str = entry.get("published", entry.get("updated", ""))
        if not date_str:
            return None

        # Try common date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _clean_title(self, title: str) -> str:
        """Clean up title (remove extra whitespace, newlines)."""
        return " ".join(title.split())

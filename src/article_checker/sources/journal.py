"""Journal RSS feed source implementation (APS, Nature, etc.)."""

import logging
import re
from datetime import datetime
from typing import Any, List, Optional

import feedparser

from ..models import Author, Paper, parse_author_name
from .base import BaseSource

logger = logging.getLogger(__name__)


class JournalSource(BaseSource):
    """
    Fetches papers from journal RSS feeds.

    Supports various journal formats:
    - APS (Physical Review, PRX Quantum)
    - Nature (Nature, Nature Physics, npj Quantum Information)
    - Quantum (quantum-journal.org)
    """

    def fetch(self) -> List[Paper]:
        """Fetch and filter papers from journal RSS feed."""
        papers = []
        url = self.config["url"]
        journal_name = self.config.get("name", "Unknown Journal")

        logger.info(f"Fetching journal feed: {journal_name} ({url})")
        feed = feedparser.parse(url)

        if feed.bozo:
            logger.warning(f"Feed parsing warning for {url}: {feed.bozo_exception}")

        filters = self.config.get("filters", {})
        keyword_config = filters.get("keywords", {})

        for entry in feed.entries:
            try:
                paper = self._parse_entry(entry)
                paper.source = journal_name
                paper.source_symbol = self.config.get("symbol", journal_name)

                # Apply keyword filter if enabled
                if keyword_config.get("enabled", False):
                    include_keywords = keyword_config.get("include", [])
                    exclude_keywords = keyword_config.get("exclude", [])
                    text = f"{paper.title} {paper.abstract}"
                    passes, matched = self._apply_keyword_filter(
                        text, include_keywords, exclude_keywords
                    )
                    if not passes:
                        continue
                    paper.keywords_matched = matched

                papers.append(paper)

            except Exception as e:
                logger.warning(f"Failed to parse entry from {journal_name}: {e}")
                continue

        logger.info(f"Found {len(papers)} papers from {journal_name}")
        return papers

    def _parse_entry(self, entry: Any) -> Paper:
        """Parse a journal RSS entry into a Paper object."""
        # Extract DOI if available
        doi = self._extract_doi(entry)

        # Parse authors
        authors = self._parse_authors(entry)

        # Parse publication date
        published = self._parse_date(entry)

        # Determine if open access
        is_open_access = self.config.get("open_access", False)

        return Paper(
            id=doi or entry.get("id", entry.get("link", "")),
            title=self._clean_title(entry.get("title", "")),
            url=entry.get("link", ""),
            source=self.config.get("name", "Journal"),
            abstract=entry.get("summary", entry.get("description", "")),
            authors=authors,
            published=published,
            doi=doi,
            is_open_access=is_open_access,
        )

    def _extract_doi(self, entry: Any) -> Optional[str]:
        """Extract DOI from entry."""
        # Try dc:identifier field (common in APS feeds)
        if hasattr(entry, "dc_identifier"):
            return entry.dc_identifier

        # Try to extract from link
        link = entry.get("link", "")
        doi_match = re.search(r"(10\.\d{4,}/[^\s]+)", link)
        if doi_match:
            return doi_match.group(1)

        return None

    def _parse_authors(self, entry: Any) -> List[Author]:
        """Parse authors from journal RSS entry."""
        authors = []

        # Try 'authors' field (list of dicts)
        if hasattr(entry, "authors") and entry.authors:
            for author in entry.authors:
                name = author.get("name", "")
                if name:
                    authors.append(Author(name=parse_author_name(name)))

        # Try 'author' field (single string)
        elif hasattr(entry, "author") and entry.author:
            authors.append(Author(name=parse_author_name(entry.author)))

        # Try dc:creator field (common in some feeds)
        elif hasattr(entry, "dc_creator"):
            if isinstance(entry.dc_creator, list):
                for name in entry.dc_creator:
                    if name:
                        authors.append(Author(name=parse_author_name(name)))
            else:
                authors.append(Author(name=parse_author_name(entry.dc_creator)))

        return authors

    def _parse_date(self, entry: Any) -> Optional[datetime]:
        """Parse publication date from entry."""
        date_str = entry.get("published", entry.get("updated", ""))

        # Try dc:date field
        if not date_str and hasattr(entry, "dc_date"):
            date_str = entry.dc_date

        if not date_str:
            return None

        # Try common date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
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
        """Clean up title (remove extra whitespace, newlines, HTML tags)."""
        # Remove HTML tags
        title = re.sub(r"<[^>]+>", "", title)
        # Normalize whitespace
        return " ".join(title.split())

"""Author evaluation service using Semantic Scholar API."""

import time
import logging
from typing import Optional

import requests

from ..models import Paper, Author
from .cache import CacheManager

logger = logging.getLogger(__name__)


class AuthorEvaluator:
    """
    Evaluates authors using the Semantic Scholar API.

    Features:
    - Fetches h-index, citation count, paper count
    - Caches results to reduce API calls
    - Respects rate limits
    """

    API_BASE = "https://api.semanticscholar.org/graph/v1"
    RATE_LIMIT_DELAY = 1.0  # seconds between requests

    def __init__(self, cache_manager: CacheManager):
        """
        Initialize the evaluator.

        Args:
            cache_manager: Cache manager for storing h-index data
        """
        self.cache = cache_manager
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ArticleChecker/1.0"})

    def evaluate_paper(self, paper: Paper, max_authors: int = 5) -> None:
        """
        Evaluate all authors of a paper.

        Args:
            paper: Paper object to evaluate
            max_authors: Maximum number of authors to evaluate (to save API calls)
        """
        logger.info(f"Evaluating authors for: {paper.title[:50]}...")

        for i, author in enumerate(paper.authors[:max_authors]):
            self._evaluate_author(author)
            if i < len(paper.authors) - 1:
                time.sleep(self.RATE_LIMIT_DELAY)

        # Compute paper score based on author h-indices
        paper.compute_score()

    def _evaluate_author(self, author: Author) -> None:
        """
        Evaluate a single author.

        Args:
            author: Author object to populate with metrics
        """
        if not author.name:
            return

        # Check cache first
        cached = self.cache.get_author(author.name)
        if cached:
            author.h_index = cached.get("h_index")
            author.citation_count = cached.get("citation_count")
            author.paper_count = cached.get("paper_count")
            author.semantic_scholar_url = cached.get("url")
            logger.debug(f"Cache hit for author: {author.name}")
            return

        # Query Semantic Scholar API
        try:
            data = self._search_author(author.name)
            if data:
                author.h_index = data.get("hIndex", 0)
                author.citation_count = data.get("citationCount", 0)
                author.paper_count = data.get("paperCount", 0)
                author.semantic_scholar_url = data.get("url", "")

                # Cache the result
                self.cache.set_author(
                    author.name,
                    {
                        "h_index": author.h_index,
                        "citation_count": author.citation_count,
                        "paper_count": author.paper_count,
                        "url": author.semantic_scholar_url,
                    },
                )
                logger.debug(f"Evaluated author: {author.name} (h-index: {author.h_index})")

        except Exception as e:
            logger.warning(f"Failed to evaluate author {author.name}: {e}")

    def _search_author(self, name: str) -> Optional[dict]:
        """
        Search for an author on Semantic Scholar.

        Args:
            name: Author name to search

        Returns:
            Author data dict or None
        """
        try:
            # Search for author
            search_url = f"{self.API_BASE}/author/search"
            params = {
                "query": name,
                "fields": "hIndex,citationCount,paperCount,url",
                "limit": 1,
            }

            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("data") and len(data["data"]) > 0:
                return data["data"][0]

        except requests.exceptions.RequestException as e:
            logger.warning(f"API error for author {name}: {e}")

        return None

    def check_h_index_threshold(
        self, paper: Paper, min_h_index: int, check_first_n: int = 3
    ) -> bool:
        """
        Check if any author meets the h-index threshold.

        This is a quick check that can be used for filtering before
        full evaluation.

        Args:
            paper: Paper to check
            min_h_index: Minimum h-index required
            check_first_n: Number of authors to check

        Returns:
            True if at least one author meets the threshold
        """
        for author in paper.authors[:check_first_n]:
            # Check cache first
            cached = self.cache.get_author(author.name)
            if cached and cached.get("h_index", 0) >= min_h_index:
                return True

            # Query API if not cached
            data = self._search_author(author.name)
            if data:
                h_index = data.get("hIndex", 0)
                # Cache the result
                self.cache.set_author(
                    author.name,
                    {
                        "h_index": h_index,
                        "citation_count": data.get("citationCount", 0),
                        "paper_count": data.get("paperCount", 0),
                        "url": data.get("url", ""),
                    },
                )
                if h_index >= min_h_index:
                    return True

            time.sleep(self.RATE_LIMIT_DELAY)

        return False

"""Abstract base class for paper sources."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..models import Paper


class BaseSource(ABC):
    """
    Abstract base class for paper sources.

    Each source (arXiv, APS, Nature, etc.) implements this interface
    to provide a unified way to fetch and filter papers.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the source with configuration.

        Args:
            config: Source-specific configuration dictionary
        """
        self.config = config
        self.name = config.get("name", self.__class__.__name__)

    @abstractmethod
    def fetch(self) -> List[Paper]:
        """
        Fetch papers from the source.

        Returns:
            List of Paper objects
        """
        pass

    @abstractmethod
    def _parse_entry(self, entry: Any) -> Paper:
        """
        Parse a single feed entry into a Paper object.

        Args:
            entry: Feed entry (format depends on source)

        Returns:
            Paper object
        """
        pass

    def _apply_keyword_filter(
        self, text: str, include: List[str], exclude: List[str]
    ) -> tuple[bool, List[str]]:
        """
        Apply keyword filtering to text.

        Args:
            text: Text to search (title + abstract)
            include: Keywords that must be present (OR logic)
            exclude: Keywords that must not be present

        Returns:
            Tuple of (passes_filter, matched_keywords)
        """
        text_lower = text.lower()

        # Check exclude keywords first
        for keyword in exclude:
            if keyword.lower() in text_lower:
                return False, []

        # Check include keywords
        matched = []
        for keyword in include:
            if keyword.lower() in text_lower:
                matched.append(keyword)

        # If include list is specified, at least one must match
        if include and not matched:
            return False, []

        return True, matched

"""Cache management for h-index and sent papers."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caches for:
    - Author h-index data (to reduce Semantic Scholar API calls)
    - Sent papers (to avoid duplicate emails)

    Each cache can optionally delegate to an external store (e.g. GistStore).
    When no external store is provided, local JSON files are used.
    """

    def __init__(
        self,
        cache_dir: Path,
        author_cache_expiry_days: int = 180,
        sent_papers_expiry_days: int = 30,
        sent_papers_store=None,
        author_cache_store=None,
    ):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store local cache files (fallback)
            author_cache_expiry_days: Days before author cache expires
            sent_papers_expiry_days: Days to keep sent papers history
            sent_papers_store: External store for sent papers (e.g. GistStore)
            author_cache_store: External store for author cache (e.g. GistStore)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.author_cache_expiry = timedelta(days=author_cache_expiry_days)
        self.sent_papers_expiry = timedelta(days=sent_papers_expiry_days)

        self._sent_papers_store = sent_papers_store
        self._author_cache_store = author_cache_store

        # Local file paths (used when no external store is provided)
        self._author_cache_file = self.cache_dir / "author_cache.json"
        self._sent_papers_file = self.cache_dir / "sent_papers.json"

        self._author_cache: Dict[str, Any] = {}
        self._sent_papers: Dict[str, Any] = {}

        self._load_caches()

    # ---- Load / Save ----

    def _load_caches(self) -> None:
        """Load caches from stores or local files."""
        if self._author_cache_store:
            self._author_cache = self._author_cache_store.load()
        else:
            self._author_cache = self._load_json(self._author_cache_file)

        if self._sent_papers_store:
            self._sent_papers = self._sent_papers_store.load()
        else:
            self._sent_papers = self._load_json(self._sent_papers_file)

        self._cleanup_expired()

    def save(self) -> None:
        """Save all caches to their respective stores."""
        # Author cache
        if self._author_cache_store:
            try:
                self._author_cache_store.save(self._author_cache)
            except Exception as e:
                logger.error(f"Failed to save author cache to external store: {e}")
        else:
            self._save_json(self._author_cache_file, self._author_cache)

        # Sent papers
        if self._sent_papers_store:
            try:
                self._sent_papers_store.save(self._sent_papers)
            except Exception as e:
                logger.error(f"Failed to save sent papers to external store: {e}")
        else:
            self._save_json(self._sent_papers_file, self._sent_papers)

    # ---- Local JSON helpers ----

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load JSON file, returning empty dict on error."""
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache {path}: {e}")
            return {}

    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Save data to JSON file."""
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache {path}: {e}")

    # ---- Expiry cleanup ----

    def _cleanup_expired(self) -> None:
        """Remove expired entries from caches."""
        now = datetime.now()

        # Cleanup author cache
        expired_authors = [
            key
            for key, data in self._author_cache.items()
            if now - datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            > self.author_cache_expiry
        ]
        for key in expired_authors:
            del self._author_cache[key]

        # Cleanup sent papers
        expired_papers = [
            key
            for key, data in self._sent_papers.items()
            if now - datetime.fromisoformat(data.get("sent_at", "2000-01-01"))
            > self.sent_papers_expiry
        ]
        for key in expired_papers:
            del self._sent_papers[key]

        if expired_authors or expired_papers:
            logger.info(
                f"Cleaned up {len(expired_authors)} expired authors, "
                f"{len(expired_papers)} expired papers"
            )

    # ---- Author cache methods ----

    def _author_key(self, name: str) -> str:
        """Generate cache key for author name."""
        normalized = name.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    def get_author(self, name: str) -> Optional[Dict[str, Any]]:
        """Get cached author data."""
        key = self._author_key(name)
        data = self._author_cache.get(key)
        if data:
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at <= self.author_cache_expiry:
                return data
        return None

    def set_author(self, name: str, data: Dict[str, Any]) -> None:
        """Cache author data."""
        key = self._author_key(name)
        data["cached_at"] = datetime.now().isoformat()
        data["name"] = name
        self._author_cache[key] = data

    # ---- Sent papers methods ----

    def _paper_key(self, paper_id: str) -> str:
        """Generate cache key for paper."""
        return hashlib.md5(paper_id.encode()).hexdigest()

    def is_paper_sent(self, paper_id: str) -> bool:
        """Check if paper has already been sent."""
        key = self._paper_key(paper_id)
        return key in self._sent_papers

    def mark_paper_sent(
        self,
        paper_id: str,
        title: str,
        source: str,
        doi: str = "",
        source_symbol: str = "",
        citation_label: str = "",
    ) -> None:
        """Mark paper as sent."""
        key = self._paper_key(paper_id)
        self._sent_papers[key] = {
            "paper_id": paper_id,
            "doi": doi,
            "title": title,
            "source": source,
            "source_symbol": source_symbol,
            "sent_at": datetime.now().isoformat(),
            "citation_label": citation_label,
        }

    def get_unsent_papers(self, papers: list) -> list:
        """Filter out already-sent papers."""
        return [p for p in papers if not self.is_paper_sent(p.id)]

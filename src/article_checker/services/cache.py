"""Cache management for h-index and sent papers."""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caches for:
    - Author h-index data (to reduce Semantic Scholar API calls)
    - Sent papers (to avoid duplicate emails)
    """

    def __init__(
        self,
        cache_dir: Path,
        author_cache_expiry_days: int = 180,
        sent_papers_expiry_days: int = 30,
    ):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store cache files
            author_cache_expiry_days: Days before author cache expires
            sent_papers_expiry_days: Days to keep sent papers history
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.author_cache_file = self.cache_dir / "author_cache.json"
        self.sent_papers_file = self.cache_dir / "sent_papers.json"

        self.author_cache_expiry = timedelta(days=author_cache_expiry_days)
        self.sent_papers_expiry = timedelta(days=sent_papers_expiry_days)

        self._author_cache: Dict[str, Any] = {}
        self._sent_papers: Dict[str, Any] = {}

        self._load_caches()

    def _load_caches(self) -> None:
        """Load caches from disk."""
        self._author_cache = self._load_json(self.author_cache_file)
        self._sent_papers = self._load_json(self.sent_papers_file)
        self._cleanup_expired()

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

    def _cleanup_expired(self) -> None:
        """Remove expired entries from caches."""
        now = datetime.now()

        # Cleanup author cache
        expired_authors = []
        for key, data in self._author_cache.items():
            cached_date = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if now - cached_date > self.author_cache_expiry:
                expired_authors.append(key)
        for key in expired_authors:
            del self._author_cache[key]

        # Cleanup sent papers
        expired_papers = []
        for key, data in self._sent_papers.items():
            sent_date = datetime.fromisoformat(data.get("sent_at", "2000-01-01"))
            if now - sent_date > self.sent_papers_expiry:
                expired_papers.append(key)
        for key in expired_papers:
            del self._sent_papers[key]

        if expired_authors or expired_papers:
            logger.info(
                f"Cleaned up {len(expired_authors)} expired authors, "
                f"{len(expired_papers)} expired papers"
            )

    def save(self) -> None:
        """Save all caches to disk."""
        self._save_json(self.author_cache_file, self._author_cache)
        self._save_json(self.sent_papers_file, self._sent_papers)

    # Author cache methods
    def _author_key(self, name: str) -> str:
        """Generate cache key for author name."""
        normalized = name.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    def get_author(self, name: str) -> Optional[Dict[str, Any]]:
        """Get cached author data."""
        key = self._author_key(name)
        data = self._author_cache.get(key)
        if data:
            # Check expiry
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

    # Sent papers methods
    def _paper_key(self, paper_id: str) -> str:
        """Generate cache key for paper."""
        return hashlib.md5(paper_id.encode()).hexdigest()

    def is_paper_sent(self, paper_id: str) -> bool:
        """Check if paper has already been sent."""
        key = self._paper_key(paper_id)
        return key in self._sent_papers

    def mark_paper_sent(self, paper_id: str, title: str, source: str) -> None:
        """Mark paper as sent."""
        key = self._paper_key(paper_id)
        self._sent_papers[key] = {
            "paper_id": paper_id,
            "title": title,
            "source": source,
            "sent_at": datetime.now().isoformat(),
        }

    def get_unsent_papers(self, papers: list) -> list:
        """Filter out already-sent papers."""
        return [p for p in papers if not self.is_paper_sent(p.id)]

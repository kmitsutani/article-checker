"""Paper source implementations."""

from .base import BaseSource
from .arxiv import ArxivSource
from .journal import JournalSource

__all__ = ["BaseSource", "ArxivSource", "JournalSource"]

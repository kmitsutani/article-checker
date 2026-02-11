"""Data models for article-checker."""

from .paper import Paper, Author, AuthorName, parse_author_name

__all__ = ["Paper", "Author", "AuthorName", "parse_author_name"]

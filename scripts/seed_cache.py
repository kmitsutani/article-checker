#!/usr/bin/env python3
"""Seed the sent papers cache with all current RSS papers.

Run this once to mark all existing papers as "already sent",
so that only genuinely new papers are processed from the next run.
"""

import logging
import os
import sys
from pathlib import Path

import yaml

from article_checker.services import CacheManager, EmailSender
from article_checker.services.gist_store import GistStore
from article_checker.sources import ArxivSource, JournalSource

SENT_PAPERS_COLUMNS = [
    "paper_id", "doi", "title", "source", "source_symbol", "sent_at", "citation_label",
]
AUTHOR_CACHE_COLUMNS = [
    "name", "h_index", "citation_count", "paper_count", "url", "cached_at",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    gist_id = os.getenv("GIST_ID", "")
    gist_token = os.getenv("GH_GIST_TOKEN", "")
    if not gist_id or not gist_token:
        print("Set GIST_ID and GH_GIST_TOKEN first")
        sys.exit(1)

    # Load feeds config
    config_path = Path(__file__).parent.parent / "config" / "feeds.yaml"
    with open(config_path) as f:
        feeds = yaml.safe_load(f)

    # Fetch all papers from all sources (with keyword filters applied)
    all_papers = []
    for cfg in feeds.get("arxiv", []):
        src = ArxivSource(cfg)
        papers = src.fetch()
        logger.info(f"arXiv {cfg['category']}: {len(papers)} papers")
        all_papers.extend(papers)
    for cfg in feeds.get("journals", []):
        src = JournalSource(cfg)
        papers = src.fetch()
        logger.info(f"{cfg['name']}: {len(papers)} papers")
        all_papers.extend(papers)

    logger.info(f"Total: {len(all_papers)} papers to seed")

    # Initialize cache with Gist store
    sent_store = GistStore(gist_id, gist_token, "sent_papers.csv", SENT_PAPERS_COLUMNS)
    author_store = GistStore(gist_id, gist_token, "author_cache.csv", AUTHOR_CACHE_COLUMNS)
    cache = CacheManager(
        Path(__file__).parent.parent / ".cache",
        sent_papers_store=sent_store,
        author_cache_store=author_store,
    )

    # Mark all papers as sent
    new_count = 0
    for paper in all_papers:
        if not cache.is_paper_sent(paper.id):
            cache.mark_paper_sent(
                paper.id,
                paper.title,
                paper.source,
                doi=paper.doi or "",
                source_symbol=paper.source_symbol,
                citation_label=EmailSender.build_citation_label(paper),
            )
            new_count += 1

    logger.info(f"Newly seeded: {new_count} papers (skipped {len(all_papers) - new_count} already in cache)")

    cache.save()
    logger.info("Done! Cache saved to Gist.")


if __name__ == "__main__":
    main()

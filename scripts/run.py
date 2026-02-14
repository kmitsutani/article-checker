#!/usr/bin/env python3
"""
Main entry point for article-checker.

Fetches papers from configured sources, evaluates authors,
and sends individual email notifications for each paper.
"""

import sys
import os
import logging
import argparse
from pathlib import Path

import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from article_checker.sources import ArxivSource, JournalSource
from article_checker.services import AuthorEvaluator, EmailSender, CacheManager
from article_checker.models import Paper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_dir: Path) -> tuple[dict, dict]:
    """Load feed and email configurations."""
    feeds_path = config_dir / "feeds.yaml"

    with open(feeds_path, "r") as f:
        feeds_config = yaml.safe_load(f)

    # Email config from environment variables only (for security)
    email_config = {
        "smtp": {
            "server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "use_tls": True,
            "username": os.getenv("GMAIL_SENDER", ""),
            "password": os.getenv("GMAIL_APP_PASSWORD", ""),
        },
        "email": {
            "from": os.getenv("GMAIL_SENDER", ""),
            "to": os.getenv("GMAIL_RECEIVER", ""),
        },
    }

    return feeds_config, email_config


def fetch_all_papers(feeds_config: dict) -> list[Paper]:
    """Fetch papers from all configured sources."""
    papers = []

    # Fetch from arXiv
    for arxiv_config in feeds_config.get("arxiv", []):
        source = ArxivSource(arxiv_config)
        papers.extend(source.fetch())

    # Fetch from journals
    for journal_config in feeds_config.get("journals", []):
        source = JournalSource(journal_config)
        papers.extend(source.fetch())

    return papers


def main():
    parser = argparse.ArgumentParser(description="Fetch and notify about new papers")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path(__file__).parent.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(__file__).parent.parent / ".cache",
        help="Cache directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and evaluate but don't send emails",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore sent papers cache (re-send all)",
    )
    args = parser.parse_args()

    logger.info("Starting article-checker...")

    # Load configuration
    feeds_config, email_config = load_config(args.config_dir)
    settings = feeds_config.get("settings", {})

    # Initialize services
    cache = CacheManager(args.cache_dir)
    evaluator = AuthorEvaluator(cache)
    sender = EmailSender(email_config)

    # Fetch papers from all sources
    logger.info("Fetching papers from all sources...")
    all_papers = fetch_all_papers(feeds_config)
    logger.info(f"Found {len(all_papers)} papers total")

    # Filter out already-sent papers
    if not args.no_cache:
        papers = cache.get_unsent_papers(all_papers)
        logger.info(f"After filtering sent papers: {len(papers)} new papers")
    else:
        papers = all_papers

    # Apply max papers limit
    max_papers = settings.get("max_papers_per_run", 50)
    if len(papers) > max_papers:
        logger.info(f"Limiting to {max_papers} papers")
        papers = papers[:max_papers]

    if not papers:
        logger.info("No new papers to process")
        cache.save()
        return

    # Evaluate authors and send emails
    evaluate_authors = settings.get("evaluate_authors", True)
    max_authors = settings.get("max_authors_to_evaluate", 5)

    sent_count = 0
    for i, paper in enumerate(papers, 1):
        logger.info(f"\n[{i}/{len(papers)}] Processing: {paper.title[:60]}...")

        # Evaluate authors (skip for journal papers — published in a journal is sufficient)
        if evaluate_authors and paper.authors and paper.arxiv_id is not None:
            evaluator.evaluate_paper(paper, max_authors=max_authors)
            logger.info(f"  Max h-index: {paper.max_h_index} ({paper.score_label})")
        elif paper.arxiv_id is None:
            paper.set_journal_score()
            logger.info(f"  Journal paper — skipping author evaluation")

        # Send email
        if args.dry_run:
            logger.info("  [DRY RUN] Would send email")
        else:
            if sender.send_paper(paper):
                cache.mark_paper_sent(paper.id, paper.title, paper.source)
                sent_count += 1
            else:
                logger.warning(f"  Failed to send email for: {paper.title[:50]}")

    # Save cache
    cache.save()

    logger.info(f"\nDone! Sent {sent_count}/{len(papers)} emails")


if __name__ == "__main__":
    main()

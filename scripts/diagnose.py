#!/usr/bin/env python3
"""Diagnose why papers might be re-sent or why sent_papers.csv keeps growing."""

import hashlib
import os
import sys
from pathlib import Path

import yaml

from article_checker.services.gist_store import GistStore
from article_checker.sources import ArxivSource, JournalSource

SENT_COLS = [
    "paper_id", "doi", "title", "source", "source_symbol", "sent_at", "citation_label",
]


def main():
    gist_id = os.getenv("GIST_ID", "")
    gist_token = os.getenv("GH_GIST_TOKEN", "")
    if not gist_id or not gist_token:
        print("Set GIST_ID and GH_GIST_TOKEN first")
        sys.exit(1)

    # 1. Load Gist
    store = GistStore(gist_id, gist_token, "sent_papers.csv", SENT_COLS)
    gist_data = store.load()
    print(f"=== Gist: {len(gist_data)} sent papers ===\n")

    # Show sent_at range
    dates = sorted(r.get("sent_at", "")[:10] for r in gist_data.values())
    if dates:
        print(f"  Date range: {dates[0]} .. {dates[-1]}")
        from collections import Counter
        date_counts = Counter(dates)
        for d, c in sorted(date_counts.items()):
            print(f"    {d}: {c} papers")
    print()

    # 2. Fetch RSS
    config_path = Path(__file__).parent.parent / "config" / "feeds.yaml"
    with open(config_path) as f:
        feeds = yaml.safe_load(f)

    all_papers = []
    for cfg in feeds.get("arxiv", []):
        src = ArxivSource(cfg)
        papers = src.fetch()
        print(f"  arXiv {cfg['category']}: {len(papers)} papers (after keyword filter)")
        all_papers.extend(papers)
    for cfg in feeds.get("journals", []):
        src = JournalSource(cfg)
        papers = src.fetch()
        print(f"  {cfg['name']}: {len(papers)} papers (after keyword filter)")
        all_papers.extend(papers)

    print(f"\n  Total RSS papers: {len(all_papers)}\n")

    # 3. Check matching
    matched = []
    unmatched = []
    for p in all_papers:
        key = hashlib.md5(p.id.encode()).hexdigest()
        if key in gist_data:
            matched.append(p)
        else:
            unmatched.append(p)

    print(f"=== Matching results ===")
    print(f"  Would SKIP (already sent): {len(matched)}")
    print(f"  Would SEND (new):          {len(unmatched)}")
    print()

    if unmatched:
        print(f"=== Unmatched papers (first 10) ===")
        for p in unmatched[:10]:
            print(f"  paper.id: {p.id[:80]}")
            print(f"  doi:      {p.doi}")
            print(f"  title:    {p.title[:60]}")
            print(f"  source:   {p.source}")
            # Check if same title exists in gist with different ID
            for r in gist_data.values():
                if p.title[:30] in r.get("title", ""):
                    print(f"  !! DUPLICATE TITLE in Gist with different ID:")
                    print(f"     gist paper_id: {r['paper_id'][:80]}")
                    break
            print()

    # 4. Check max_papers_per_run
    settings = feeds.get("settings", {})
    max_papers = settings.get("max_papers_per_run", 50)
    print(f"=== Config ===")
    print(f"  max_papers_per_run: {max_papers}")
    if len(unmatched) > max_papers:
        print(f"  !! {len(unmatched)} unmatched > limit {max_papers}")
        print(f"     This means multiple runs are needed to process all papers.")
        print(f"     Each run sends up to {max_papers}, then the next run sends more.")


if __name__ == "__main__":
    main()

"""Email sending service for paper notifications."""

import logging
import smtplib
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

from ..models import Paper
from .mathml import convert_latex_to_mathml

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Sends email notifications for papers.

    Features:
    - Batch mode: one email per source with all papers grouped together
    - HTML email with MathML support and card-based layout
    - Plain text fallback
    - はてなブックマーク「あとで読む」integration
    """

    REPO_URL = "https://github.com/kmitsutani/article-checker"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize email sender.

        Args:
            config: Email configuration dict with smtp and email settings
        """
        self.smtp_config = config.get("smtp", {})
        self.email_config = config.get("email", {})

    def send_paper(self, paper: Paper) -> bool:
        """
        Send email for a single paper (backward compatible).

        Delegates to send_batch() with a single-paper list.

        Args:
            paper: Paper to send

        Returns:
            True if sent successfully
        """
        return self.send_batch(
            paper.source,
            paper.source_symbol or paper.source,
            [paper],
        )

    def send_batch(self, source: str, source_symbol: str, papers: List[Paper]) -> bool:
        """
        Send a single email containing all papers for a given source.

        Args:
            source: Source name (e.g., "arXiv:hep-th", "PRX Quantum")
            source_symbol: Short symbol for subject (e.g., "arxiv/hep-th", "PRX-Q")
            papers: List of papers to include

        Returns:
            True if sent successfully
        """
        if not papers:
            return True

        subject = self._build_batch_subject(source_symbol, papers)
        plain_body = self._build_batch_plain_body(source, papers)
        html_body = self._build_batch_html_body(source, source_symbol, papers)

        return self._send_email(subject, plain_body, html_body)

    @staticmethod
    def build_citation_label(paper: Paper) -> str:
        """Build a short citation label like 'Smith+24_Title' or 'Smith-Jones-Lee_Title'."""
        title = paper.title.replace(" ", "")
        yy = paper.published.strftime("%y") if paper.published else ""
        if not paper.authors:
            return title
        if len(paper.authors) > 3:
            return f"{paper.authors[0].name.lastname}+{yy}_{title}"
        return "-".join(a.name.lastname for a in paper.authors) + f"_{title}"

    # ── Batch subject / plain / html ──────────────────────────────

    @staticmethod
    def _build_batch_subject(source_symbol: str, papers: List[Paper]) -> str:
        """Build subject line for a batch email."""
        n = len(papers)
        return f"[{source_symbol}] {n} new paper{'s' if n != 1 else ''}"

    def _build_batch_plain_body(self, source: str, papers: List[Paper]) -> str:
        """Build plain text body listing all papers."""
        lines = [
            f"[{self.REPO_URL}]",
            "",
            f"Source: {source}",
            f"Papers: {len(papers)}",
            "",
            "=" * 60,
        ]

        for i, paper in enumerate(papers, 1):
            citation_label = self.build_citation_label(paper)
            lines.append("")
            lines.append(f"[{i}/{len(papers)}] {paper.title}")
            lines.append(f"  Citation: {citation_label}")
            lines.append(f"  URL: {paper.url}")

            if paper.authors:
                author_names = ", ".join(a.name.fullname for a in paper.authors)
                lines.append(f"  Authors: {author_names}")

            if paper.keywords_matched:
                lines.append(f"  Keywords: {', '.join(paper.keywords_matched)}")

            if paper.score_class == "score-journal":
                lines.append(f"  {paper.score_label}")
            elif paper.max_h_index > 0:
                lines.append(f"  Max h-index: {paper.max_h_index} ({paper.score_label})")

            hatena_url = (
                "https://b.hatena.ne.jp/my/add.confirm?url="
                + urllib.parse.quote(paper.url, safe="")
            )
            lines.append(f"  あとで読む: {hatena_url}")

            lines.append("")
            lines.append("  Abstract:")
            lines.append(f"  {paper.abstract}")
            lines.append("")
            lines.append("-" * 60)

        return "\n".join(lines)

    def _build_batch_html_body(
        self, source: str, source_symbol: str, papers: List[Paper]
    ) -> str:
        """Build HTML email body with card layout for all papers."""
        cards_html = "\n".join(
            self._render_paper_card(paper, i, len(papers))
            for i, paper in enumerate(papers, 1)
        )

        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px 25px;
            border-radius: 8px 8px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 1.3em;
        }}
        .header .meta {{
            color: #bdc3c7;
            font-size: 0.85em;
            margin-top: 5px;
        }}
        .header .meta a {{
            color: #bdc3c7;
        }}
        .paper-card {{
            background-color: white;
            padding: 20px 25px;
            border-bottom: 1px solid #ecf0f1;
        }}
        .paper-card:last-child {{
            border-bottom: none;
            border-radius: 0 0 8px 8px;
        }}
        .paper-card h2 {{
            color: #2c3e50;
            font-size: 1.15em;
            margin: 0 0 8px 0;
        }}
        .paper-number {{
            display: inline-block;
            background-color: #3498db;
            color: white;
            width: 24px;
            height: 24px;
            line-height: 24px;
            text-align: center;
            border-radius: 50%;
            font-size: 0.8em;
            margin-right: 8px;
            vertical-align: middle;
        }}
        .source-badge {{
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
        }}
        .score-badge {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 15px;
            font-weight: bold;
            font-size: 0.85em;
            margin: 5px 0;
        }}
        .card-meta {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin: 5px 0;
        }}
        .keywords {{
            color: #e74c3c;
            font-weight: 500;
        }}
        .abstract {{
            background-color: #f9f9f9;
            border-left: 3px solid #95a5a6;
            padding: 12px 15px;
            margin: 12px 0;
            font-style: italic;
            color: #555;
            font-size: 0.9em;
        }}
        .buttons {{
            margin-top: 12px;
        }}
        .btn {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            font-size: 0.85em;
            margin-right: 8px;
            margin-bottom: 5px;
        }}
        .btn-read {{
            background-color: #3498db;
            color: white;
        }}
        .btn-pdf {{
            background-color: #27ae60;
            color: white;
        }}
        .btn-hatena {{
            background-color: #00A4DE;
            color: white;
        }}
        .authors-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 0.85em;
        }}
        .authors-table th {{
            background-color: #3498db;
            color: white;
            padding: 6px 8px;
            text-align: left;
        }}
        .authors-table td {{
            padding: 6px 8px;
            border-bottom: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>[{source_symbol}] {len(papers)} new paper{"s" if len(papers) != 1 else ""}</h1>
        <div class="meta">
            Source: {source} |
            <a href="{self.REPO_URL}">{self.REPO_URL}</a>
        </div>
    </div>
{cards_html}
</body>
</html>
"""
        return html

    def _render_paper_card(self, paper: Paper, index: int, total: int) -> str:
        """Render a single paper card as HTML."""
        abstract_html = convert_latex_to_mathml(paper.abstract)
        citation_label = self.build_citation_label(paper)

        # Score badge
        score_colors = {
            "score-s-plus": ("#ffd700", "#000"),
            "score-s": ("#ff6b6b", "white"),
            "score-a": ("#4ecdc4", "white"),
            "score-b": ("#45b7d1", "white"),
            "score-c": ("#95a5a6", "white"),
            "score-journal": ("#2ecc71", "white"),
        }
        bg, fg = score_colors.get(paper.score_class, ("#95a5a6", "white"))

        card = f"""    <div class="paper-card">
        <h2><span class="paper-number">{index}</span>{paper.get_score_emoji()} {paper.title}</h2>
        <div class="card-meta">{citation_label}</div>
"""

        # Authors
        if paper.authors:
            author_names = ", ".join(a.name.fullname for a in paper.authors)
            card += f'        <div class="card-meta">Authors: {author_names}</div>\n'

        # Score badge
        if paper.score_class:
            if paper.score_class == "score-journal":
                label = paper.score_label
            elif paper.max_h_index > 0:
                label = f"h-index: {paper.max_h_index} ({paper.score_label})"
            else:
                label = paper.score_label
            card += f'        <div class="score-badge" style="background-color: {bg}; color: {fg};">{label}</div>\n'

        # Keywords
        if paper.keywords_matched:
            card += f'        <div class="card-meta"><span class="keywords">Keywords: {" &bull; ".join(paper.keywords_matched)}</span></div>\n'

        # Published date
        if paper.published:
            card += f'        <div class="card-meta">Published: {paper.published.strftime("%Y-%m-%d %H:%M")}</div>\n'

        # Authors table (Semantic Scholar data)
        if paper.authors and any(a.h_index is not None for a in paper.authors):
            card += '        <table class="authors-table">\n'
            card += "            <tr><th>Author</th><th>h-index</th><th>Citations</th><th>Papers</th></tr>\n"
            for author in paper.authors:
                if author.h_index is not None:
                    url = author.semantic_scholar_url or "#"
                    citations = f"{author.citation_count:,}" if author.citation_count else "-"
                    p_count = author.paper_count if author.paper_count else "-"
                    card += f'            <tr><td><a href="{url}">{author.name.fullname}</a></td><td>{author.h_index}</td><td>{citations}</td><td>{p_count}</td></tr>\n'
            card += "        </table>\n"

        # Abstract
        card += f'        <div class="abstract">{abstract_html}</div>\n'

        # Buttons
        hatena_url = (
            "https://b.hatena.ne.jp/my/add.confirm?url="
            + urllib.parse.quote(paper.url, safe="")
        )
        card += '        <div class="buttons">\n'
        card += f'            <a href="{paper.url}" class="btn btn-read" target="_blank">Read Paper &rarr;</a>\n'
        if paper.pdf_url:
            card += f'            <a href="{paper.pdf_url}" class="btn btn-pdf" target="_blank">Download PDF</a>\n'
        card += f'            <a href="{hatena_url}" class="btn btn-hatena" target="_blank">あとで読む</a>\n'
        card += "        </div>\n"
        card += "    </div>"

        return card

    def _send_email(self, subject: str, plain_body: str, html_body: str) -> bool:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.email_config.get("from", "")
            msg["To"] = self.email_config.get("to", "")
            msg["Subject"] = subject

            # Attach both versions
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Connect and send
            server_host = self.smtp_config.get("server", "smtp.gmail.com")
            server_port = self.smtp_config.get("port", 587)
            use_ssl = self.smtp_config.get("use_ssl", False)
            use_tls = self.smtp_config.get("use_tls", True)

            if use_ssl:
                server = smtplib.SMTP_SSL(server_host, server_port)
            else:
                server = smtplib.SMTP(server_host, server_port)
                if use_tls:
                    server.starttls()

            username = self.smtp_config.get("username", "")
            password = self.smtp_config.get("password", "")
            if username and password:
                server.login(username, password)

            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent: {subject[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

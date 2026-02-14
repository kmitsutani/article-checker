"""Email sending service for paper notifications."""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any

from ..models import Paper
from .mathml import convert_latex_to_mathml

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Sends email notifications for papers.

    Features:
    - Sends one email per paper (not daily digest)
    - HTML email with MathML support
    - Plain text fallback
    """

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
        Send email for a single paper.

        Args:
            paper: Paper to send

        Returns:
            True if sent successfully
        """
        subject = self._build_subject(paper)
        plain_body = self._build_plain_body(paper)
        html_body = self._build_html_body(paper)

        return self._send_email(subject, plain_body, html_body)

    def _build_subject(self, paper: Paper) -> str:
        """Build email subject line."""
        # Truncate title if too long
        title = paper.title
        if len(title) > 60:
            title = title[:57] + "..."

        emoji = paper.get_score_emoji()
        source = paper.source

        return f"{emoji} [{source}] {title}"

    def _build_plain_body(self, paper: Paper) -> str:
        """Build plain text email body."""
        lines = [
            f"Title: {paper.title}",
            f"Source: {paper.source}",
            f"URL: {paper.url}",
            "",
        ]

        if paper.authors:
            author_names = ", ".join(a.name for a in paper.authors[:5])
            if len(paper.authors) > 5:
                author_names += " et al."
            lines.append(f"Authors: {author_names}")
            lines.append("")

        if paper.keywords_matched:
            lines.append(f"Keywords: {', '.join(paper.keywords_matched)}")
            lines.append("")

        if paper.score_class == "score-journal":
            lines.append(f"{paper.score_label}")
            lines.append("")
        elif paper.max_h_index > 0:
            lines.append(f"Max h-index: {paper.max_h_index} ({paper.score_label})")
            lines.append("")

        lines.append("Abstract:")
        lines.append(paper.abstract)

        return "\n".join(lines)

    def _build_html_body(self, paper: Paper) -> str:
        """Build HTML email body with styling."""
        # Convert abstract LaTeX to MathML
        abstract_html = convert_latex_to_mathml(paper.abstract)

        # Score badge color
        score_colors = {
            "score-s-plus": "#ffd700",
            "score-s": "#ff6b6b",
            "score-a": "#4ecdc4",
            "score-b": "#45b7d1",
            "score-c": "#95a5a6",
            "score-journal": "#2ecc71",
        }
        badge_color = score_colors.get(paper.score_class, "#95a5a6")
        is_journal = paper.score_class == "score-journal"

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
        .container {{
            background-color: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            font-size: 1.4em;
            margin-top: 0;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .source-badge {{
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            margin-bottom: 10px;
        }}
        .score-badge {{
            display: inline-block;
            background-color: {badge_color};
            color: {"#000" if paper.score_class == "score-s-plus" else "white"};
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .meta {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin: 10px 0;
        }}
        .keywords {{
            color: #e74c3c;
            font-weight: 500;
        }}
        .authors-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 0.9em;
        }}
        .authors-table th {{
            background-color: #3498db;
            color: white;
            padding: 8px;
            text-align: left;
        }}
        .authors-table td {{
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }}
        .authors-table tr:hover {{
            background-color: #f5f5f5;
        }}
        .abstract {{
            background-color: #f9f9f9;
            border-left: 3px solid #95a5a6;
            padding: 15px;
            margin: 15px 0;
            font-style: italic;
            color: #555;
        }}
        .link-button {{
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            margin-top: 15px;
        }}
        .link-button:hover {{
            background-color: #2980b9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <span class="source-badge">{paper.source}</span>
        <h1>{paper.get_score_emoji()} {paper.title}</h1>
"""

        # Score badge
        if is_journal:
            html += f"""
        <div class="score-badge">
            {paper.score_label}
        </div>
"""
        elif paper.max_h_index > 0:
            html += f"""
        <div class="score-badge">
            h-index: {paper.max_h_index} ({paper.score_label})
        </div>
"""

        # Keywords
        if paper.keywords_matched:
            html += f"""
        <div class="meta">
            <span class="keywords">Keywords: {' • '.join(paper.keywords_matched)}</span>
        </div>
"""

        # Published date
        if paper.published:
            html += f"""
        <div class="meta">
            Published: {paper.published.strftime('%Y-%m-%d %H:%M')}
        </div>
"""

        # Authors table
        if paper.authors and any(a.h_index is not None for a in paper.authors):
            html += """
        <h3>Authors (Semantic Scholar)</h3>
        <table class="authors-table">
            <tr>
                <th>Author</th>
                <th>h-index</th>
                <th>Citations</th>
                <th>Papers</th>
            </tr>
"""
            for author in paper.authors:
                if author.h_index is not None:
                    url = author.semantic_scholar_url or "#"
                    citations = f"{author.citation_count:,}" if author.citation_count else "-"
                    papers = author.paper_count if author.paper_count else "-"
                    html += f"""
            <tr>
                <td><a href="{url}" target="_blank">{author.name}</a></td>
                <td>{author.h_index}</td>
                <td>{citations}</td>
                <td>{papers}</td>
            </tr>
"""
            html += """
        </table>
"""

        # Abstract
        html += f"""
        <h3>Abstract</h3>
        <div class="abstract">{abstract_html}</div>

        <a href="{paper.url}" class="link-button" target="_blank">Read Paper →</a>
"""

        # PDF link if available
        if paper.pdf_url:
            html += f"""
        <a href="{paper.pdf_url}" class="link-button" target="_blank" style="background-color: #27ae60;">Download PDF</a>
"""

        html += """
    </div>
</body>
</html>
"""
        return html

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

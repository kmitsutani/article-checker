"""GitHub Gist-based CSV storage for cache data."""

import csv
import hashlib
import io
import logging
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


class GistStore:
    """Read and write a CSV file stored in a GitHub Gist.

    Used as a persistent backend for both sent_papers and author_cache,
    replacing the local JSON files that are lost when GitHub Actions
    cache expires.
    """

    GIST_API = "https://api.github.com/gists"

    def __init__(self, gist_id: str, token: str, filename: str, columns: List[str]):
        """
        Args:
            gist_id: GitHub Gist ID
            token: GitHub PAT with gist scope
            filename: CSV filename inside the Gist (e.g. "sent_papers.csv")
            columns: Ordered list of CSV column names
        """
        self.gist_id = gist_id
        self.filename = filename
        self.columns = columns
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ArticleChecker/1.0",
            }
        )

    def _key_for(self, row: dict) -> str:
        """Generate a stable dict key from the first column value."""
        value = row.get(self.columns[0], "")
        return hashlib.md5(value.encode()).hexdigest()

    def load(self) -> Dict[str, Any]:
        """Download CSV from Gist and return as {md5_key: row_dict}."""
        try:
            resp = self.session.get(
                f"{self.GIST_API}/{self.gist_id}", timeout=30
            )
            resp.raise_for_status()
            files = resp.json().get("files", {})

            if self.filename not in files:
                logger.info(f"No {self.filename} in Gist, starting fresh")
                return {}

            content = files[self.filename].get("content", "")
            if not content.strip():
                return {}

            reader = csv.DictReader(io.StringIO(content))
            result: Dict[str, Any] = {}
            for row in reader:
                key = self._key_for(row)
                result[key] = {col: row.get(col, "") for col in self.columns}
            logger.info(f"Loaded {len(result)} rows from Gist/{self.filename}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to load {self.filename} from Gist: {e}")
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        """Serialize dict to CSV and upload to Gist."""
        output = io.StringIO()
        writer = csv.DictWriter(
            output, fieldnames=self.columns, extrasaction="ignore"
        )
        writer.writeheader()

        rows = sorted(data.values(), key=lambda r: r.get(self.columns[-1], ""))
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in self.columns})

        try:
            resp = self.session.patch(
                f"{self.GIST_API}/{self.gist_id}",
                json={"files": {self.filename: {"content": output.getvalue()}}},
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Saved {len(rows)} rows to Gist/{self.filename}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to save {self.filename} to Gist: {e}")
            raise

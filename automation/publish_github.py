"""Publish a Markdown post to GitHub via the Contents API."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import logging
import os
import pathlib
import re
import sys
from typing import Any

import requests
from dotenv import load_dotenv

try:
    from .paths import ENV_PATH
except ImportError:
    from paths import ENV_PATH

LOGGER = logging.getLogger(__name__)


def slugify(value: str) -> str:
    """Convert a title into a file-safe slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "post"


def extract_title(markdown: str) -> str:
    """Extract a title from frontmatter or headings."""
    frontmatter_match = re.search(r"^title:\s*(.+)$", markdown, re.M)
    if frontmatter_match:
        return frontmatter_match.group(1).strip().strip("'\"")

    heading_match = re.search(r"^#\s+(.+)$", markdown, re.M)
    if heading_match:
        return heading_match.group(1).strip()
    return "claritystack-update"


def build_filename(markdown: str) -> str:
    """Build the Jekyll post filename."""
    today = dt.date.today().isoformat()
    title = extract_title(markdown)
    return f"{today}-{slugify(title)}.md"


def publish(content: str, credentials: dict[str, Any]) -> dict[str, Any]:
    """Returns {"success": bool, "url": str, "error": str|None}."""
    repository = credentials["repository"]
    token = credentials["token"]
    branch = credentials.get("branch", "main")
    posts_path = credentials.get("posts_path", "site/_posts")
    filename = credentials.get("filename") or build_filename(content)
    path = f"{posts_path}/{filename}"

    response = requests.put(
        f"https://api.github.com/repos/{repository}/contents/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "message": f"Publish blog post {filename}",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        },
        timeout=30,
    )

    if response.status_code not in {200, 201}:
        error = response.text
        LOGGER.error("GitHub publish failed: %s", error)
        return {"success": False, "url": "", "error": error}

    payload = response.json()
    file_url = payload.get("content", {}).get("html_url", "")
    return {"success": True, "url": file_url, "error": None}


def load_credentials() -> dict[str, str]:
    """Load GitHub publish credentials from the environment."""
    load_dotenv(ENV_PATH)
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY", "RayZYunYan/ClarityStack")
    branch = os.getenv("GITHUB_BRANCH", "main")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set.")
    return {"token": token, "repository": repository, "branch": branch, "posts_path": "site/_posts"}


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Path to the Markdown file to publish.")
    parser.add_argument("--dry-run", action="store_true", help="Print the request instead of publishing.")
    return parser


def main() -> int:
    """Run the GitHub publisher CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    content = pathlib.Path(args.file).read_text(encoding="utf-8")
    filename = build_filename(content)

    if args.dry_run:
        payload = {
            "filename": filename,
            "preview": content[:500],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    credentials = load_credentials()
    result = publish(content, credentials | {"filename": filename})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


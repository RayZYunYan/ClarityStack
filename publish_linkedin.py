"""Publish content to LinkedIn using the UGC Posts API."""

from __future__ import annotations

import argparse
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

LOGGER = logging.getLogger(__name__)


def write_manual_draft(content: str) -> pathlib.Path:
    """Persist a manual LinkedIn draft for copy-paste publishing."""
    outbox_dir = pathlib.Path("outbox") / "linkedin"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    filename = dt.datetime.now().strftime("%Y%m%d_%H%M%S_linkedin.txt")
    path = outbox_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def extract_first_url(content: str) -> str | None:
    """Extract the first URL from a content block."""
    match = re.search(r"https?://\S+", content)
    return match.group(0) if match else None


def refresh_access_token(credentials: dict[str, Any]) -> str | None:
    """Attempt to refresh the LinkedIn access token."""
    refresh_token = credentials.get("refresh_token")
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not refresh_token or not client_id or not client_secret:
        return None

    response = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    if response.status_code != 200:
        LOGGER.warning("LinkedIn token refresh failed: %s", response.text)
        return None
    return response.json().get("access_token")


def build_payload(content: str, author_urn: str) -> dict[str, Any]:
    """Build the LinkedIn UGC post payload."""
    first_url = extract_first_url(content)
    media_category = "ARTICLE" if first_url else "NONE"
    payload: dict[str, Any] = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": media_category,
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    if first_url:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
            {"status": "READY", "originalUrl": first_url}
        ]
    return payload


def publish(content: str, credentials: dict[str, Any]) -> dict[str, Any]:
    """Returns {"success": bool, "url": str, "error": str|None}."""
    mode = credentials.get("publish_mode", "manual")
    if mode != "api":
        draft_path = write_manual_draft(content)
        return {
            "success": True,
            "url": credentials.get("profile_url", ""),
            "error": None,
            "mode": "manual",
            "draft_path": str(draft_path),
        }

    token = credentials["access_token"]
    author_urn = credentials["author_urn"]
    payload = build_payload(content, author_urn)

    response = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if response.status_code == 401:
        refreshed = refresh_access_token(credentials)
        if refreshed:
            credentials = credentials | {"access_token": refreshed}
            return publish(content, credentials)

    if response.status_code not in {200, 201}:
        error = response.text
        LOGGER.error("LinkedIn publish failed: %s", error)
        return {"success": False, "url": "", "error": error}

    resource_id = response.headers.get("x-restli-id", "")
    url_value = f"https://www.linkedin.com/feed/update/{resource_id}" if resource_id else ""
    return {"success": True, "url": url_value, "error": None}


def load_credentials() -> dict[str, str]:
    """Load LinkedIn credentials from the environment."""
    load_dotenv()
    publish_mode = os.getenv("LINKEDIN_PUBLISH_MODE", "manual").lower()
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    author_urn = os.getenv("LINKEDIN_PERSON_URN")
    if publish_mode == "api" and (not access_token or not author_urn):
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN must be set.")
    return {
        "publish_mode": publish_mode,
        "access_token": access_token or "",
        "author_urn": author_urn or "",
        "profile_url": os.getenv("LINKEDIN_PROFILE_URL", ""),
        "client_id": os.getenv("LINKEDIN_CLIENT_ID", ""),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET", ""),
        "refresh_token": os.getenv("LINKEDIN_REFRESH_TOKEN", ""),
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Path to the text file to publish.")
    parser.add_argument("--dry-run", action="store_true", help="Print the payload instead of publishing.")
    return parser


def main() -> int:
    """Run the LinkedIn publisher CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    content = pathlib.Path(args.file).read_text(encoding="utf-8")

    if args.dry_run:
        payload = build_payload(content, "urn:li:person:example")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    result = publish(content, load_credentials())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

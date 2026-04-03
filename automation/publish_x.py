"""Publish a post or thread to X via the v2 tweets endpoint."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv

try:
    from .paths import ENV_PATH, OUTBOX_DIR
except ImportError:
    from paths import ENV_PATH, OUTBOX_DIR

LOGGER = logging.getLogger(__name__)


def split_thread(content: str) -> list[str]:
    """Split a thread into chunks separated by blank lines."""
    chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
    if not chunks:
        return []
    for chunk in chunks:
        if len(chunk) > 280:
            raise ValueError("X post exceeds 280 characters. Shorten the generated content.")
    return chunks


def check_credit_balance(credentials: dict[str, Any]) -> None:
    """Warn if the configured X API credit balance looks low."""
    balance_text = credentials.get("credit_balance", "")
    if not balance_text:
        LOGGER.warning("X API credit balance could not be verified; set X_API_CREDIT_BALANCE to track it.")
        return

    try:
        balance = float(balance_text)
    except ValueError:
        LOGGER.warning("Ignoring invalid X_API_CREDIT_BALANCE value: %s", balance_text)
        return

    if balance < 1.0:
        LOGGER.warning("X API credit balance is low: %.2f", balance)


def write_manual_thread(chunks: list[str]) -> pathlib.Path:
    """Persist a manual X thread draft for copy-paste publishing."""
    outbox_dir = OUTBOX_DIR / "x"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    filename = dt.datetime.now().strftime("%Y%m%d_%H%M%S_x_thread.txt")
    path = outbox_dir / filename
    rendered = []
    for index, chunk in enumerate(chunks, start=1):
        rendered.append(f"[Post {index}]\n{chunk}")
    path.write_text("\n\n".join(rendered) + "\n", encoding="utf-8")
    return path


def create_tweet(
    chunk: str,
    token: str,
    reply_to: str | None = None,
    max_attempts: int = 3,
) -> requests.Response:
    """Create a single tweet with basic rate limit handling."""
    payload: dict[str, Any] = {"text": chunk}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}

    for attempt in range(1, max_attempts + 1):
        response = requests.post(
            "https://api.x.com/2/tweets",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if response.status_code != 429:
            return response

        reset_at = response.headers.get("x-rate-limit-reset")
        wait_seconds = max(2, int(reset_at) - int(time.time())) if reset_at else 15
        LOGGER.warning("X rate limit hit on attempt %d; waiting %d seconds", attempt, wait_seconds)
        time.sleep(min(wait_seconds, 60))

    return response


def publish(content: str, credentials: dict[str, Any]) -> dict[str, Any]:
    """Returns {"success": bool, "url": str, "error": str|None}."""
    chunks = split_thread(content)
    if not chunks:
        return {"success": False, "url": "", "error": "No content to publish."}

    mode = credentials.get("publish_mode", "manual")
    if mode != "api":
        draft_path = write_manual_thread(chunks)
        return {
            "success": True,
            "url": credentials.get("profile_url", ""),
            "error": None,
            "mode": "manual",
            "draft_path": str(draft_path),
        }

    check_credit_balance(credentials)
    token = credentials["access_token"]
    reply_to: str | None = None
    last_tweet_id = ""

    for chunk in chunks:
        response = create_tweet(chunk, token, reply_to=reply_to)
        if response.status_code not in {200, 201}:
            error = response.text
            LOGGER.error("X publish failed: %s", error)
            return {"success": False, "url": "", "error": error}

        payload = response.json()
        last_tweet_id = payload.get("data", {}).get("id", "")
        reply_to = last_tweet_id

    username = credentials.get("username", "")
    url_value = f"https://x.com/{username}/status/{last_tweet_id}" if username and last_tweet_id else ""
    return {"success": True, "url": url_value, "error": None}


def load_credentials() -> dict[str, str]:
    """Load X credentials from the environment."""
    load_dotenv(ENV_PATH)
    publish_mode = os.getenv("X_PUBLISH_MODE", "manual").lower()
    access_token = os.getenv("X_ACCESS_TOKEN")
    if publish_mode == "api" and not access_token:
        raise RuntimeError("X_ACCESS_TOKEN is not set.")
    return {
        "publish_mode": publish_mode,
        "access_token": access_token or "",
        "username": os.getenv("X_USERNAME", ""),
        "profile_url": os.getenv("X_PROFILE_URL", ""),
        "user_id": os.getenv("X_USER_ID", ""),
        "credit_balance": os.getenv("X_API_CREDIT_BALANCE", ""),
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Path to the text file to publish.")
    parser.add_argument("--dry-run", action="store_true", help="Print the parsed thread instead of publishing.")
    return parser


def main() -> int:
    """Run the X publisher CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    content = pathlib.Path(args.file).read_text(encoding="utf-8")

    if args.dry_run:
        print(json.dumps({"thread": split_thread(content)}, indent=2, ensure_ascii=False))
        return 0

    result = publish(content, load_credentials())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


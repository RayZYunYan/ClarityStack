"""Fetch AI-related news from ArXiv, GitHub Trending, and Hacker News."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import logging
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import pathlib

import requests

LOGGER = logging.getLogger(__name__)

try:
    from .paths import OUTBOX_DIR, SITE_POSTS_DIR
except ImportError:
    from paths import OUTBOX_DIR, SITE_POSTS_DIR

PUBLISH_HISTORY_PATH = pathlib.Path(OUTBOX_DIR) / "publish_history.json"
USER_AGENT = "ClarityStackFetcher/1.0 (+https://github.com/RayZYunYan/ClarityStack)"
KEYWORDS = {
    "ai",
    "artificial intelligence",
    "ml",
    "machine learning",
    "llm",
    "transformer",
    "rag",
    "diffusion",
    "multimodal",
    "agent",
    "openai",
    "anthropic",
    "gemini",
}
TOKEN_KEYWORDS = {keyword for keyword in KEYWORDS if " " not in keyword}
PHRASE_KEYWORDS = {keyword for keyword in KEYWORDS if " " in keyword}


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace into single spaces."""
    return re.sub(r"\s+", " ", text or "").strip()


def strip_tags(text: str) -> str:
    """Remove simple HTML tags from a string."""
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", html.unescape(text)))


def split_sentences(text: str, max_sentences: int = 2) -> str:
    """Return the first few sentences from a text block."""
    parts = re.split(r"(?<=[.!?])\s+", normalize_whitespace(text))
    summary = " ".join(part for part in parts[:max_sentences] if part)
    if not summary:
        summary = normalize_whitespace(text)[:280]
    return summary[:400].strip()


def keyword_hits(*values: str) -> int:
    """Count AI-related keyword hits across text values."""
    corpus = " ".join(normalize_whitespace(value).lower() for value in values)
    tokens = set(re.findall(r"[a-z0-9]+", corpus))
    token_hits = sum(1 for keyword in TOKEN_KEYWORDS if keyword in tokens)
    phrase_hits = sum(1 for keyword in PHRASE_KEYWORDS if keyword in corpus)
    return token_hits + phrase_hits


def compute_relevance(source: str, title: str, summary: str, extra_weight: float = 0.0) -> float:
    """Generate a normalized relevance score."""
    hits = keyword_hits(title, summary)
    source_bonus = {"arxiv": 0.18, "github": 0.14, "hackernews": 0.1}.get(source, 0.0)
    score = min(0.99, 0.38 + (hits * 0.08) + source_bonus + extra_weight)
    return round(score, 2)


def fetch_arxiv(limit: int = 5, session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Fetch recent AI and CL papers from ArXiv."""
    current_utc = dt.datetime.now(dt.timezone.utc)
    cutoff = current_utc - dt.timedelta(days=2)
    search_query = urllib.parse.quote('(cat:cs.AI OR cat:cs.CL)')
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query={search_query}&sortBy=submittedDate&sortOrder=descending&max_results=20"
    )
    client = session or requests.Session()
    response = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict[str, Any]] = []

    for entry in root.findall("atom:entry", namespace):
        published_text = entry.findtext("atom:published", default="", namespaces=namespace)
        if not published_text:
            continue
        published = dt.datetime.fromisoformat(published_text.replace("Z", "+00:00"))
        if published < cutoff:
            continue

        title = normalize_whitespace(entry.findtext("atom:title", default="", namespaces=namespace))
        summary = split_sentences(entry.findtext("atom:summary", default="", namespaces=namespace), max_sentences=3)
        url_value = normalize_whitespace(entry.findtext("atom:id", default="", namespaces=namespace))
        score = compute_relevance("arxiv", title, summary, extra_weight=0.05)

        items.append(
            {
                "title": title,
                "source": "arxiv",
                "url": url_value,
                "summary": summary,
                "date": published.date().isoformat(),
                "relevance_score": score,
            }
        )

        if len(items) >= limit:
            break

    return items


def fetch_github_trending(limit: int = 5, session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Scrape the GitHub Trending page and keep AI-related repositories."""
    client = session or requests.Session()
    response = client.get(
        "https://github.com/trending?since=daily",
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    page = response.text
    blocks = re.findall(r"<article class=\"Box-row\".*?</article>", page, re.S)
    today = dt.date.today().isoformat()
    items: list[dict[str, Any]] = []

    for block in blocks:
        repo_match = re.search(r'href=\"/([^\"#?]+/[^\"#?]+)\"', block)
        if not repo_match:
            continue
        repo_name = repo_match.group(1).strip()
        if repo_name.lower().startswith("sponsors/"):
            continue
        description_match = re.search(r"<p.*?>(.*?)</p>", block, re.S)
        description = strip_tags(description_match.group(1)) if description_match else ""
        language_match = re.search(r'programmingLanguage\"[^>]*>\s*(.*?)\s*</span>', block, re.S)
        language = strip_tags(language_match.group(1)) if language_match else ""
        stars_match = re.search(r"([\d,]+)\s+stars today", block)
        stars_today = stars_match.group(1) if stars_match else "0"

        title = repo_name
        summary = normalize_whitespace(
            f"Trending GitHub repository. {description} Language: {language or 'unknown'}. "
            f"Stars today: {stars_today}."
        )
        if keyword_hits(title, summary) == 0:
            continue

        items.append(
            {
                "title": title,
                "source": "github",
                "url": f"https://github.com/{repo_name}",
                "summary": split_sentences(summary, max_sentences=2),
                "date": today,
                "relevance_score": compute_relevance("github", title, summary),
            }
        )

        if len(items) >= limit:
            break

    return items


def fetch_hacker_news(limit: int = 5, session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Fetch top Hacker News stories and keep AI-related entries."""
    client = session or requests.Session()
    ids_response = client.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    ids_response.raise_for_status()
    story_ids = ids_response.json()[:60]
    today = dt.date.today().isoformat()
    items: list[dict[str, Any]] = []

    for story_id in story_ids:
        item_response = client.get(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        item_response.raise_for_status()
        story = item_response.json() or {}
        if story.get("type") != "story":
            continue
        title = normalize_whitespace(story.get("title", ""))
        if "hiring" in title.lower():
            continue
        url_value = story.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        score = int(story.get("score", 0))
        comments = int(story.get("descendants", 0))
        summary = (
            f"Hacker News discussion with score {score} and {comments} comments. "
            f"Original link: {url_value}."
        )
        if keyword_hits(title, summary) == 0:
            continue

        items.append(
            {
                "title": title,
                "source": "hackernews",
                "url": url_value,
                "summary": split_sentences(summary, max_sentences=2),
                "date": today,
                "relevance_score": compute_relevance(
                    "hackernews",
                    title,
                    summary,
                    extra_weight=min(score / 500, 0.08),
                ),
            }
        )

        if len(items) >= limit:
            break

    return items


def extract_url_slug(url: str) -> str:
    """Return a normalised identifier for a URL — repo path for GitHub, domain+path otherwise."""
    url = url.lower().rstrip("/")
    github_match = re.search(r"github\.com/([^/]+/[^/?\s#)(>\]\"']+)", url)
    if github_match:
        return github_match.group(1)
    domain_match = re.search(r"https?://(?:www\.)?([^/?\s#]+)(/[^?\s#]*)?", url)
    if domain_match:
        return domain_match.group(1) + (domain_match.group(2) or "").rstrip("/")
    return url


def load_recent_slugs(days: int = 14) -> set[str]:
    """Return URL slugs seen in published content over the past *days* days.

    Reads from two sources:
    - outbox/publish_history.json  (authoritative; written after each real publish)
    - site/_posts/*.md             (fallback for manually committed posts)
    """
    cutoff = dt.date.today() - dt.timedelta(days=days)
    url_pattern = re.compile(r"https?://\S+")
    seen: set[str] = set()

    # Primary: local history file written by publish_github after each publish
    if PUBLISH_HISTORY_PATH.exists():
        try:
            import json as _json
            records = _json.loads(PUBLISH_HISTORY_PATH.read_text(encoding="utf-8"))
            for record in records:
                try:
                    record_date = dt.date.fromisoformat(record.get("date", ""))
                except ValueError:
                    continue
                if record_date < cutoff:
                    continue
                for url in record.get("urls", []):
                    seen.add(extract_url_slug(url))
        except Exception as exc:
            LOGGER.warning("Could not read publish history: %s", exc)

    # Fallback: scan local site/_posts/ (useful for manually committed posts)
    posts_dir = pathlib.Path(SITE_POSTS_DIR)
    if posts_dir.exists():
        for post_file in posts_dir.glob("*.md"):
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", post_file.name)
            if not date_match:
                continue
            try:
                post_date = dt.date.fromisoformat(date_match.group(1))
            except ValueError:
                continue
            if post_date < cutoff:
                continue
            text = post_file.read_text(encoding="utf-8", errors="ignore")
            for url in url_pattern.findall(text):
                seen.add(extract_url_slug(url.rstrip(").,\"'`>")))

    if seen:
        LOGGER.info("History filter: %d slug(s) seen in the past %d days", len(seen), days)
    return seen


def filter_recent_duplicates(
    items: list[dict[str, Any]], seen_slugs: set[str]
) -> list[dict[str, Any]]:
    """Remove items whose URL slug was already covered in recent published posts."""
    if not seen_slugs:
        return items
    fresh = []
    for item in items:
        slug = extract_url_slug(item.get("url", ""))
        if slug in seen_slugs:
            LOGGER.info("Skipping recently covered item: %s (%s)", item.get("title", ""), slug)
        else:
            fresh.append(item)
    return fresh


def deduplicate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate items by URL while keeping the highest scoring variant."""
    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        url_value = item["url"]
        existing = deduped.get(url_value)
        if existing is None or item["relevance_score"] > existing["relevance_score"]:
            deduped[url_value] = item
    return list(deduped.values())


def fetch_news(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch and rank AI-related items across all configured sources."""
    sources = [
        ("arxiv",      lambda s: fetch_arxiv(limit=5, session=s)),
        ("github",     lambda s: fetch_github_trending(limit=5, session=s)),
        ("hackernews", lambda s: fetch_hacker_news(limit=5, session=s)),
    ]
    with requests.Session() as session:
        candidates = []
        for name, fetcher in sources:
            try:
                items = fetcher(session)
                LOGGER.info("Fetched %d item(s) from %s", len(items), name)
                candidates.extend(items)
            except Exception as exc:
                LOGGER.warning("Source %s unavailable: %s", name, exc)

    unique_items = deduplicate_items(candidates)
    seen_slugs = load_recent_slugs(days=14)
    fresh_items = filter_recent_duplicates(unique_items, seen_slugs)

    # Fall back to all unique items if history filter removed everything
    pool = fresh_items if fresh_items else unique_items
    if not fresh_items:
        LOGGER.warning("History filter removed all candidates; using unfiltered pool")

    ranked = sorted(pool, key=lambda item: item["relevance_score"], reverse=True)
    return ranked[: max(5, min(limit, 10))]


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=8, help="Maximum number of items to emit.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def main() -> int:
    """Run the fetcher CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    try:
        items = fetch_news(limit=args.limit)
    except requests.RequestException as exc:
        LOGGER.error("Failed to fetch news: %s", exc)
        return 1

    json.dump(
        items,
        sys.stdout,
        indent=2 if args.pretty else None,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

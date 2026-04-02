"""Generate platform-specific posts from fetched news using Claude."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import re
import sys
import textwrap
import time
from typing import Any

import requests
from dotenv import load_dotenv

from privacy_scanner import scan

LOGGER = logging.getLogger(__name__)
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
MODEL_NAME = "claude-sonnet-4-6"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def load_style_guide(style_file: str) -> str:
    """Read the editorial style guide from disk."""
    return pathlib.Path(style_file).read_text(encoding="utf-8")


def collapse_text(text: str) -> str:
    """Collapse line breaks and repeated whitespace for short-form outputs."""
    return " ".join(text.split())


def truncate_text(text: str, max_length: int) -> str:
    """Trim text to a maximum length without cutting mid-word when possible."""
    compact = collapse_text(text)
    if len(compact) <= max_length:
        return compact
    shortened = compact[: max_length - 1]
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]
    return shortened.rstrip(" ,.;:-") + "…"


def select_focus_items(news_items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Keep the highest-priority items for compact social outputs."""
    return news_items[:limit]


def naturalize_title(title: str) -> str:
    """Clean a title for use in fallback prose."""
    return collapse_text(title).rstrip(". ")


def infer_item_angle(item: dict[str, Any]) -> str:
    """Create a cleaner, more human-readable angle for fallback copy."""
    title = naturalize_title(item["title"])
    source = item.get("source", "")

    lower_title = title.lower()
    if source == "arxiv":
        return "It points to a fresh research signal worth watching for AI practitioners."
    if "open source" in lower_title or "open-source" in lower_title:
        return "It shows continued momentum behind practical, builder-friendly AI tooling."
    if "agent" in lower_title:
        return "It highlights how quickly agent-style AI systems are becoming more practical."
    if "compute" in lower_title or "cost" in lower_title or "money furnace" in lower_title:
        return "It is a useful reminder that AI economics still matter as much as model capability."
    if "acquires" in lower_title or "acquisition" in lower_title:
        return "It signals another strategic move in the fast-shifting AI platform landscape."
    return "It stood out in today's AI scan as a development builders may want to keep on their radar."


def build_prompt(news_items: list[dict[str, Any]], platform: str, style_guide: str) -> str:
    """Build a platform-specific prompt for Claude."""
    prompt_items = select_focus_items(news_items, 3 if platform == "x" else len(news_items))
    items_json = json.dumps(prompt_items, indent=2, ensure_ascii=False)
    platform_instructions = {
        "linkedin": textwrap.dedent(
            """
            Produce one LinkedIn post in a professional tone.
            Open with a strong hook centered on the single most important development, optionally pairing it with one secondary item.
            Focus the main body on the top 1-2 news items, and mention any remaining items only briefly.
            Use 1-3 short paragraphs, include 2-3 emoji sparingly, keep under 3000 characters.
            Place each source link immediately after the sentence or clause discussing that item instead of collecting links at the bottom.
            Finish with 3-5 relevant hashtags.
            """
        ).strip(),
        "blog": textwrap.dedent(
            """
            Produce a Markdown blog post with frontmatter containing title, date, and tags.
            Add descriptive headers and concise technical analysis.
            When discussing an item, place its source link directly in that section or sentence instead of creating a bottom-only link dump.
            If a code snippet would help clarify a point, include a short illustrative snippet.
            """
        ).strip(),
        "x": textwrap.dedent(
            """
            Produce a 1-3 post X thread.
            Each post must stay under 280 characters.
            Each post must focus on exactly one topic or news item.
            Include exactly one most relevant source URL in each post, placed inline in that post.
            Do not add a combined sources post and do not include more than one URL per post.
            The first post should be the strongest hook.
            Separate each post with a blank line.
            """
        ).strip(),
    }

    if platform not in platform_instructions:
        raise ValueError(f"Unsupported platform: {platform}")

    return textwrap.dedent(
        f"""
        You are writing for ClarityStack, an AI news publication.

        Style guide:
        {style_guide}

        Platform requirements:
        {platform_instructions[platform]}

        News items:
        {items_json}

        Requirements:
        - Preserve factual accuracy.
        - Always include the original source URLs in the final output.
        - Do not invent facts beyond the source summaries.
        """
    ).strip()


def call_claude(prompt: str, api_key: str) -> str:
    """Submit a prompt to the Anthropic Messages API."""
    response = requests.post(
        ANTHROPIC_ENDPOINT,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "max_tokens": 1600,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    blocks = payload.get("content", [])
    text_blocks = [block.get("text", "") for block in blocks if block.get("type") == "text"]
    return "\n".join(part.strip() for part in text_blocks if part.strip()).strip()


def call_gemini(prompt: str, api_key: str) -> str:
    """Submit a prompt to the Gemini generateContent API."""
    response = None
    for attempt in range(1, 4):
        response = requests.post(
            GEMINI_ENDPOINT,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ]
            },
            timeout=60,
        )
        if response.status_code != 429:
            break

        retry_after = response.headers.get("Retry-After")
        wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else attempt * 10
        LOGGER.warning("Gemini rate limited on attempt %d; retrying in %d seconds", attempt, wait_seconds)
        time.sleep(wait_seconds)

    if response is None:
        raise RuntimeError("Gemini request did not execute.")
    response.raise_for_status()
    payload = response.json()
    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text_blocks = [part.get("text", "") for part in parts if part.get("text")]
    return "\n".join(text_blocks).strip()


def get_generation_provider() -> tuple[str, str]:
    """Resolve which text generation provider is available."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        return "anthropic", anthropic_key

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGL_API_KEY")
    if gemini_key:
        return "gemini", gemini_key

    raise RuntimeError("Set ANTHROPIC_API_KEY or GEMINI_API_KEY (GOOGLE_API_KEY also works).")


def ensure_source_links(content: str, news_items: list[dict[str, Any]], platform: str) -> str:
    """Append missing source links to guarantee attribution."""
    missing_items = [item for item in news_items if item["url"] not in content]
    if not missing_items:
        return content

    if platform == "blog":
        suffix = "\n\nAdditional source notes:\n" + "\n".join(
            f"- {item['title']}: {item['url']}" for item in missing_items
        )
    elif platform == "linkedin":
        return content
    else:
        suffix = ""
    return f"{content.rstrip()}{suffix}"


def strip_urls(text: str) -> str:
    """Remove URLs from generated text."""
    return re.sub(r"https?://\S+", "", text).strip()


def extract_urls(text: str) -> list[str]:
    """Extract URLs from generated text in order."""
    return re.findall(r"https?://\S+", text)


def build_x_post(item: dict[str, Any], intro: str = "") -> str:
    """Create a compact X post for one news item with a single inline link."""
    url = item["url"]
    prefix = f"{intro} " if intro else ""
    body = f"{prefix}{infer_item_angle(item)}"
    body = collapse_text(strip_urls(body))
    max_body_length = max(40, 280 - len(url) - 1)
    body = truncate_text(body, max_body_length)
    return f"{body} {url}"


def build_x_fallback_thread(news_items: list[dict[str, Any]]) -> str:
    """Build a deterministic X thread when model output is unusable."""
    focus_items = select_focus_items(news_items, 3)
    posts = []
    for index, item in enumerate(focus_items, start=1):
        intro = "Big AI shift:" if index == 1 else ""
        posts.append(build_x_post(item, intro=intro))
    return "\n\n".join(posts)


def sanitize_blog_output(content: str) -> str:
    """Strip model meta-explanations and keep the actual Markdown article."""
    fenced_blocks = re.findall(r"```markdown\s*(.*?)```", content, re.S | re.I)
    if fenced_blocks:
        return fenced_blocks[-1].strip()

    frontmatter_match = re.search(r"(?ms)^---\s*\n.*?(?:\n---\s*\n.*)$", content)
    if frontmatter_match:
        return frontmatter_match.group(0).strip()

    return content.strip()


def build_linkedin_fallback(news_items: list[dict[str, Any]]) -> str:
    """Build a deterministic LinkedIn post when model generation is unavailable."""
    focus = select_focus_items(news_items, 2)
    remainder = news_items[2:]
    if not focus:
        return "No AI updates were available today."

    paragraphs = [
        (
            f"One development worth watching: {naturalize_title(focus[0]['title'])} ({focus[0]['url']}). "
            f"{infer_item_angle(focus[0])} This is the clearest signal in today's batch for builders tracking practical AI deployment."
        )
    ]
    if len(focus) > 1:
        paragraphs.append(
            f"Right behind it, {naturalize_title(focus[1]['title'])} ({focus[1]['url']}) shows how fast the ecosystem is shifting. "
            f"{infer_item_angle(focus[1])}"
        )
    if remainder:
        quick_reads = "; ".join(f"{naturalize_title(item['title'])} ({item['url']})" for item in remainder[:2])
        paragraphs.append(f"Two more items worth a quick look: {quick_reads}.")
    return "\n\n".join(paragraphs) + "\n\n#AI #LLMs #OpenSource #AIBuilders"


def build_blog_fallback(news_items: list[dict[str, Any]]) -> str:
    """Build a deterministic Markdown blog post when model generation is unavailable."""
    focus = select_focus_items(news_items, 4)
    today = dt.date.today().isoformat()
    lines = [
        "---",
        'title: "ClarityStack AI Roundup"',
        f"date: {today}",
        "tags: [AI, roundup, automation]",
        "---",
        "",
        "This roundup highlights the AI developments most relevant to builders and technical readers today.",
        "",
    ]
    for item in focus:
        lines.extend(
            [
                f"## {naturalize_title(item['title'])}",
                f"{infer_item_angle(item)} Source: {item['url']}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def normalize_x_thread(content: str, news_items: list[dict[str, Any]]) -> str:
    """Force model output into a valid 1-3 post X thread."""
    focus_items = select_focus_items(news_items, 3)
    known_urls = {item["url"] for item in focus_items}
    raw_chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
    usable_chunks = [
        chunk for chunk in raw_chunks if "sources:" not in chunk.lower() and "read more:" not in chunk.lower()
    ]

    if not usable_chunks:
        return build_x_fallback_thread(focus_items)

    normalized: list[str] = []
    for index, chunk in enumerate(usable_chunks[:3]):
        fallback_item = focus_items[min(index, len(focus_items) - 1)]
        urls_in_chunk = [url for url in extract_urls(chunk) if url in known_urls]
        chosen_url = urls_in_chunk[0] if urls_in_chunk else fallback_item["url"]
        body = collapse_text(strip_urls(chunk))
        body_signal = re.sub(r"[^a-zA-Z0-9]+", "", body)
        if len(body_signal) < 24 or body.startswith("---"):
            intro = "Big AI shift:" if index == 0 else ""
            normalized.append(build_x_post(fallback_item, intro=intro))
            continue
        max_body_length = max(40, 280 - len(chosen_url) - 1)
        normalized.append(f"{truncate_text(body, max_body_length)} {chosen_url}")

    if not normalized:
        return build_x_fallback_thread(focus_items)
    normalized_urls = [extract_urls(chunk)[0] for chunk in normalized if extract_urls(chunk)]
    if len(normalized_urls) != len(set(normalized_urls)):
        return build_x_fallback_thread(focus_items)
    return "\n\n".join(normalized)


def generate(
    news_items: list[dict[str, Any]],
    platform: str,
    style_file: str = "style_guide.md",
) -> str:
    """Generate content for the requested platform."""
    load_dotenv()
    provider, api_key = get_generation_provider()

    raw_news = json.dumps(news_items, ensure_ascii=False)
    _, findings = scan(raw_news)
    if findings:
        LOGGER.warning("Input news payload triggered %d redaction(s) before generation", len(findings))

    style_guide = load_style_guide(style_file)
    prompt = build_prompt(news_items, platform, style_guide)
    cleaned_prompt, prompt_findings = scan(prompt)
    if prompt_findings:
        LOGGER.warning("Prompt triggered %d redaction(s) before model call", len(prompt_findings))

    LOGGER.info("Generating %s content with %s", platform, provider)
    try:
        if provider == "anthropic":
            content = call_claude(cleaned_prompt, api_key)
        else:
            content = call_gemini(cleaned_prompt, api_key)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if provider == "gemini" and status_code == 429:
            LOGGER.warning("Gemini remained rate limited; using deterministic %s fallback", platform)
            if platform == "linkedin":
                content = build_linkedin_fallback(news_items)
            elif platform == "blog":
                content = build_blog_fallback(news_items)
            else:
                content = build_x_fallback_thread(news_items)
        else:
            raise

    if platform == "blog":
        content = sanitize_blog_output(content)
    content = ensure_source_links(content, news_items, platform)
    if platform == "x":
        return normalize_x_thread(content, news_items)
    return content


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["linkedin", "blog", "x"], required=True)
    parser.add_argument("--input", required=True, help="Path to a JSON file containing news items.")
    parser.add_argument("--style-file", default="style_guide.md", help="Path to the style guide.")
    return parser


def main() -> int:
    """Run the content generator as a CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    news_items = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    print(generate(news_items, args.platform, style_file=args.style_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

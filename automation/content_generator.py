"""Generate platform-specific content from structured news-item JSON."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import time
from typing import Any

import requests
from dotenv import load_dotenv

try:
    from .paths import ENV_PATH, PROMPT_TEMPLATE_PATH, REPO_ROOT, STYLE_GUIDE_PATH
    from .privacy_scanner import scan
except ImportError:
    from paths import ENV_PATH, PROMPT_TEMPLATE_PATH, REPO_ROOT, STYLE_GUIDE_PATH
    from privacy_scanner import scan

LOGGER = logging.getLogger(__name__)
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
URL_PATTERN = re.compile(r"https?://\S+")
DEFAULT_SAMPLE_ITEMS = [
    {
        "title": "AMD launches Lemonade, an open-source local LLM server for GPUs and NPUs",
        "source": "github",
        "url": "https://lemonade-server.ai",
        "summary": "AMD introduced Lemonade as an open-source local inference server designed for on-device LLM workflows across GPU and NPU hardware.",
        "date": "2026-04-02",
        "relevance_score": 0.93,
    },
    {
        "title": "Qwen3.6-Plus pushes toward real-world agents",
        "source": "hackernews",
        "url": "https://qwen.ai/blog?id=qwen3.6",
        "summary": "Qwen described improvements aimed at more capable agentic workflows, including stronger tool use and better task completion on practical benchmarks.",
        "date": "2026-04-02",
        "relevance_score": 0.88,
    },
]


def collapse_text(text: str) -> str:
    """Collapse repeated whitespace for compact outputs."""
    return " ".join((text or "").split())


def truncate_text(text: str, max_length: int) -> str:
    """Trim text to a maximum length without cutting mid-word when possible."""
    compact = collapse_text(text)
    if len(compact) <= max_length:
        return compact
    shortened = compact[: max_length - 1]
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]
    return shortened.rstrip(" ,.;:-") + "…"


def strip_urls(text: str) -> str:
    """Remove URLs from text."""
    return URL_PATTERN.sub("", text or "").strip()


def extract_urls(text: str) -> list[str]:
    """Extract URLs in order."""
    return URL_PATTERN.findall(text or "")


def load_style_guide(style_file: str | pathlib.Path) -> str:
    """Read the editorial style guide from disk."""
    return pathlib.Path(style_file).read_text(encoding="utf-8")


def load_prompt_template(template_file: str | pathlib.Path) -> dict[str, Any]:
    """Load the structured prompt template from disk."""
    return json.loads(pathlib.Path(template_file).read_text(encoding="utf-8"))


def get_prompt_template_path(template_file: str | None = None) -> pathlib.Path:
    """Resolve the prompt template path from arg/env/default."""
    if template_file:
        candidate = pathlib.Path(template_file)
        return candidate if candidate.is_absolute() else REPO_ROOT / candidate
    configured = os.getenv("PROMPT_TEMPLATE_PATH", "").strip()
    if configured:
        candidate = pathlib.Path(configured)
        return candidate if candidate.is_absolute() else REPO_ROOT / candidate
    return PROMPT_TEMPLATE_PATH


def template_limits(template: dict[str, Any]) -> dict[str, int | None]:
    """Map template keys to max lengths."""
    limits: dict[str, int | None] = {}
    for field in template.get("fields", []):
        limits[field["key"]] = field.get("max_length")
    return limits


def naturalize_title(title: str) -> str:
    """Clean a title for prose use."""
    return collapse_text(title).rstrip(". ")


def clean_source_summary(item: dict[str, Any]) -> str:
    """Turn source summaries into readable fallback prose."""
    title = naturalize_title(item.get("title", ""))
    summary = collapse_text(item.get("summary", ""))
    if not summary:
        return f"The original source centers on {title}."
    if "Hacker News discussion with score" in summary:
        return f"The original source centers on {title}, and it is already drawing attention from technical readers tracking AI product and research shifts."
    summary = re.sub(r"Original link:\s*https?://\S+\.?", "", summary)
    return summary.strip() or f"The original source centers on {title}."


def build_template_field_map(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map template keys to full field descriptors."""
    return {field["key"]: field for field in template.get("fields", [])}


def infer_item_angle(item: dict[str, Any]) -> str:
    """Create a cleaner, more human-readable angle for fallback copy."""
    title = collapse_text(item.get("title", "")).rstrip(". ")
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


def suggest_context(item: dict[str, Any]) -> str:
    """Create a broader-trend context sentence for fallback JSON."""
    source = item.get("source", "")
    if source == "arxiv":
        return "This fits the steady cadence of AI research moving from benchmark gains toward more deployable systems and clearer real-world use cases."
    if source == "github":
        return "This lines up with the broader shift toward open tooling that gives teams more control over deployment cost, latency, and privacy."
    return "This sits inside a broader AI cycle where product launches, infrastructure bets, and model updates are landing faster than most teams can evaluate them."


def suggest_application(item: dict[str, Any]) -> str:
    """Create a use-case-oriented fallback line."""
    title = collapse_text(item.get("title", "")).lower()
    if "local" in title or "server" in title or "gpu" in title or "npu" in title:
        return "It matters for private copilots, internal assistants, and cost-sensitive on-device inference workflows."
    if "agent" in title:
        return "It is most relevant for support automation, internal research agents, and workflow tools that need stronger tool use."
    if "video" in title or "compute" in title or "cost" in title:
        return "It matters anywhere teams are budgeting for multimodal products, heavy inference pipelines, or premium AI features."
    return "It could shape roadmap decisions for product teams, infrastructure engineers, and technical leaders evaluating where to invest next."


def suggest_relevance_to_builders(item: dict[str, Any]) -> str:
    """Create a builder-centric relevance sentence for fallback JSON."""
    title = collapse_text(item.get("title", "")).lower()
    if "local" in title or "server" in title or "gpu" in title or "npu" in title:
        return "If you are building AI systems, this matters because it could shift local inference cost, privacy, and deployment control in your stack."
    if "agent" in title:
        return "If you are building agents, this matters because better tool use and task completion can change what workflows are realistic to automate."
    if "compute" in title or "cost" in title or "video" in title:
        return "If you ship AI features, this matters because infrastructure cost can kill product margins long before model quality does."
    if "acquires" in title or "acquisition" in title:
        return "If your stack depends on a fast-moving vendor, this matters because product direction and integration surfaces can change quickly after acquisitions."
    return "If you are building AI products, this matters because it may affect model choice, system design, or what is worth prototyping next."


def suggest_counterpoint(item: dict[str, Any]) -> str:
    """Create a skeptical or limiting view for fallback JSON."""
    title = collapse_text(item.get("title", "")).lower()
    if "open source" in title or "open-source" in title:
        return "Open tooling still has to prove reliability, maintenance quality, and production ergonomics against more mature managed stacks."
    if "agent" in title:
        return "Agent progress is still easy to overstate because benchmark wins do not always translate into reliable task completion in messy environments."
    if "compute" in title or "cost" in title or "video" in title:
        return "The main risk is that cost curves stay stubbornly high, which can turn flashy demos into weak business models."
    return "The obvious caution is that headlines move faster than operational proof, so teams should wait for evidence beyond launch-day claims."


def suggest_action(item: dict[str, Any]) -> str:
    """Create an actionable takeaway for fallback JSON."""
    title = collapse_text(item.get("title", "")).lower()
    if "local" in title or "server" in title:
        return "Test whether this can replace a small slice of your hosted inference workload before assuming you need a bigger platform bet."
    if "agent" in title:
        return "Watch for benchmark details, tool-use behavior, and failure cases before wiring it into production workflows."
    if "compute" in title or "cost" in title:
        return "Revisit unit economics for any AI feature on your roadmap and model best-case versus worst-case inference cost now."
    return "Track the primary source directly and decide whether it changes your roadmap, evaluation stack, or monitoring priorities this quarter."


def build_minimal_structured_item(item: dict[str, Any], template: dict[str, Any]) -> dict[str, str]:
    """Build a readable minimal structured record when extraction fails."""
    limits = template_limits(template)
    minimal = {
        "hook": naturalize_title(item.get("title", "")),
        "summary": clean_source_summary(item),
        "context": suggest_context(item),
        "insight": infer_item_angle(item),
        "relevance_to_builders": suggest_relevance_to_builders(item),
        "application": suggest_application(item),
        "counterpoint": suggest_counterpoint(item),
        "action": suggest_action(item),
        "source_url": item.get("url", ""),
    }
    return normalize_structured_item(minimal, item, template, allow_empty=False)


def normalize_structured_item(
    raw_data: dict[str, Any],
    item: dict[str, Any],
    template: dict[str, Any],
    allow_empty: bool = False,
) -> dict[str, str]:
    """Normalize extracted JSON against the template and source item."""
    field_map = build_template_field_map(template)
    fallback = build_minimal_structured_item(item, template) if allow_empty else None
    normalized: dict[str, str] = {}

    for key, descriptor in field_map.items():
        max_length = descriptor.get("max_length")
        if key == "source_url":
            normalized[key] = item.get("url", "")
            continue

        raw_value = collapse_text(str(raw_data.get(key, "")))
        if not raw_value and fallback is not None:
            raw_value = fallback[key]
        if max_length:
            raw_value = truncate_text(raw_value, max_length)
        normalized[key] = raw_value

    return normalized


def sanitize_json_text(text: str) -> str:
    """Strip markdown fences and isolate the main JSON object."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    match = re.search(r"\{.*\}", cleaned, re.S)
    return match.group(0) if match else cleaned


def parse_structured_response(text: str) -> dict[str, Any]:
    """Parse a Gemini JSON response safely."""
    cleaned = sanitize_json_text(text)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("Structured extraction response was not a JSON object.")
    return payload


def build_extraction_prompt(item: dict[str, Any], template: dict[str, Any]) -> str:
    """Build the structured extraction prompt for a single news item."""
    field_lines = []
    for field in template.get("fields", []):
        max_note = f" (max {field['max_length']} chars)" if field.get("max_length") else ""
        field_lines.append(f'- {field["key"]}:{max_note} {field["instruction"]}')
    field_block = "\n".join(field_lines)

    return textwrap.dedent(
        f"""
        You are extracting builder-relevant structured notes for a developer who builds AI systems.
        For the following news item, fill in EVERY field of this JSON structure.
        Respond with valid JSON only, no markdown fences, no preamble.
        Be concrete and useful for someone shipping AI products, agents, evals, or inference infrastructure.
        The field relevance_to_builders is required and should say why a hands-on builder should care.

        News item:
        Title: {item.get("title", "")}
        Source: {item.get("source", "")}
        URL: {item.get("url", "")}
        Summary: {item.get("summary", "")}

        JSON template:
        {field_block}
        """
    ).strip()


def get_gemini_api_key() -> str | None:
    """Resolve the Gemini key if one is configured."""
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGL_API_KEY")


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
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        if response.status_code != 429:
            break

        retry_after = response.headers.get("Retry-After")
        wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(8, attempt * 2)
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


def extract_structured_item(item: dict[str, Any], template: dict[str, Any], api_key: str | None) -> dict[str, str]:
    """Extract one structured JSON item through Gemini, with graceful fallback."""
    if not api_key:
        return build_minimal_structured_item(item, template)

    prompt = build_extraction_prompt(item, template)
    cleaned_prompt, prompt_findings = scan(prompt)
    if prompt_findings:
        LOGGER.warning("Structured extraction prompt triggered %d redaction(s)", len(prompt_findings))

    for attempt in range(1, 3):
        try:
            response_text = call_gemini(cleaned_prompt, api_key)
            parsed = parse_structured_response(response_text)
            return normalize_structured_item(parsed, item, template, allow_empty=True)
        except json.JSONDecodeError as exc:
            LOGGER.warning("Gemini structured extraction returned invalid JSON on attempt %d: %s", attempt, exc)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 429:
                LOGGER.warning("Gemini extraction remained rate limited; using minimal structured fallback")
                return build_minimal_structured_item(item, template)
            raise
        except Exception as exc:
            LOGGER.warning("Gemini structured extraction failed on attempt %d: %s", attempt, exc)

    return build_minimal_structured_item(item, template)


def structure_news_items(
    news_items: list[dict[str, Any]],
    template_file: str | pathlib.Path | None = None,
    limit: int = 5,
) -> list[dict[str, str]]:
    """Convert raw news items into structured JSON records."""
    load_dotenv(ENV_PATH)
    template = load_prompt_template(get_prompt_template_path(str(template_file) if template_file else None))
    api_key = get_gemini_api_key()
    structured_items = []
    for item in news_items[:limit]:
        structured_items.append(extract_structured_item(item, template, api_key))
    return structured_items


def build_assembly_prompt(structured_items: list[dict[str, str]], platform: str, style_guide: str) -> str:
    """Build the prose-assembly prompt for Claude or Gemini."""
    items_json = json.dumps(structured_items, indent=2, ensure_ascii=False)
    instructions = {
        "linkedin": textwrap.dedent(
            """
            Assemble one LinkedIn post.
            - Professional but conversational
            - Lead with the strongest hook and focus on the most important 1-2 items
            - Weave in insights and counterpoints naturally
            - Mention any remaining items briefly, with their links inline next to the relevant mention
            - Use 1-2 emoji max and keep the post under 3000 characters
            - Do not dump links at the bottom
            """
        ).strip(),
        "blog": textwrap.dedent(
            """
            Assemble one Markdown blog post.
            - Preserve Markdown output
            - Include frontmatter with title, date, and tags
            - Give each item its own section
            - Write in first person and sound like a builder talking to peers
            - In each section, move through What, So What, and My Take naturally
            - Use relevance_to_builders to sharpen the So What layer
            - End each section with a concrete next step or a clear dismissal
            - Weave counterpoints in naturally instead of labeling them mechanically
            - Keep source links inline in paragraphs and end with a clean References section
            - Format all references as Markdown links, never raw URLs
            """
        ).strip(),
        "x": textwrap.dedent(
            """
            Assemble a 2-3 tweet X thread.
            - Focus on the top 1-2 items only
            - Tweet 1 is the hook and should not include a link
            - Each later tweet should focus on one topic and include exactly one relevant source link
            - Stay under 280 characters per tweet
            - Keep it punchy and free of filler words
            """
        ).strip(),
    }
    if platform not in instructions:
        raise ValueError(f"Unsupported platform: {platform}")

    return textwrap.dedent(
        f"""
        You are writing for ClarityStack.

        Style guide:
        {style_guide}

        Platform instructions:
        {instructions[platform]}

        Structured source material:
        {items_json}

        Use the structured data as raw material. Write naturally.
        Write like a developer who builds AI systems, not a journalist.
        Use first person freely.
        Give a specific technical judgment for each topic.
        If something is overhyped, narrow, or not useful, say so directly.
        Do NOT output JSON or field labels.
        Preserve all original source URLs exactly as they appear in the structured data.
        Do not invent facts.
        Return only the final content.
        """
    ).strip()


def run_claude_cli(prompt: str, timeout: int = 60) -> str:
    """Call Claude Code CLI in one-shot print mode."""
    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "text",
            "--model",
            "sonnet",
            "--max-turns",
            "1",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        stderr_line = result.stderr.strip().splitlines()[0] if result.stderr.strip() else "unknown error"
        raise RuntimeError(stderr_line)
    return result.stdout.strip()


def sanitize_blog_output(content: str) -> str:
    """Strip model meta-explanations and keep the actual Markdown article."""
    fenced_blocks = re.findall(r"```markdown\s*(.*?)```", content, re.S | re.I)
    if fenced_blocks:
        return fenced_blocks[-1].strip()

    frontmatter_match = re.search(r"(?ms)^---\s*\n.*?(?:\n---\s*\n.*)$", content)
    if frontmatter_match:
        return frontmatter_match.group(0).strip()

    return content.strip()


def ensure_inline_links(content: str, structured_items: list[dict[str, str]], platform: str) -> str:
    """Guarantee key source URLs survive assembly."""
    missing = [item for item in structured_items if item["source_url"] not in content]
    if not missing:
        return content

    if platform == "linkedin":
        additions = " ".join(f"Also worth tracking: {item['hook']} ({item['source_url']})." for item in missing[:3])
        candidate = content.rstrip() + "\n\n" + additions
        return candidate[:3000].rstrip() if len(candidate) > 3000 else candidate

    if platform == "blog":
        reference_lines = ["", "## References"]
        reference_lines.extend(
            f"- [{item['hook']}]({item['source_url']})"
            for item in missing
        )
        return content.rstrip() + "\n" + "\n".join(reference_lines)

    return content


def normalize_x_thread(content: str, structured_items: list[dict[str, str]]) -> str:
    """Force model output into a valid 2-3 tweet thread."""
    top_items = structured_items[:2] if len(structured_items) > 1 else structured_items[:1]
    chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
    if not chunks:
        return build_x_fallback(top_items)

    normalized: list[str] = []
    for index, chunk in enumerate(chunks[:3]):
        body = collapse_text(strip_urls(chunk))
        urls = extract_urls(chunk)
        chosen_url = urls[0] if urls else ""

        if index == 0:
            normalized.append(truncate_text(body, 280))
            continue

        fallback_url = top_items[min(index - 1, len(top_items) - 1)]["source_url"] if top_items else chosen_url
        chosen_url = chosen_url or fallback_url
        max_body = max(40, 280 - len(chosen_url) - 1)
        normalized.append(f"{truncate_text(body, max_body)} {chosen_url}".strip())

    if len(normalized) < 2:
        return build_x_fallback(top_items)
    return "\n\n".join(normalized[:3])


def validate_output(content: str, platform: str, structured_items: list[dict[str, str]]) -> bool:
    """Validate assembled output against platform constraints."""
    if not content.strip():
        return False

    if platform == "linkedin":
        return len(content) <= 3000

    if platform == "blog":
        return content.lstrip().startswith("---")

    if platform == "x":
        tweets = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
        if not 2 <= len(tweets) <= 3:
            return False
        if any(len(tweet) > 280 for tweet in tweets):
            return False
        if extract_urls(tweets[0]):
            return False
        if any(len(extract_urls(tweet)) > 1 for tweet in tweets[1:]):
            return False
    return True


def assemble_with_model(
    structured_items: list[dict[str, str]],
    platform: str,
    style_guide: str,
    prefer_claude: bool,
    gemini_key: str | None,
) -> str:
    """Assemble final prose through Claude CLI or Gemini."""
    prompt = build_assembly_prompt(structured_items, platform, style_guide)
    cleaned_prompt, prompt_findings = scan(prompt)
    if prompt_findings:
        LOGGER.warning("Assembly prompt triggered %d redaction(s)", len(prompt_findings))

    if prefer_claude and shutil.which("claude"):
        try:
            LOGGER.info("Assembling %s content with Claude Code CLI", platform)
            return run_claude_cli(cleaned_prompt, timeout=60)
        except Exception as exc:
            LOGGER.warning("Claude assembly unavailable for %s: %s", platform, exc)

    if gemini_key:
        try:
            LOGGER.info("Assembling %s content with Gemini", platform)
            return call_gemini(cleaned_prompt, gemini_key)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code != 429:
                raise
            LOGGER.warning("Gemini assembly remained rate limited for %s; falling back deterministically", platform)

    return build_deterministic_output(structured_items, platform)


def build_linkedin_fallback(structured_items: list[dict[str, str]]) -> str:
    """Build a readable LinkedIn post from structured JSON."""
    focus = structured_items[:2]
    rest = structured_items[2:5]
    if not focus:
        return "No AI updates were available today."

    paragraphs = [
        (
            f"{focus[0]['hook']} {focus[0]['summary']} {focus[0]['insight']} "
            f"{focus[0]['source_url']}"
        )
    ]
    if len(focus) > 1:
        paragraphs.append(
            f"Another signal worth watching: {focus[1]['hook']} {focus[1]['context']} {focus[1]['counterpoint']} {focus[1]['source_url']}"
        )
    if rest:
        brief = " ".join(
            f"{item['hook']} {item['source_url']}" for item in rest[:2]
        )
        paragraphs.append(f"Two shorter reads on the radar: {brief}")
    paragraphs.append("If I were prioritizing this stack today, I would test the pieces that change deployment economics or workflow reliability first and ignore the rest. #AI #LLMs #OpenSource #AIBuilders")
    return "\n\n".join(paragraphs)


def build_blog_fallback(structured_items: list[dict[str, str]]) -> str:
    """Build a Markdown roundup from structured JSON."""
    today = dt.date.today().isoformat()
    lines = [
        "---",
        'title: "ClarityStack AI Roundup"',
        f"date: {today}",
        "tags: [AI, roundup, automation]",
        "---",
        "",
        "I care less about AI headlines than about what changes how I would actually build. This roundup filters for the developments that seem most relevant to real systems work.",
        "",
    ]
    for item in structured_items[:5]:
        lines.extend(
            [
                f"## {item['hook']}",
                "",
                f"{item['summary']} [Source]({item['source_url']})",
                "",
                f"{item['relevance_to_builders']} {item['context']}",
                "",
                f"My take: {item['insight']} {item['application']}",
                "",
                f"The catch: {item['counterpoint']}",
                "",
                f"What I'd do: {item['action']}",
                "",
            ]
        )
    lines.append("## References")
    lines.extend(f"- [{item['hook']}]({item['source_url']})" for item in structured_items[:5])
    return "\n".join(lines).strip()


def build_x_fallback(structured_items: list[dict[str, str]]) -> str:
    """Build a tight X thread from structured JSON."""
    if not structured_items:
        return "No AI updates available today."

    top = structured_items[0]
    second = structured_items[1] if len(structured_items) > 1 else None

    tweet_1 = truncate_text(f"{top['hook']} {top['insight']}", 280)
    top_body = f"{top['summary']} {top['action']}"
    tweet_2 = f"{truncate_text(top_body, max(40, 280 - len(top['source_url']) - 1))} {top['source_url']}"
    tweets = [tweet_1, tweet_2]

    if second:
        second_body = f"{second['hook']} {second['action']}"
        tweets.append(
            f"{truncate_text(second_body, max(40, 280 - len(second['source_url']) - 1))} {second['source_url']}"
        )

    return "\n\n".join(tweets[:3])


def build_deterministic_output(structured_items: list[dict[str, str]], platform: str) -> str:
    """Fallback assembly from structured JSON."""
    if platform == "linkedin":
        return build_linkedin_fallback(structured_items)
    if platform == "blog":
        return build_blog_fallback(structured_items)
    return build_x_fallback(structured_items)


def post_process_output(content: str, platform: str, structured_items: list[dict[str, str]]) -> str:
    """Clean and normalize assembled output."""
    processed = content.strip()
    if platform == "blog":
        processed = sanitize_blog_output(processed)
        processed = ensure_inline_links(processed, structured_items, platform)
    elif platform == "linkedin":
        processed = ensure_inline_links(processed, structured_items, platform)
    else:
        processed = normalize_x_thread(processed, structured_items)
    return processed.strip()


def generate(
    news_items: list[dict[str, Any]],
    platform: str,
    style_file: str = str(STYLE_GUIDE_PATH),
    template_file: str | None = None,
    structured_items: list[dict[str, str]] | None = None,
) -> str:
    """Generate content for the requested platform from structured JSON."""
    load_dotenv(ENV_PATH)
    raw_news = json.dumps(news_items, ensure_ascii=False)
    _, findings = scan(raw_news)
    if findings:
        LOGGER.warning("Input news payload triggered %d redaction(s) before generation", len(findings))

    template_path = get_prompt_template_path(template_file)
    style_guide = load_style_guide(style_file)
    if structured_items is None:
        structured_items = structure_news_items(news_items, template_path, limit=5)
    gemini_key = get_gemini_api_key()
    prefer_claude = os.getenv("CLAUDE_POLISH_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

    content = assemble_with_model(structured_items, platform, style_guide, prefer_claude=prefer_claude, gemini_key=gemini_key)
    content = post_process_output(content, platform, structured_items)
    if validate_output(content, platform, structured_items):
        return content

    LOGGER.warning("Structured assembly output failed validation for %s; using deterministic fallback", platform)
    return build_deterministic_output(structured_items, platform)


def run_structured_test(style_file: str, template_file: str | None) -> dict[str, Any]:
    """Run a local structured extraction + assembly smoke test."""
    load_dotenv(ENV_PATH)
    template_path = get_prompt_template_path(template_file)
    structured_items = structure_news_items(DEFAULT_SAMPLE_ITEMS, template_path, limit=2)
    outputs = {
        platform: generate(
            DEFAULT_SAMPLE_ITEMS,
            platform,
            style_file=style_file,
            template_file=str(template_path),
            structured_items=structured_items,
        )
        for platform in ("linkedin", "blog", "x")
    }
    return {"structured_items": structured_items, "outputs": outputs}


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["linkedin", "blog", "x"])
    parser.add_argument("--input", help="Path to a JSON file containing news items.")
    parser.add_argument("--style-file", default=str(STYLE_GUIDE_PATH), help="Path to the style guide.")
    parser.add_argument("--template-file", default=None, help="Optional override path for the structured prompt template.")
    parser.add_argument("--test-structured", action="store_true", help="Run a structured extraction and assembly smoke test.")
    return parser


def main() -> int:
    """Run the content generator as a CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    if args.test_structured:
        payload = run_structured_test(args.style_file, args.template_file)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if not args.platform or not args.input:
        raise SystemExit("--platform and --input are required unless --test-structured is used.")

    news_items = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    print(generate(news_items, args.platform, style_file=args.style_file, template_file=args.template_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())






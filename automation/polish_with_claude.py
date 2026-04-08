"""Polish generated content using Claude Code CLI."""

from __future__ import annotations

import argparse
import logging
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap

try:
    from .paths import STYLE_GUIDE_PATH
except ImportError:
    from paths import STYLE_GUIDE_PATH

LOGGER = logging.getLogger(__name__)
URL_PATTERN = re.compile(r"https?://\S+")


def load_style_guide(style_guide_path: str) -> str:
    """Load the style guide, falling back to a compact default if missing."""
    path = pathlib.Path(style_guide_path)
    if path.exists():
        return path.read_text(encoding="utf-8")

    return textwrap.dedent(
        """
        Voice:
        - Write like a developer building AI systems, not a journalist.
        - Use first person freely and give concrete technical judgments.
        - Sound like a senior engineer talking to peers, not a press release.
        """
    ).strip()


def extract_urls(text: str) -> list[str]:
    """Extract URLs from text in order."""
    return URL_PATTERN.findall(text)


def build_prompt(content: str, platform: str, style_guide: str) -> str:
    """Build a one-shot Claude CLI polishing prompt."""
    url_lines = extract_urls(content)
    url_inventory = "\n".join(f"- {url}" for url in url_lines) if url_lines else "- No URLs found"
    instructions = {
        "linkedin": textwrap.dedent(
            """
            Polish this LinkedIn post.
            - Conversational builder tone, still polished enough for LinkedIn
            - Use 1-2 emoji max, naturally placed
            - Keep under 2800 characters (a footer will be appended separately)
            - Keep the opening hook focused on the most important 1-2 news items only — drop the rest
            - Keep each source link inline next to its relevant mention, not dumped at the bottom
            - Do NOT use any Markdown formatting: no **bold**, no *italics*, no ## headers
            - Do not add a sign-off or closing line
            """
        ).strip(),
        "blog": textwrap.dedent(
            """
            Polish this Markdown blog post.
            - Preserve Markdown formatting and frontmatter exactly
            - If there is an H1 heading immediately after the frontmatter that repeats the title, remove it — the layout renders the title from frontmatter already
            - Keep the writing in first person with clear technical judgment
            - Improve transitions between sections without flattening the voice
            - Make code references and technical terms precise
            - Keep links inline in relevant paragraphs
            - End with a clean References section at the bottom
            - Format all references as Markdown links, never raw URLs
            """
        ).strip(),
        "x": textwrap.dedent(
            """
            Polish this X thread.
            - Max 3 tweets
            - Each tweet focuses on ONE topic with ONE link
            - First tweet is a hook and should not include a link
            - Tweets must stay under 280 characters
            - Keep the tone punchy and concise, with no filler words
            """
        ).strip(),
    }
    if platform not in instructions:
        raise ValueError(f"Unsupported platform: {platform}")

    return textwrap.dedent(
        f"""
        You are ghostwriting a tech blog post for a developer who builds AI systems.

        Rules:
        1. Write in first person. Use "I" freely.
        2. For each topic, after explaining what it is, add a personal take that includes a specific technical judgment. Prefer lines like "I'd use this for X but not Y because Z."
        3. Never use hedge phrases like "it remains to be seen", "time will tell", "teams should consider", "the practical stance is", or "the broader pattern". Replace them with concrete opinions.
        4. Reference the author's own tech stack when relevant: local inference on a Mac mini, NemoClaw sandbox, and multi-model pipelines with Gemini + Claude.
        5. Tone: like a senior engineer talking to peers at lunch, not a press release.
        6. If a topic is boring or overhyped, say so. Not every item needs praise.
        7. End each topic section with either a concrete next step or a clear dismissal.
        8. The References section at the bottom must use clickable Markdown links, not raw URLs.
        9. Format all references as Markdown links. Never output raw URLs.

        Style guide:
        {style_guide}

        Platform instructions:
        {instructions[platform]}

        Non-negotiable requirements:
        - Preserve ALL original source URLs exactly as-is.
        - Do not remove or rewrite any URL.
        - Do not invent facts.
        - Return only the polished final content, with no explanation.

        URLs that MUST remain present verbatim in the final output:
        {url_inventory}

        Draft to polish:
        {content}
        """
    ).strip()


def restore_missing_urls(original: str, polished: str, platform: str) -> str:
    """Reattach missing URLs for longer-form platforms before falling back."""
    missing_urls = [url for url in extract_urls(original) if url not in polished]
    if not missing_urls:
        return polished

    if platform == "blog":
        suffix = "\n\n## References\n" + "\n".join(f"- [Source]({url})" for url in missing_urls)
        return polished.rstrip() + suffix

    if platform == "linkedin":
        return polished

    return polished


def validate_polished_content(original: str, polished: str, platform: str) -> bool:
    """Check that the polished output still satisfies key invariants."""
    if not polished.strip():
        return False

    original_urls = extract_urls(original)
    if any(url not in polished for url in original_urls):
        return False

    if platform == "blog" and original.lstrip().startswith("---") and not polished.lstrip().startswith("---"):
        return False

    if platform == "linkedin" and len(polished) > 3000:
        return False

    if platform == "x":
        tweets = [chunk.strip() for chunk in polished.split("\n\n") if chunk.strip()]
        if not 1 <= len(tweets) <= 3:
            return False
        if any(len(tweet) > 280 for tweet in tweets):
            return False

    return True


def polish(content: str, platform: str, style_guide_path: str = str(STYLE_GUIDE_PATH)) -> str:
    """Polish content with Claude Code CLI, falling back to the original text."""
    if not content.strip():
        return content
    if shutil.which("claude") is None:
        return content

    style_guide = load_style_guide(style_guide_path)
    prompt = build_prompt(content, platform, style_guide)

    try:
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
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.warning("Claude polish unavailable for %s: %s", platform, exc)
        return content

    if result.returncode != 0:
        stderr_line = result.stderr.strip().splitlines()[0] if result.stderr.strip() else "unknown error"
        LOGGER.warning("Claude polish failed for %s: %s", platform, stderr_line)
        return content

    polished = result.stdout.strip()
    polished = restore_missing_urls(content, polished, platform)
    if not validate_polished_content(content, polished, platform):
        LOGGER.warning("Claude polish output rejected for %s; using original draft", platform)
        return content
    return polished


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for standalone testing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["linkedin", "blog", "x"], default="linkedin")
    parser.add_argument("--style-guide-path", default=str(STYLE_GUIDE_PATH))
    parser.add_argument("--test", action="store_true", help="Polish a built-in sample payload.")
    return parser


def main() -> int:
    """Run a standalone Claude polish smoke test."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    sample = textwrap.dedent(
        """
        AMD just launched Lemonade, a fast open-source local llm server for gpus and npus. https://lemonade-server.ai

        Other quick read: Qwen3.6-Plus pushes toward real-world agents https://qwen.ai/blog?id=qwen3.6
        """
    ).strip()
    content = sample if args.test else sys.stdin.read().strip()
    print(polish(content, args.platform, style_guide_path=args.style_guide_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


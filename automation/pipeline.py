"""Main entry point for the ClarityStack AI content automation pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import sys
from typing import Any

from dotenv import load_dotenv

try:
    from . import content_generator, fetcher, notify_dispatch, publish_github, publish_linkedin, publish_x
    from .paths import ENV_PATH, LOG_DIR
    from .privacy_scanner import scan
except ImportError:
    import content_generator
    import fetcher
    import notify_dispatch
    import publish_github
    import publish_linkedin
    import publish_x
    from paths import ENV_PATH, LOG_DIR
    from privacy_scanner import scan

LOGGER = logging.getLogger(__name__)


def setup_logging() -> pathlib.Path:
    """Configure console and file logging for the current run."""
    log_dir = LOG_DIR
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"pipeline_{dt.date.today().isoformat()}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    return log_path


def preview_content(content_map: dict[str, str]) -> None:
    """Print generated previews for human approval."""
    print("\nGenerated content preview:\n")
    for platform, content in content_map.items():
        print(f"=== {platform.upper()} ===")
        print(content)
        print()


def request_cli_approval() -> bool:
    """Prompt the operator for publication approval."""
    if not os.isatty(0):
        raise RuntimeError("Approval is required, but no interactive terminal is available.")
    reply = input("Publish all? [y/N]: ").strip().lower()
    return reply in {"y", "yes"}


def redact_generated_content(content_map: dict[str, str]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Run the privacy scanner on generated content and keep the cleaned versions."""
    cleaned_map: dict[str, str] = {}
    findings_map: dict[str, list[str]] = {}

    for platform, content in content_map.items():
        cleaned, findings = scan(content)
        cleaned_map[platform] = cleaned
        findings_map[platform] = findings
        if findings:
            LOGGER.warning("Generated %s content triggered %d redaction(s)", platform, len(findings))

    return cleaned_map, findings_map


def publish_all(content_map: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Publish the approved content to all platforms."""
    github_result = publish_github.publish(content_map["blog"], publish_github.load_credentials())
    linkedin_result = publish_linkedin.publish(content_map["linkedin"], publish_linkedin.load_credentials())
    x_result = publish_x.publish(content_map["x"], publish_x.load_credentials())
    return {
        "github": github_result,
        "linkedin": linkedin_result,
        "x": x_result,
    }


def request_dispatch_approval(content_map: dict[str, str]) -> str:
    """Write review content for Claude Dispatch and return the pending file path."""
    return notify_dispatch.request_approval(content_map)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--manual", action="store_true", help="Run on demand.")
    mode_group.add_argument("--auto", action="store_true", help="Run from a scheduler or agent heartbeat.")
    mode_group.add_argument(
        "--publish-approved",
        action="store_true",
        help="Publish the already approved content from outbox/review/approved/.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate previews without publishing.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum number of fetched items to use.")
    return parser


def main() -> int:
    """Run the full automation pipeline."""
    load_dotenv(ENV_PATH)
    log_path = setup_logging()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    approval_mode = os.getenv("APPROVAL_MODE", "cli").strip().lower()

    if args.publish_approved:
        LOGGER.info("Pipeline started in publish-approved mode")
        approved_content = notify_dispatch.load_review_bundle("approved")
        preview_content(approved_content)
        if args.dry_run:
            LOGGER.info("Dry run enabled; skipping publish-approved execution")
            print(f"Dry run complete. Log written to {log_path}")
            return 0

        results = publish_all(approved_content)
        notify_dispatch.cleanup_review_bundle()
        LOGGER.info("Publish-approved results: %s", json.dumps(results, ensure_ascii=False))
        print(json.dumps({"results": results, "log": str(log_path)}, indent=2, ensure_ascii=False))
        return 0 if all(result["success"] for result in results.values()) else 1

    LOGGER.info("Pipeline started. Mode: %s", "auto" if args.auto else "manual" if args.manual else "default")

    news_items = fetcher.fetch_news(limit=args.limit)
    LOGGER.info("Fetched %d news item(s)", len(news_items))

    raw_payload = json.dumps(news_items, indent=2, ensure_ascii=False)
    _, source_findings = scan(raw_payload)
    if source_findings:
        LOGGER.warning("Fetched payload triggered %d privacy redaction(s)", len(source_findings))

    LOGGER.info("Extracting structured JSON for fetched items")
    structured_items = content_generator.structure_news_items(news_items, limit=5)
    LOGGER.info("Structured extraction completed for %d item(s)", len(structured_items))

    content_map = {
        "linkedin": content_generator.generate(news_items, "linkedin", structured_items=structured_items),
        "blog": content_generator.generate(news_items, "blog", structured_items=structured_items),
        "x": content_generator.generate(news_items, "x", structured_items=structured_items),
    }
    LOGGER.info("Structured assembly completed for %d platform(s)", len(content_map))

    cleaned_map, generated_findings = redact_generated_content(content_map)
    LOGGER.info("Second-pass privacy scan completed")

    preview_content(cleaned_map)

    if args.dry_run:
        LOGGER.info("Dry run enabled; skipping approval and publish")
        print(f"Dry run complete. Log written to {log_path}")
        return 0

    if approval_mode == "dispatch":
        pending_path = request_dispatch_approval(cleaned_map)
        print(f"Dispatch review bundle written to {pending_path}")
        LOGGER.info("Dispatch approval requested")
        return 0

    if not request_cli_approval():
        LOGGER.info("Publication was declined by the operator")
        print("Publishing cancelled.")
        return 0

    results = publish_all(cleaned_map)
    LOGGER.info("Publish results: %s", json.dumps(results, ensure_ascii=False))
    print(json.dumps({"results": results, "log": str(log_path), "redactions": generated_findings}, indent=2, ensure_ascii=False))

    success = all(result["success"] for result in results.values())
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

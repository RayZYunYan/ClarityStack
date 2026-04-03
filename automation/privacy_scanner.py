"""Regex-based redaction for sensitive data before external API calls."""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
import sys
from typing import Any

try:
    from .paths import REDACTION_RULES_PATH
except ImportError:
    from paths import REDACTION_RULES_PATH

LOGGER = logging.getLogger(__name__)


def load_rules(rules_path: str | pathlib.Path) -> dict[str, Any]:
    """Load redaction rules from JSON."""
    with open(pathlib.Path(rules_path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def scan(text: str, rules_path: str | pathlib.Path | None = None) -> tuple[str, list[str]]:
    """Returns (clean_text, list_of_findings)."""
    rules = load_rules(rules_path or REDACTION_RULES_PATH)
    placeholder = rules.get("placeholder", "[REDACTED]")
    findings: list[str] = []
    cleaned = text

    for pattern in rules.get("patterns", []):
        regex = pattern["regex"]
        label = pattern["label"]
        compiled = re.compile(regex)
        matches = list(compiled.finditer(cleaned))
        if not matches:
            continue

        findings.extend([f"Redacted {label} via pattern {regex}"] * len(matches))
        LOGGER.info("Redacted %s using pattern %s (%d matches)", label, regex, len(matches))
        cleaned = compiled.sub(placeholder, cleaned)

    if findings:
        LOGGER.warning("Privacy scanner made %d redaction(s)", len(findings))

    return cleaned, findings


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Path to the input text file.")
    parser.add_argument("--text", help="Inline text to scan.")
    parser.add_argument("--rules-path", default=str(REDACTION_RULES_PATH), help="Path to the rules JSON file.")
    return parser


def main() -> int:
    """Run the privacy scanner as a CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()

    if args.text:
        content = args.text
    elif args.file:
        content = pathlib.Path(args.file).read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    cleaned, findings = scan(content, rules_path=args.rules_path)
    payload = {"cleaned_text": cleaned, "findings": findings}
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

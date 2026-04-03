"""Centralized project paths for the ClarityStack repo."""

from __future__ import annotations

import pathlib

AUTOMATION_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = AUTOMATION_DIR.parent
SITE_DIR = REPO_ROOT / "site"
DOCS_DIR = REPO_ROOT / "docs"
CONFIG_DIR = AUTOMATION_DIR / "config"
LOG_DIR = REPO_ROOT / "logs"
OUTBOX_DIR = REPO_ROOT / "outbox"
REVIEW_DIR = OUTBOX_DIR / "review"
ENV_PATH = REPO_ROOT / ".env"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
STYLE_GUIDE_PATH = CONFIG_DIR / "style_guide.md"
REDACTION_RULES_PATH = CONFIG_DIR / "redaction_rules.json"
PROMPT_TEMPLATE_PATH = CONFIG_DIR / "prompt_template.json"
SITE_POSTS_DIR = SITE_DIR / "_posts"

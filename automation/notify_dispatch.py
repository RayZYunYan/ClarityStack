"""Review bundle helpers for Claude Dispatch approval flow."""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import shutil
import sys

try:
    from .paths import REVIEW_DIR
except ImportError:
    from paths import REVIEW_DIR

LOGGER = logging.getLogger(__name__)
PLATFORM_FILES = {
    "linkedin": "linkedin.txt",
    "blog": "blog.md",
    "x": "x.txt",
}


def ensure_review_dirs(output_dir: str | pathlib.Path = REVIEW_DIR) -> tuple[pathlib.Path, pathlib.Path]:
    """Ensure the pending and approved review directories exist."""
    base = pathlib.Path(output_dir)
    pending_dir = base / "pending"
    approved_dir = base / "approved"
    pending_dir.mkdir(parents=True, exist_ok=True)
    approved_dir.mkdir(parents=True, exist_ok=True)
    return pending_dir, approved_dir


def write_platform_files(content_preview: dict[str, str], target_dir: pathlib.Path) -> dict[str, pathlib.Path]:
    """Persist platform-specific review files."""
    file_map: dict[str, pathlib.Path] = {}
    for platform, filename in PLATFORM_FILES.items():
        path = target_dir / filename
        path.write_text(content_preview.get(platform, ""), encoding="utf-8")
        file_map[platform] = path
    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"platforms": list(content_preview.keys())}, indent=2), encoding="utf-8")
    return file_map


def render_pending_markdown(content_preview: dict[str, str]) -> str:
    """Render a readable markdown file for Dispatch review."""
    sections = [
        "# ClarityStack Review Queue",
        "",
        "## LinkedIn",
        "",
        content_preview.get("linkedin", ""),
        "",
        "## Blog",
        "",
        "````markdown",
        content_preview.get("blog", ""),
        "````",
        "",
        "## X",
        "",
        content_preview.get("x", ""),
        "",
        "---",
        "Reply OK to publish, or reply with edit instructions",
    ]
    return "\n".join(sections).strip() + "\n"


def request_approval(content_preview: dict[str, str], output_dir: str | pathlib.Path = REVIEW_DIR) -> str:
    """Write a Dispatch-friendly pending review bundle and return pending.md."""
    pending_dir, _ = ensure_review_dirs(output_dir)
    write_platform_files(content_preview, pending_dir)
    pending_path = pathlib.Path(output_dir) / "pending.md"
    pending_path.write_text(render_pending_markdown(content_preview), encoding="utf-8")
    (pathlib.Path(output_dir) / ".pending").touch()
    LOGGER.info("Wrote Dispatch review bundle to %s", pending_path)
    return str(pending_path)


def load_review_bundle(state: str = "approved", output_dir: str | pathlib.Path = REVIEW_DIR) -> dict[str, str]:
    """Load content from the pending or approved review bundle."""
    base_dir = pathlib.Path(output_dir) / state
    if not base_dir.exists():
        raise FileNotFoundError(f"Review bundle not found: {base_dir}")

    content_map: dict[str, str] = {}
    for platform, filename in PLATFORM_FILES.items():
        file_path = base_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Missing review content for {platform}: {file_path}")
        content_map[platform] = file_path.read_text(encoding="utf-8")
    return content_map


def promote_pending_to_approved(output_dir: str | pathlib.Path = REVIEW_DIR) -> dict[str, str]:
    """Utility for local testing: copy pending files into approved."""
    pending_dir, approved_dir = ensure_review_dirs(output_dir)
    for filename in list(PLATFORM_FILES.values()) + ["manifest.json"]:
        source = pending_dir / filename
        if source.exists():
            shutil.copy2(source, approved_dir / filename)
    return load_review_bundle("approved", output_dir=output_dir)


def cleanup_review_bundle(output_dir: str | pathlib.Path = REVIEW_DIR) -> None:
    """Remove review artifacts after publishing."""
    base = pathlib.Path(output_dir)
    pending_md = base / "pending.md"
    if pending_md.exists():
        pending_md.unlink()
    for state in ("pending", "approved"):
        state_dir = base / state
        if state_dir.exists():
            for child in state_dir.iterdir():
                if child.is_file():
                    child.unlink()


def build_parser() -> argparse.ArgumentParser:
    """Create a small CLI for manual testing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--promote-pending", action="store_true")
    return parser


def main() -> int:
    """Run a simple manual helper CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    if args.promote_pending:
        content_map = promote_pending_to_approved()
        print(json.dumps(content_map, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


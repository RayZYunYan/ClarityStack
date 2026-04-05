"""Discord bot for ClarityStack article approval workflow."""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import sys

import discord
from dotenv import load_dotenv

try:
    from .paths import ENV_PATH, REVIEW_DIR
    from .notify_dispatch import promote_pending_to_approved
except ImportError:
    from paths import ENV_PATH, REVIEW_DIR
    from notify_dispatch import promote_pending_to_approved

LOGGER = logging.getLogger(__name__)

PENDING_FLAG = REVIEW_DIR / ".pending"
APPROVED_FLAG = REVIEW_DIR / ".approved"
MODIFICATION_REQUEST = REVIEW_DIR / "modification_request.txt"
PENDING_DIR = REVIEW_DIR / "pending"

PLATFORM_FILES = {
    "blog": "blog.md",
    "linkedin": "linkedin.txt",
    "x": "x.txt",
}


def read_preview() -> tuple[str, pathlib.Path | None]:
    """Return (summary_text, blog_path) for Discord preview + attachment."""
    blog = PENDING_DIR / "blog.md"
    target = blog if blog.exists() else next(
        (p for p in sorted(PENDING_DIR.iterdir()) if p.is_file() and p.suffix in {".md", ".txt"}),
        None,
    ) if PENDING_DIR.exists() else None
    if not target:
        return "(no preview available)", None

    text = target.read_text(encoding="utf-8")
    # Strip frontmatter for the summary snippet
    body = text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            body = text[end + 3:].lstrip()
    summary = body[:300] + "\n…" if len(body) > 300 else body
    return summary, target


def apply_modification_with_claude(request: str) -> bool:
    """Call Claude CLI to apply modification request to each platform file. Returns True if any file was updated."""
    if shutil.which("claude") is None:
        LOGGER.warning("claude CLI not found — skipping AI modification")
        return False

    updated = False
    for platform, filename in PLATFORM_FILES.items():
        file_path = PENDING_DIR / filename
        if not file_path.exists():
            continue

        current = file_path.read_text(encoding="utf-8")
        prompt = (
            f"Apply the following modification request to this content. "
            f"Return only the modified content with no explanation or preamble.\n\n"
            f"Modification request: {request}\n\n"
            f"Current content:\n{current}"
        )

        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text", "--model", "sonnet", "--max-turns", "1"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )

        if result.returncode == 0 and result.stdout.strip():
            file_path.write_text(result.stdout.strip(), encoding="utf-8")
            updated = True
            LOGGER.info("Applied modification to %s", filename)
        else:
            LOGGER.warning("Claude modification failed for %s: %s", filename, result.stderr.strip()[:200])

    return updated


def build_bot(channel_id: int, owner_id: int) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        LOGGER.info("Discord bot ready as %s", client.user)
        if PENDING_FLAG.exists():
            channel = client.get_channel(channel_id)
            if channel:
                summary, blog_path = read_preview()
                kwargs = {"file": discord.File(blog_path, filename="blog_preview.md")} if blog_path else {}
                await channel.send(
                    f"**ClarityStack 待审稿**\n\n{summary}\n\n"
                    "回复 `ok` 批准发布，或回复修改需求。",
                    **kwargs
                )
                PENDING_FLAG.unlink()
                LOGGER.info("Sent pending notification and removed .pending flag")

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.channel.id != channel_id:
            return
        if message.author.id != owner_id:
            return

        if message.content.strip().lower() == "ok":
            promote_pending_to_approved()
            APPROVED_FLAG.touch()
            await message.channel.send("✅ 已批准，正在发布...")
            LOGGER.info("Article approved — triggering publish-approved")
            result = subprocess.run(
                [sys.executable, "-m", "automation.pipeline", "--publish-approved"],
                capture_output=True,
                text=True,
                cwd=str(REVIEW_DIR.parent.parent),
            )
            if result.returncode == 0:
                await message.channel.send("🚀 发布成功")
                LOGGER.info("publish-approved completed successfully")
            else:
                await message.channel.send(f"⚠️ 发布失败：{result.stderr.strip()[-200:]}")
                LOGGER.error("publish-approved failed: %s", result.stderr.strip())

        else:
            MODIFICATION_REQUEST.write_text(message.content, encoding="utf-8")
            await message.channel.send("✍️ 正在调用 Claude 应用修改，请稍候...")
            LOGGER.info("Applying modification: %s", message.content[:100])

            updated = apply_modification_with_claude(message.content)

            if updated:
                summary, blog_path = read_preview()
                kwargs = {"file": discord.File(blog_path, filename="blog_preview.md")} if blog_path else {}
                await message.channel.send(
                    f"📝 修改完成，更新后预览：\n\n{summary}\n\n"
                    "回复 `ok` 发布，或继续发送修改需求。",
                    **kwargs
                )
            else:
                await message.channel.send(
                    "⚠️ Claude CLI 不可用，修改需求已保存到文件。请手动修改后回复 `ok`。"
                )

    return client


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv(ENV_PATH)

    token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    owner_id = os.getenv("DISCORD_OWNER_ID")

    if not token or not channel_id or not owner_id:
        raise RuntimeError("DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, and DISCORD_OWNER_ID must be set in .env")

    bot = build_bot(int(channel_id), int(owner_id))
    bot.run(token)


if __name__ == "__main__":
    main()

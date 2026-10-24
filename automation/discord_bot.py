"""Discord bot for ClarityStack article approval workflow."""

from __future__ import annotations

import logging
import os
import pathlib
import subprocess
import sys

import discord
from dotenv import load_dotenv

try:
    from .anthropic_client import call_anthropic, get_anthropic_api_key
    from .paths import ENV_PATH, REVIEW_DIR
    from .notify_dispatch import cleanup_review_bundle, promote_pending_to_approved
except ImportError:
    from anthropic_client import call_anthropic, get_anthropic_api_key
    from paths import ENV_PATH, REVIEW_DIR
    from notify_dispatch import cleanup_review_bundle, promote_pending_to_approved

LOGGER = logging.getLogger(__name__)

PENDING_FLAG = REVIEW_DIR / ".pending"
APPROVED_FLAG = REVIEW_DIR / ".approved"
NO_CONTENT_FLAG = REVIEW_DIR / ".no_content"
ERROR_FLAG = REVIEW_DIR / ".error"
MODIFICATION_REQUEST = REVIEW_DIR / "modification_request.txt"
PENDING_DIR = REVIEW_DIR / "pending"

# Whole-message matches only, so "reject the second paragraph" is still a modification request.
APPROVE_COMMANDS = {"ok", "approve"}
DISCARD_COMMANDS = {"reject", "skip", "cancel", "拒绝", "跳过", "取消"}

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
    """Call the Anthropic API to apply modification requests."""
    if not get_anthropic_api_key():
        LOGGER.warning("ANTHROPIC_API_KEY is not configured — skipping AI modification")
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

        try:
            rewritten = call_anthropic(prompt, timeout=90, max_tokens=2200)
        except Exception as exc:
            LOGGER.warning("Claude modification failed for %s: %s", filename, exc)
            continue

        if rewritten.strip():
            file_path.write_text(rewritten.strip(), encoding="utf-8")
            updated = True
            LOGGER.info("Applied modification to %s", filename)

    return updated


def build_bot(channel_id: int, owner_id: int) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        LOGGER.info("Discord bot ready as %s", client.user)
        channel = client.get_channel(channel_id)
        if not channel:
            return

        if ERROR_FLAG.exists():
            detail = ERROR_FLAG.read_text(encoding="utf-8").strip()[:1500] or "（无详细信息）"
            await channel.send(f"⚠️ 管道已中止，本次未生成稿件：\n```\n{detail}\n```")
            ERROR_FLAG.unlink()
            LOGGER.info("Sent pipeline error notification")
            await client.close()
            return

        if NO_CONTENT_FLAG.exists():
            await channel.send("📭 今日无新内容：所有数据源均不可用或近期已覆盖，跳过发布。")
            NO_CONTENT_FLAG.unlink()
            LOGGER.info("Sent no-content notification")
            await client.close()
            return

        if PENDING_FLAG.exists():
            summary, blog_path = read_preview()
            kwargs = {"file": discord.File(blog_path, filename="blog_preview.md")} if blog_path else {}
            await channel.send(
                f"**ClarityStack 待审稿**\n\n{summary}\n\n"
                "回复 `ok` 批准发布，回复 `拒绝` 丢弃本次稿件，或回复修改需求。",
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

        text = message.content.strip().lower()

        if text in DISCARD_COMMANDS:
            cleanup_review_bundle()
            for path in (PENDING_FLAG, MODIFICATION_REQUEST):
                if path.exists():
                    path.unlink()
            await message.channel.send("🗑️ 已丢弃本次稿件，不会发布。")
            LOGGER.info("Review bundle discarded by owner")
            await client.close()

        elif text in APPROVE_COMMANDS:
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
                await client.close()
            else:
                await message.channel.send(
                    f"⚠️ 发布失败：{result.stderr.strip()[-200:]}\n未成功的平台稿件已保留，回复 `ok` 重试。"
                )
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
                    "回复 `ok` 发布，回复 `拒绝` 丢弃，或继续发送修改需求。",
                    **kwargs
                )
            else:
                await message.channel.send("⚠️ Claude API 不可用，修改需求已保存到文件。请手动修改后回复 `ok`。")

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

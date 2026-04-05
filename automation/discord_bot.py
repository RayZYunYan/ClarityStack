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
    from .paths import ENV_PATH, REVIEW_DIR
except ImportError:
    from paths import ENV_PATH, REVIEW_DIR

LOGGER = logging.getLogger(__name__)

PENDING_FLAG = REVIEW_DIR / ".pending"
APPROVED_FLAG = REVIEW_DIR / ".approved"
MODIFICATION_REQUEST = REVIEW_DIR / "modification_request.txt"
PENDING_DIR = REVIEW_DIR / "pending"


def read_preview() -> str:
    """Read the first content file found in the pending directory."""
    if not PENDING_DIR.exists():
        return "(no preview available)"
    for path in sorted(PENDING_DIR.iterdir()):
        if path.is_file() and path.suffix in {".md", ".txt"}:
            text = path.read_text(encoding="utf-8")
            return text[:1800] + "\n…(truncated)" if len(text) > 1800 else text
    return "(no preview available)"


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
                preview = read_preview()
                await channel.send(
                    f"**ClarityStack 待审稿**\n\n{preview}\n\n"
                    "回复 `ok` 批准发布，或回复修改需求。"
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
            await message.channel.send("📝 已记录修改需求")
            LOGGER.info("Modification request saved to %s", MODIFICATION_REQUEST)

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

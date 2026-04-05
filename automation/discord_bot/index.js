/**
 * ClarityStack Discord bot — Node.js rewrite for NemoClaw sandbox compatibility.
 * Replaces automation/discord_bot.py (Python blocked by Landlock policy).
 *
 * Workflow:
 *   1. On ready: if outbox/review/.pending exists, send blog.md preview and remove flag.
 *   2. Owner replies "ok" → touch .approved, run python pipeline --publish-approved.
 *   3. Owner replies anything else → call Claude CLI to modify platform files, send updated preview.
 */

"use strict";

const { Client, GatewayIntentBits } = require("discord.js");
const { execFileSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const { HttpsProxyAgent } = require("https-proxy-agent");
require("dotenv").config({ path: path.resolve(__dirname, "../../.env") });

// ── Paths (mirrors automation/paths.py) ──────────────────────────────────────
const REPO_ROOT    = path.resolve(__dirname, "../..");
const REVIEW_DIR   = path.join(REPO_ROOT, "outbox", "review");
const PENDING_DIR  = path.join(REVIEW_DIR, "pending");
const PENDING_FLAG = path.join(REVIEW_DIR, ".pending");
const APPROVED_FLAG = path.join(REVIEW_DIR, ".approved");
const MODIFICATION_REQUEST = path.join(REVIEW_DIR, "modification_request.txt");

const PLATFORM_FILES = {
  blog:     "blog.md",
  linkedin: "linkedin.txt",
  x:        "x.txt",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function readPreview() {
  const blog = path.join(PENDING_DIR, "blog.md");
  let target = null;

  if (fs.existsSync(blog)) {
    target = blog;
  } else if (fs.existsSync(PENDING_DIR)) {
    const files = fs.readdirSync(PENDING_DIR)
      .filter(f => /\.(md|txt)$/.test(f))
      .sort();
    if (files.length) target = path.join(PENDING_DIR, files[0]);
  }

  if (!target) return "(no preview available)";
  const text = fs.readFileSync(target, "utf8");
  return text.length > 1800 ? text.slice(0, 1800) + "\n…(truncated)" : text;
}

function which(cmd) {
  try {
    execFileSync("which", [cmd], { stdio: "pipe" });
    return true;
  } catch {
    return false;
  }
}

function applyModificationWithClaude(request) {
  if (!which("claude")) {
    console.warn("claude CLI not found — skipping AI modification");
    return false;
  }

  let updated = false;
  for (const [platform, filename] of Object.entries(PLATFORM_FILES)) {
    const filePath = path.join(PENDING_DIR, filename);
    if (!fs.existsSync(filePath)) continue;

    const current = fs.readFileSync(filePath, "utf8");
    const prompt =
      `Apply the following modification request to this content. ` +
      `Return only the modified content with no explanation or preamble.\n\n` +
      `Modification request: ${request}\n\n` +
      `Current content:\n${current}`;

    const result = spawnSync(
      "claude",
      ["-p", prompt, "--output-format", "text", "--model", "sonnet", "--max-turns", "1"],
      { encoding: "utf8", timeout: 90_000 }
    );

    if (result.status === 0 && result.stdout.trim()) {
      fs.writeFileSync(filePath, result.stdout.trim(), "utf8");
      updated = true;
      console.info(`Applied modification to ${filename}`);
    } else {
      console.warn(`Claude modification failed for ${filename}: ${(result.stderr || "").slice(0, 200)}`);
    }
  }
  return updated;
}

// ── Bot ───────────────────────────────────────────────────────────────────────

const token     = process.env.DISCORD_BOT_TOKEN;
const channelId = process.env.DISCORD_CHANNEL_ID;
const ownerId   = process.env.DISCORD_OWNER_ID;

if (!token || !channelId || !ownerId) {
  console.error("DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, and DISCORD_OWNER_ID must be set in .env");
  process.exit(1);
}

const proxyUrl = process.env.HTTPS_PROXY || process.env.https_proxy;
const wsOptions = proxyUrl ? { agent: new HttpsProxyAgent(proxyUrl) } : {};

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
  ws: wsOptions,
});

client.once("ready", async () => {
  console.info(`Discord bot ready as ${client.user.tag}`);

  if (fs.existsSync(PENDING_FLAG)) {
    const channel = client.channels.cache.get(channelId);
    if (channel) {
      const preview = readPreview();
      await channel.send(
        `**ClarityStack 待审稿**\n\n${preview}\n\n` +
        "回复 `ok` 批准发布，或回复修改需求。"
      );
      fs.unlinkSync(PENDING_FLAG);
      console.info("Sent pending notification and removed .pending flag");
    }
  }
});

client.on("messageCreate", async (message) => {
  if (message.author.bot) return;
  if (message.channelId !== channelId) return;
  if (message.author.id !== ownerId) return;

  const text = message.content.trim().toLowerCase();

  if (text === "ok") {
    // Approve and publish
    fs.closeSync(fs.openSync(APPROVED_FLAG, "a")); // touch
    await message.channel.send("✅ 已批准，正在发布...");
    console.info("Article approved — running pipeline --publish-approved");

    const result = spawnSync(
      "python3",
      ["-m", "automation.pipeline", "--publish-approved"],
      { encoding: "utf8", cwd: REPO_ROOT }
    );

    if (result.status === 0) {
      await message.channel.send("🚀 发布成功");
      console.info("publish-approved completed successfully");
    } else {
      const errTail = (result.stderr || "").slice(-200);
      await message.channel.send(`⚠️ 发布失败：${errTail}`);
      console.error("publish-approved failed:", result.stderr);
    }
  } else {
    // Modification request
    fs.writeFileSync(MODIFICATION_REQUEST, message.content, "utf8");
    await message.channel.send("✍️ 正在调用 Claude 应用修改，请稍候...");
    console.info(`Applying modification: ${message.content.slice(0, 100)}`);

    const updated = applyModificationWithClaude(message.content);

    if (updated) {
      const preview = readPreview();
      await message.channel.send(
        `📝 修改完成，更新后预览：\n\n${preview}\n\n` +
        "回复 `ok` 发布，或继续发送修改需求。"
      );
    } else {
      await message.channel.send(
        "⚠️ Claude CLI 不可用，修改需求已保存到文件。请手动修改后回复 `ok`。"
      );
    }
  }
});

client.login(token).catch((err) => {
  console.error("Failed to login:", err);
  process.exit(1);
});

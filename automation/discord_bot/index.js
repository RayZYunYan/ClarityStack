/**
 * ClarityStack Discord bot — Node.js rewrite for NemoClaw sandbox compatibility.
 * Replaces automation/discord_bot.py (Python blocked by Landlock policy).
 *
 * Workflow:
 *   1. On ready: if outbox/review/.pending exists, send blog.md preview and remove flag.
 *   2. Owner replies "ok" → touch .approved, run python pipeline --publish-approved.
 *   3. Owner replies anything else → call Anthropic API to modify platform files, send updated preview.
 */

"use strict";

const { Client, GatewayIntentBits } = require("discord.js");
const { spawnSync } = require("child_process");
const fs = require("fs");
const https = require("https");
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

const PYTHON_CANDIDATES = [
  process.env.PYTHON_EXECUTABLE,
  "python3",
  "python",
].filter(Boolean);

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

function callAnthropic(prompt, timeoutMs = 90_000) {
  const apiKey = process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY;
  if (!apiKey) {
    throw new Error("ANTHROPIC_API_KEY is not configured");
  }

  const payload = JSON.stringify({
    model: process.env.ANTHROPIC_MODEL || "claude-haiku-4-5",
    max_tokens: 2200,
    messages: [{ role: "user", content: prompt }],
  });

  const agent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;

  return new Promise((resolve, reject) => {
    const req = https.request(
      "https://api.anthropic.com/v1/messages",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "anthropic-version": "2023-06-01",
          "x-api-key": apiKey,
          "content-length": Buffer.byteLength(payload),
        },
        agent,
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode < 200 || res.statusCode >= 300) {
            reject(new Error(`Anthropic HTTP ${res.statusCode}: ${body.slice(0, 300)}`));
            return;
          }

          try {
            const parsed = JSON.parse(body);
            const text = (parsed.content || [])
              .filter((block) => block && block.type === "text" && block.text)
              .map((block) => block.text.trim())
              .join("\n")
              .trim();
            if (!text) {
              reject(new Error("Anthropic returned no text content"));
              return;
            }
            resolve(text);
          } catch (error) {
            reject(error);
          }
        });
      }
    );

    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error("Anthropic request timed out"));
    });
    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

function runPipelinePublishApproved() {
  for (const command of PYTHON_CANDIDATES) {
    const result = spawnSync(
      command,
      ["-m", "automation.pipeline", "--publish-approved"],
      { encoding: "utf8", cwd: REPO_ROOT }
    );

    if (result.error && result.error.code === "ENOENT") {
      continue;
    }

    return { command, result };
  }

  return {
    command: PYTHON_CANDIDATES[0] || "python3",
    result: {
      status: null,
      stderr: "No usable Python executable found. Set PYTHON_EXECUTABLE in .env.",
    },
  };
}

async function applyModificationWithClaude(request) {
  if (!(process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY)) {
    console.warn("ANTHROPIC_API_KEY is not configured — skipping AI modification");
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

    try {
      const rewritten = await callAnthropic(prompt, 90_000);
      if (!rewritten.trim()) {
        continue;
      }
      fs.writeFileSync(filePath, rewritten.trim(), "utf8");
      updated = true;
      console.info(`Applied modification to ${filename}`);
    } catch (error) {
      console.warn(`Claude modification failed for ${filename}: ${String(error).slice(0, 300)}`);
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

    const { command, result } = runPipelinePublishApproved();

    if (result.status === 0) {
      await message.channel.send("🚀 发布成功");
      console.info(`publish-approved completed successfully with ${command}`);
    } else {
      const errTail = (result.stderr || "unknown error").slice(-200);
      await message.channel.send(`⚠️ 发布失败：${errTail}`);
      console.error(`publish-approved failed with ${command}:`, result.stderr);
    }
  } else {
    // Modification request
    fs.writeFileSync(MODIFICATION_REQUEST, message.content, "utf8");
    await message.channel.send("✍️ 正在调用 Claude API 修改，请稍候...");
    console.info(`Applying modification: ${message.content.slice(0, 100)}`);

    const updated = await applyModificationWithClaude(message.content);

    if (updated) {
      const preview = readPreview();
      await message.channel.send(
        `📝 修改完成，更新后预览：\n\n${preview}\n\n` +
        "回复 `ok` 发布，或继续发送修改需求。"
      );
    } else {
      await message.channel.send(
        "⚠️ Claude API 不可用，修改需求已保存到文件。请手动修改后回复 `ok`。"
      );
    }
  }
});

client.login(token).catch((err) => {
  console.error("Failed to login:", err);
  process.exit(1);
});

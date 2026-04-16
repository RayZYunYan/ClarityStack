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
const PENDING_FLAG    = path.join(REVIEW_DIR, ".pending");
const NO_CONTENT_FLAG = path.join(REVIEW_DIR, ".no_content");
const APPROVED_FLAG   = path.join(REVIEW_DIR, ".approved");
const MODIFICATION_REQUEST = path.join(REVIEW_DIR, "modification_request.txt");

const PLATFORM_FILES = {
  blog:     "blog.md",
  linkedin: "linkedin.txt",
  x:        "x.txt",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseFrontmatter(text) {
  const match = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!match) return { meta: {}, body: text };
  const meta = {};
  for (const line of match[1].split("\n")) {
    const [key, ...rest] = line.split(":");
    if (key && rest.length) meta[key.trim()] = rest.join(":").trim().replace(/^["']|["']$/g, "");
  }
  return { meta, body: match[2].trim() };
}

function splitIntoChunks(text, maxLen = 1900) {
  const chunks = [];
  let remaining = text;
  while (remaining.length > maxLen) {
    let cut = remaining.lastIndexOf("\n\n", maxLen);
    if (cut < 800) cut = remaining.lastIndexOf("\n", maxLen);
    if (cut < 100) cut = maxLen;
    chunks.push(remaining.slice(0, cut).trimEnd());
    remaining = remaining.slice(cut).trimStart();
  }
  if (remaining.trim()) chunks.push(remaining.trim());
  return chunks;
}

function readBlogFile() {
  const blog = path.join(PENDING_DIR, "blog.md");
  if (!fs.existsSync(blog)) return null;
  return fs.readFileSync(blog, "utf8");
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

function scheduleShutdown(delaySec = 3) {
  console.info(`Scheduling shutdown in ${delaySec}s`);
  setTimeout(() => {
    console.info("Bot shutting down — task complete.");
    client.destroy();
    process.exit(0);
  }, delaySec * 1000);
}

async function checkNoContent() {
  if (!fs.existsSync(NO_CONTENT_FLAG)) return;
  const channel = client.channels.cache.get(channelId);
  if (!channel) return;
  await channel.send("📭 今日无新内容：所有数据源均不可用或近期已覆盖，跳过发布。");
  fs.unlinkSync(NO_CONTENT_FLAG);
  console.info("Sent no-content notification");
  scheduleShutdown(3);
}

async function checkPending() {
  if (!fs.existsSync(PENDING_FLAG)) return;
  const channel = client.channels.cache.get(channelId);
  if (!channel) return;

  const raw = readBlogFile();
  if (!raw) {
    await channel.send("⚠️ 找不到 blog.md，请检查 pending 目录。");
    fs.unlinkSync(PENDING_FLAG);
    return;
  }

  const { meta, body } = parseFrontmatter(raw);
  const title    = meta.title || "（无标题）";
  const date     = meta.date  || "（无日期）";
  const wordCount = body.split(/\s+/).filter(Boolean).length;
  const firstPara = body.split(/\n\n+/)[0].replace(/^#+\s*/, "").slice(0, 200);

  // 1. 摘要卡片
  await channel.send(
    `**ClarityStack 待审稿**\n\n` +
    `**标题：** ${title}\n` +
    `**日期：** ${date}\n` +
    `**字数：** ${wordCount} 词\n\n` +
    `> ${firstPara}\n\n` +
    `正文见下方 ↓（附件为原始 .md 文件）`
  );

  // 2. 正文分段发送（Discord 原生渲染 Markdown）
  const chunks = splitIntoChunks(body);
  for (const chunk of chunks) {
    await channel.send(chunk);
  }

  // 3. 附上原始文件
  const blogPath = path.join(PENDING_DIR, "blog.md");
  await channel.send({
    content: "---\n回复 `ok` 批准发布，或直接发送修改需求。",
    files: [{ attachment: blogPath, name: `blog-${date}.md` }],
  });

  fs.unlinkSync(PENDING_FLAG);
  console.info("Sent pending notification and removed .pending flag");
}

client.once("ready", async () => {
  console.info(`Discord bot ready as ${client.user.tag}`);
  await checkNoContent();
  await checkPending();
  setInterval(async () => { await checkNoContent(); await checkPending(); }, 30_000);
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
      scheduleShutdown(3);
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

    let updated;
    try {
      updated = applyModificationWithClaude(message.content);
    } catch (err) {
      console.error(`Modification error: ${err.message}`);
      await message.channel.send(`⚠️ 修改失败：${err.message}`);
      return;
    }

    if (updated) {
      await message.channel.send("📝 修改完成，完整预览如下：");

      // Blog full content in chunks
      const blogRaw = readBlogFile();
      if (blogRaw) {
        await message.channel.send("**── BLOG ──**");
        for (const chunk of splitIntoChunks(blogRaw)) {
          await message.channel.send(chunk);
        }
      }

      // LinkedIn full content
      const linkedinPath = path.join(PENDING_DIR, PLATFORM_FILES.linkedin);
      if (fs.existsSync(linkedinPath)) {
        const liContent = fs.readFileSync(linkedinPath, "utf8").trim();
        await message.channel.send("**── LINKEDIN ──**");
        for (const chunk of splitIntoChunks(liContent)) {
          await message.channel.send(chunk);
        }
      }

      await message.channel.send("---\n回复 `ok` 发布，或继续发送修改需求。");
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

# AI Content Automation Pipeline — Codex Task Spec

## Architecture overview

NemoClaw sandbox (on Mac mini) runs an OpenClaw agent powered by Gemini Flash (free tier). The agent fetches AI news daily, summarizes with Gemini, sends clean data to Claude for polishing, then publishes to GitHub blog + LinkedIn + X after human approval.

**Cost: ~$0** (Gemini free tier + Claude Pro existing + all open source tooling. X API may need a small credit top-up if free tier posting is unavailable on your current pay-per-use plan.)

---

## Prerequisites

**Already done:**
- [x] GitHub repo: `RayZYunYan/ClarityStack` (https://github.com/RayZYunYan/ClarityStack.git)
- [x] GitHub Pages enabled (source: GitHub Actions)
- [x] GitHub Environment `production` with required reviewer configured
- [x] Gemini API key (free tier, from aistudio.google.com)
- [x] X/Twitter App configured (Web App / Automated Bot, Read+Write, OAuth 2.0). Client ID and Secret in `.env`
- [x] LinkedIn App configured (Share on LinkedIn / w_member_social approved). Credentials in `.env`
- [x] All secrets stored in local `.env`

**Still needed (not blocking Codex):**
- [ ] Add X API credit ($5) before first real post
- [ ] Install Docker Desktop on Mac mini (for NemoClaw — only needed when deploying to production)

**Dev environment:** Windows (current) → Mac mini (production server later). Codex writes all code on Windows. NemoClaw sandbox setup (Task 1) is a manual step done on the Mac mini when ready to deploy — Codex does NOT execute it, only documents the steps.

---

## Task 1: NemoClaw sandbox setup (MANUAL — not for Codex)

**Goal:** Install NemoClaw on Mac mini, configure with Gemini Flash as the inference provider.
**When:** After all code is written and tested on Windows, do this on the Mac mini to set up the production environment.

**Steps:**

1. Install NemoClaw:
```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
```

2. During `nemoclaw onboard` wizard:
   - Sandbox name: `ai-pipeline`
   - Inference provider: choose **Google Gemini**
   - Model: `gemini-2.5-flash`
   - Enter Gemini API key when prompted
   - Accept default network policy presets

3. After onboard, add network whitelist rules. Edit the sandbox policy YAML at:
```
$(npm root -g)/nemoclaw/nemoclaw-blueprint/policies/openclaw-sandbox.yaml
```

Add these entries to `network_policies`:
```yaml
# AI news sources
- host: "export.arxiv.org"
  methods: ["GET"]
- host: "api.github.com"
  methods: ["GET"]
- host: "hacker-news.firebaseio.com"
  methods: ["GET"]
- host: "news.ycombinator.com"
  methods: ["GET"]

# LLM APIs (routed through OpenShell gateway)
- host: "generativelanguage.googleapis.com"
  methods: ["POST"]
- host: "api.anthropic.com"
  methods: ["POST"]

# Publishing APIs
- host: "api.linkedin.com"
  methods: ["POST", "GET"]
- host: "api.x.com"
  methods: ["POST"]
- host: "api.github.com"
  methods: ["POST", "PUT", "GET"]
```

4. Connect to sandbox and verify:
```bash
nemoclaw ai-pipeline connect
nemoclaw ai-pipeline status
```

**Deliverable:** Running NemoClaw sandbox with Gemini inference and correct network policies.

---

## Task 2: News fetcher module

**Goal:** Python script that fetches AI-related content from multiple sources, returns structured data with original links.

**File:** `fetcher.py`

**Sources to implement:**
- **ArXiv** — CS.AI and CS.CL categories, last 24 hours, via ArXiv API (`export.arxiv.org/api/query`)
- **GitHub Trending** — Scrape trending repos filtered by ML/AI topics
- **Hacker News** — Top stories via Firebase API, filtered by AI/ML keywords

**Output format (JSON):**
```json
[
  {
    "title": "Paper or article title",
    "source": "arxiv|github|hackernews",
    "url": "https://original-link.com",
    "summary": "Brief 2-3 sentence summary from source",
    "date": "2026-04-02",
    "relevance_score": 0.85
  }
]
```

**Requirements:**
- Use only Python standard library + `requests`
- Deduplicate by URL
- Return top 5-10 items sorted by relevance
- Include original URL for every item (this is critical — we publish links alongside summaries)

**Deliverable:** `fetcher.py` that can be run standalone and outputs JSON to stdout.

---

## Task 3: Privacy scanner

**Goal:** Regex-based redaction that strips sensitive data before sending to any external API.

**File:** `automation/privacy_scanner.py`

**Redaction rules (load from `automation/config/redaction_rules.json`):**
```json
{
  "patterns": [
    {"regex": "sk-[a-zA-Z0-9]{20,}", "label": "API key"},
    {"regex": "ghp_[a-zA-Z0-9]{36}", "label": "GitHub token"},
    {"regex": "nvapi-[a-zA-Z0-9-]+", "label": "NVIDIA key"},
    {"regex": "/Users/[a-zA-Z0-9._-]+", "label": "Local path"},
    {"regex": "AIza[a-zA-Z0-9_-]{35}", "label": "Google API key"}
  ],
  "placeholder": "[REDACTED]"
}
```

**Interface:**
```python
def scan(text: str, rules_path: str = "automation/config/redaction_rules.json") -> tuple[str, list[str]]:
    """Returns (clean_text, list_of_findings)"""
```

**Requirements:**
- Log all redactions (what pattern matched, not the actual value)
- Return both cleaned text and a report of what was found
- If any redaction fires, log a warning

**Deliverable:** `automation/privacy_scanner.py` with `scan()` function.

---

## Task 4: Content generator (Claude integration)

**Goal:** Takes cleaned news summaries, generates platform-specific posts using Claude API.

**File:** `automation/content_generator.py`

**Platforms and format:**

### LinkedIn post
- Professional tone, 1-3 paragraphs
- Include 2-3 emoji sparingly
- End with "Read more: [link]" for each source
- Add 3-5 relevant hashtags
- Max 3000 characters

### GitHub blog post (Markdown)
- Technical depth, structured with headers
- Include code snippets or key findings if relevant
- Full source links as references at bottom
- Frontmatter with title, date, tags
- No character limit

### X thread
- 1-3 tweets, each under 280 characters
- First tweet hooks the reader
- Last tweet has the source link
- Concise, punchy tone

**Interface:**
```python
def generate(
    news_items: list[dict],
    platform: str,  # "linkedin" | "blog" | "x"
    style_file: str = "automation/config/style_guide.md"
) -> str:
```

**Requirements:**
- Use Claude API (api.anthropic.com) with model `claude-sonnet-4-6`
- Load style guide from `automation/config/style_guide.md` for tone/voice consistency
- Always include original source URLs in output
- Privacy scanner must run on input BEFORE calling Claude

**Deliverable:** `automation/content_generator.py` + `automation/config/style_guide.md` template.

---

## Task 5: Platform publishers

**Goal:** Separate modules to publish content to each platform.

### 5a. GitHub blog publisher (`automation/publish_github.py`)
- Create markdown file in `site/_posts/` directory format (`YYYY-MM-DD-title.md`)
- Commit and push to the `ClarityStack` repo (https://github.com/RayZYunYan/ClarityStack.git)
- This triggers GitHub Actions → GitHub Pages deployment
- Use GitHub API (not git CLI) so it works from within the sandbox

### 5b. LinkedIn publisher (`automation/publish_linkedin.py`)
- Use LinkedIn API v2 to create a share/post
- Include text + article URL
- Handle OAuth token refresh

### 5c. X publisher (`automation/publish_x.py`)
- Use X API v2 to create tweets (POST /2/tweets)
- If content is a thread, post sequentially with `reply_to` chaining
- X API is now pay-per-use (credits). Posting costs are minimal (~$0.01/post)
- Check credit balance before posting; warn if low
- Handle rate limits gracefully

**Shared interface:**
```python
def publish(content: str, credentials: dict) -> dict:
    """Returns {"success": bool, "url": str, "error": str|None}"""
```

**Requirements:**
- Each publisher is independent and can be tested separately
- All credentials loaded from environment variables, never hardcoded
- Dry-run mode: `--dry-run` flag prints what would be published without actually posting

**Deliverable:** Three publisher scripts, each runnable standalone.

---

## Task 6: Orchestrator + approval flow

**Goal:** Main pipeline script that ties everything together with human approval gate.

**File:** `automation/pipeline.py`

**Flow:**
```
1. Run fetcher → get news items
2. Run privacy scanner on raw data
3. Run content generator for each platform
4. Run privacy scanner on generated content (second pass)
5. Show preview + request human approval
6. If approved → run publishers
7. Log results
```

**Approval mechanism (choose simplest working approach):**

Option A — CLI prompt:
```
Generated content preview:
---
[LinkedIn post preview]
[Blog post preview]
[X thread preview]
---
Publish all? [y/N]:
```

Option B — If OpenClaw Dispatch/Telegram bridge is configured, send preview there and wait for reply.

**Scheduling:**
- The script should be callable via cron or OpenClaw's heartbeat scheduler
- Suggested schedule: once daily at 9am local time
- Add a `--manual` flag for on-demand runs

**Logging:**
- Write to `logs/pipeline_YYYY-MM-DD.log`
- Record: items fetched, items selected, redactions made, content generated, publish results

**Deliverable:** `automation/pipeline.py` as the single entry point.

---

## Task 7: GitHub Actions workflow

**Goal:** CI/CD for the blog that requires environment approval before deploy.

**File:** `.github/workflows/deploy.yml`

```yaml
name: Deploy Blog

on:
  push:
    branches: [main]
    paths: ['site/**']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Jekyll/Hugo site
        # (choose static site generator)
      - uses: actions/upload-pages-artifact@v3

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production  # This triggers the approval gate
    permissions:
      pages: write
      id-token: write
    steps:
      - uses: actions/deploy-pages@v4
```

**Requirements:**
- Blog only deploys when you approve in GitHub
- Use Jekyll (simplest for GitHub Pages) with a clean minimal theme
- Include basic `site/_config.yml`, `site/index.md`, and `site/_layouts/post.html`

**Deliverable:** Complete GitHub Actions workflow + Jekyll site skeleton.

---

## Task 8: OpenClaw skill file

**Goal:** Package the pipeline as an OpenClaw skill so the agent can run it autonomously.

**File:** `SKILL.md`

The skill should instruct the OpenClaw agent to:
1. Run `pipeline.py --auto` daily via heartbeat
2. On failures, retry once after 30 minutes
3. Log all runs
4. Notify via configured messaging bridge on completion

**Deliverable:** `SKILL.md` following OpenClaw skill format conventions.

---

## File structure

```text
ai-pipeline/
├── README.md                   # Project overview
├── .env.example                # Safe template for secrets
├── .gitignore                  # Ignore local secrets and build artifacts
├── automation/
│   ├── pipeline.py             # Main orchestrator
│   ├── fetcher.py              # News fetcher
│   ├── privacy_scanner.py      # Redaction engine
│   ├── content_generator.py    # Draft generation
│   ├── publish_github.py       # GitHub blog publisher
│   ├── publish_linkedin.py     # LinkedIn publisher
│   ├── publish_x.py            # X/Twitter publisher
│   ├── notify_dispatch.py      # Dispatch approval helper
│   ├── polish_with_claude.py   # Claude Code polish step
│   └── config/
│       ├── redaction_rules.json
│       └── style_guide.md
├── docs/
│   ├── codex-tasks.md          # Build checklist / implementation notes
│   └── SKILL.md                # OpenClaw skill definition
├── logs/                       # Pipeline logs
├── outbox/                     # Manual drafts + review bundles
└── site/                       # GitHub Pages repo contents
    ├── _config.yml
    ├── _includes/
    ├── _layouts/
    ├── _posts/
    ├── assets/
    ├── Gemfile
    ├── about.md
    └── index.md
```

---

## Execution order for Codex

**Codex writes these (in order):**
1. **Task 7** — Blog repo skeleton + GitHub Actions (no dependencies)
2. **Task 2** — Fetcher (standalone, testable)
3. **Task 3** — Privacy scanner (standalone, testable)
4. **Task 4** — Content generator (depends on 3)
5. **Task 5** — Publishers (standalone each, testable with `--dry-run`)
6. **Task 6** — Orchestrator (integrates 2-5)
7. **Task 8** — OpenClaw skill file

**Human does these manually (on Mac mini, later):**
8. **Task 1** — NemoClaw sandbox setup + deploy code into sandbox

---

## Notes for Codex

- All Python code should be Python 3.11+ compatible
- Use `python-dotenv` for env var loading
- Every module must be runnable standalone for testing
- Use `argparse` for CLI interfaces
- Include `--dry-run` flags on all publishers and the orchestrator
- Write docstrings and type hints
- No hardcoded API keys anywhere — always from env vars
- The privacy scanner MUST run before AND after content generation




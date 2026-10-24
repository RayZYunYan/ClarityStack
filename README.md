# ClarityStack

ClarityStack is an automated AI news pipeline that fetches papers, repos, and news daily, runs privacy checks, extracts structured JSON, assembles platform-specific prose, and publishes — with human approval via Discord before anything goes live.

## Repo layout

```text
.
├── automation/        # Python pipeline, publishers, Discord bot, structured prompts, config
├── site/              # Jekyll content source: posts, layouts, assets, pages
├── docs/              # Project notes and migration docs
├── .github/           # GitHub Actions workflows
├── logs/              # Pipeline run logs
├── outbox/            # Review bundles and manual drafts
├── Gemfile            # Root Jekyll dependencies for Cloudflare/GitHub builds
├── _config.yml        # Root Jekyll config, using source: site
├── .env               # Runtime secrets (local only)
└── .env.example       # Safe template for commits
```

## Runtime commands

Install Python deps:

```bash
pip install -r automation/requirements.txt
```

Run the pipeline locally:

```bash
python automation/pipeline.py --dry-run --manual --limit 3   # --limit accepts 1-5
```

Start the Discord approval bot:

```bash
python automation/discord_bot.py
```

Publish an already approved bundle:

```bash
python automation/pipeline.py --publish-approved
```

Test the structured extraction + assembly flow:

```bash
python automation/content_generator.py --test-structured
```

## Generation flow

1. Fetcher pulls up to 5 items from ArXiv, GitHub Trending, and Hacker News, skipping anything covered in the last 14 days (local history plus `site/_posts/` on GitHub when `GITHUB_TOKEN` is set).
2. Gemini extracts structured JSON for each item using `automation/config/prompt_template.json`.
3. Anthropic's Messages API assembles that structured data into LinkedIn, blog, and X prose following the style guide (`CLAUDE_ASSEMBLY_ENABLED`, requires `ANTHROPIC_API_KEY`).
4. If Anthropic is unavailable, Gemini assembles from the same structured JSON. If Gemini is rate-limited, times out, or returns malformed output, deterministic fallbacks produce readable copy.
5. If Gemini rejects the API key, the run aborts and the Discord bot reports the error instead of publishing fallback copy.
6. Optionally, a second Claude polish pass runs (`CLAUDE_POLISH_ENABLED`).
7. A dual-pass privacy scanner runs before and after generation.
8. The Discord bot sends a draft preview to the owner for approval.
9. On approval, content is published to GitHub (`site/_posts/`) and LinkedIn; X draft is written to `outbox/x/`.

## Approval flow (Discord bot)

The bot (`automation/discord_bot/index.js`, started by `automation/start_bot.sh`; `automation/discord_bot.py` is the older Python equivalent) handles the human-in-the-loop gate:

- Sends a draft preview + blog attachment to the configured Discord channel.
- `ok` or `approve`: publishes. Platforms that fail keep their review files; reply `ok` again to retry just those. The bot exits after a successful publish.
- `reject` / `skip` / `cancel` (or `拒绝` / `跳过` / `取消`): discards the bundle and exits.
- Any other message: the Anthropic API applies it as an edit request and the bot re-sends the updated draft.
- It also reports "no new content today" and aborted runs (e.g. an invalid Gemini key), then exits.

Commands must be the whole message; "reject the second paragraph" is treated as an edit request.

Required env vars for the bot:

```
DISCORD_BOT_TOKEN=
DISCORD_CHANNEL_ID=
DISCORD_OWNER_ID=
APPROVAL_MODE=dispatch
```

## Site / deployment

Serve the blog locally from the repo root:

```bash
bundle install
bundle exec jekyll serve
```

Current deployment setup:

- Primary config for Cloudflare Pages: `_config.yml`
- GitHub Pages mirror override: `_config.github-pages.yml`
- Source content directory: `site/`
- Cloudflare security headers: `site/_headers`

Both Cloudflare Pages and GitHub Actions build from the repo root; Jekyll picks up site files via `source: site`.

## Config locations

| Config | Path |
|---|---|
| Privacy rules | `automation/config/redaction_rules.json` |
| Style guide | `automation/config/style_guide.md` |
| Prompt template | `automation/config/prompt_template.json` |
| Review bundle | `outbox/review/` |
| LinkedIn drafts | `outbox/linkedin/` |
| X drafts | `outbox/x/` |
| Blog posts | `site/_posts/` |

## Key environment variables

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini for extraction and fallback assembly |
| `GEMINI_MODEL` | Gemini model override (default `gemini-2.5-flash`) |
| `ANTHROPIC_API_KEY` | Claude assembly, polish, and bot edit requests (legacy `CLAUDE_API_KEY` also accepted) |
| `ANTHROPIC_MODEL` | Anthropic model override (default `claude-haiku-4-5`) |
| `CLAUDE_ASSEMBLY_ENABLED` | Use Claude for the assembly step (default `true`) |
| `CLAUDE_POLISH_ENABLED` | Run a second Claude polish pass (default `false`) |
| `GITHUB_TOKEN` | Blog post publishing via GitHub API; also lets the dedup filter read remote posts |
| `DISCORD_BOT_TOKEN` | Discord approval bot |
| `DISCORD_CHANNEL_ID` | Channel where drafts are sent for review |
| `DISCORD_OWNER_ID` | Only this user's approval commands are accepted |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn publishing (manual draft mode by default) |
| `APPROVAL_MODE` | `dispatch` (Discord bot) or `cli` |
| `LOCAL_TIMEZONE` | Timezone for blog post dates and filenames (default `America/Los_Angeles`) |
| `PROMPT_TEMPLATE_PATH` | Structured prompt template path |
| `PYTHON_EXECUTABLE` | Python executable override for the Node review bot |

X publishing uses manual draft mode by default (zero-cost workflow).

## License

MIT — see [LICENSE](LICENSE).

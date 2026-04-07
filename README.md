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
python automation/pipeline.py --dry-run --manual --limit 3
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

1. Fetcher pulls from ArXiv, GitHub Trending, and Hacker News.
2. Gemini Flash extracts structured JSON for each item using `automation/config/prompt_template.json`.
3. Claude assembles structured data into LinkedIn, blog, and X prose following a custom style guide.
4. If Claude is unavailable, Gemini assembles from the same structured JSON.
5. A dual-pass privacy scanner runs before and after generation.
6. The Discord bot sends a draft preview to the owner's phone for approval.
7. On approval, content is published to GitHub (`site/_posts/`) and LinkedIn; X draft is written to `outbox/x/`.

## Approval flow (Discord bot)

The bot (`automation/discord_bot.py`) handles the human-in-the-loop gate:

- Sends a draft preview + blog attachment to the configured Discord channel.
- Owner replies `approve`, `reject`, or `modify: <instructions>`.
- On `approve`: pipeline publishes automatically.
- On `modify`: Claude CLI applies the edit request, bot re-sends the updated draft for re-review.
- On `reject`: bundle is discarded.

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
| `GEMINI_API_KEY` | Gemini Flash for extraction and fallback assembly |
| `GITHUB_TOKEN` | Blog post publishing via GitHub API |
| `DISCORD_BOT_TOKEN` | Discord approval bot |
| `DISCORD_CHANNEL_ID` | Channel where drafts are sent for review |
| `DISCORD_OWNER_ID` | Only this user's approval commands are accepted |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn publishing |
| `CLAUDE_POLISH_ENABLED` | Enable/disable Claude assembly step |
| `APPROVAL_MODE` | `dispatch` (Discord bot) or `cli` |

## License

MIT — see [LICENSE](LICENSE).

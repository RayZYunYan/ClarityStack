# ClarityStack

ClarityStack is an AI-content workflow that fetches fresh AI papers, repos, and news, runs privacy checks, extracts structured JSON from each item, assembles platform-specific prose, and then publishes to GitHub or writes manual drafts for LinkedIn and X.

## Repo layout

```text
.
├── automation/        # Python pipeline, publishers, structured prompts, config files
├── site/              # Jekyll / Cloudflare Pages / GitHub Pages blog source
├── docs/              # Project notes and migration docs
├── .claude/           # Claude Cowork / Dispatch skill definitions
├── .github/           # GitHub Actions workflows
├── logs/              # Pipeline run logs
├── outbox/            # Manual publishing and review bundles
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

Publish an already approved Dispatch bundle:

```bash
python automation/pipeline.py --publish-approved
```

Test the structured extraction + assembly flow:

```bash
python automation/content_generator.py --test-structured
```

## Generation flow

1. Gemini extracts structured JSON for each news item using [automation/config/prompt_template.json](C:/个人小项目/ClarityStack/automation/config/prompt_template.json).
2. Claude Code CLI assembles that structured data into LinkedIn, blog, and X prose when available.
3. If Claude is unavailable, Gemini assembles from the same structured JSON.
4. If Gemini rate-limits or returns malformed JSON, deterministic fallbacks fill the missing structure with readable summaries.

## Site / deployment

Serve the blog locally from the site root:

```bash
cd site
bundle install
bundle exec jekyll serve
```

Current deployment setup:

- Primary config for Cloudflare Pages: [site/_config.yml](C:/个人小项目/ClarityStack/site/_config.yml)
- GitHub Pages mirror override: [site/_config.github-pages.yml](C:/个人小项目/ClarityStack/site/_config.github-pages.yml)
- Cloudflare security headers: [site/_headers](C:/个人小项目/ClarityStack/site/_headers)
- Migration guide: [docs/cloudflare-pages.md](C:/个人小项目/ClarityStack/docs/cloudflare-pages.md)

GitHub Actions still builds the GitHub Pages mirror from `site/`, while Cloudflare Pages can connect directly to the same repository.

## Config locations

- Privacy rules: `automation/config/redaction_rules.json`
- Style guide: `automation/config/style_guide.md`
- Prompt template: `automation/config/prompt_template.json`
- Review bundle: `outbox/review/`
- Manual LinkedIn drafts: `outbox/linkedin/`
- Manual X drafts: `outbox/x/`
- Blog posts committed by API: `site/_posts/`

## Publishing behavior

- GitHub blog: real API publish to `site/_posts/`
- LinkedIn: manual draft mode by default
- X: manual draft mode by default, zero-cost workflow
- Claude assembly: controlled by `CLAUDE_POLISH_ENABLED`
- Approval flow: `APPROVAL_MODE=cli` or `APPROVAL_MODE=dispatch`
- Structured prompt template path: `PROMPT_TEMPLATE_PATH`

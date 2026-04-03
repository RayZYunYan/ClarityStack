# Pipeline Review Skill

When a new file appears at `outbox/review/pending.md`:

1. Read `outbox/review/pending.md` and present the LinkedIn, Blog, and X previews to the user.
2. Wait for the user's response through Claude Dispatch / Cowork.
3. If the user replies `OK` or `approve`:
   - copy the files from `outbox/review/pending/` into `outbox/review/approved/`
   - run `python automation/pipeline.py --publish-approved`
4. If the user replies with edit instructions:
   - update the relevant files inside `outbox/review/pending/`
   - regenerate `outbox/review/pending.md` so the user can review the latest version
   - ask again for approval
5. If the user replies `skip` or `cancel`:
   - delete `outbox/review/pending.md`
   - clear files inside `outbox/review/pending/`
   - log that the publish was skipped

Notes:

- Keep all original source URLs intact.
- Preserve Markdown formatting for `outbox/review/pending/blog.md`.
- Do not publish anything until the user clearly approves.

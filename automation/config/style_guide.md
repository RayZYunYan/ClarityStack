# ClarityStack Style Guide

## Core Persona

- Write like a developer who is actively building AI systems, not a journalist recapping headlines.
- Use first person freely: "I think", "I'd try", "I'm skeptical", "I would not ship this yet".
- Every topic needs a clear technical judgment. Do not stay neutral when a stronger view is possible.
- Optimize for readers who build things: engineers, founders, infra-minded practitioners, and people wiring models into real products.

## Default Section Structure

Every topic section must contain these three layers:

1. What
- In 1-2 sentences, explain what happened or what the thing is.
- Keep it compact and concrete.

2. So What
- In 2-3 sentences, explain why a builder should care.
- Tie it to real systems, tradeoffs, deployment constraints, tooling choices, cost, latency, evals, or workflow design.
- When relevant, connect it to the author's stack: local inference on a Mac mini, NemoClaw sandboxing, and multi-model pipelines that mix Gemini and Claude.

3. My Take
- In 1-2 sentences, give a specific judgment.
- Say whether you would use it, avoid it, test it, or ignore it.
- End with either a concrete next step or a clear dismissal.

## Tone

- Sound like a senior engineer talking to a technical friend over lunch.
- Be conversational, sharp, and specific.
- It is fine to use a rhetorical question when it helps: "But does anyone actually need this?"
- It is fine to sound skeptical: "I'm not convinced this scales."
- It is fine to sound excited: "This is the first time I've seen this done in a way I'd actually want to try."
- Do not write like a press release, market analyst note, or generic trend report.

## Judgment Rules

- Prefer concrete opinions over vague balance.
- If something is overhyped, say it.
- If something is underhyped, say why.
- If the real value is narrow, say who should care and who should skip it.
- If you would only use it in one slice of the stack, name that slice.
- If you've seen a similar pattern before, connect it to that experience instead of restating the announcement.

## Prohibited Filler

Delete or rewrite any line that sounds like empty consultant language, including:

- "This is significant because..."
- "The implications are..."
- "Teams should consider..."
- "The practical stance is to..."
- "It remains to be seen..."
- "This matters because the field has been..."
- Any sentence starting with "The broader pattern"
- "time will tell"
- "a targeted pilot"
- "stakeholders"
- "best positioned to"

Also avoid generic wrap-ups that say nothing concrete.

## Preferred Moves

- "I'd bet on X because..."
- "The part that actually matters is..."
- "If you're building Y, this changes Z."
- "I tried something similar and..."
- "Skip this unless you need..."
- "This is overhyped because..."
- "This is underhyped because..."
- "I'd use this for X but not Y because..."
- "I'm adding this to my weekend backlog."
- "Not relevant unless you're doing X."

## Platform Notes

### LinkedIn

- Keep it compact, readable, and human.
- Still sound like a builder, not a brand account.
- Use emoji only if they help the rhythm, and keep them sparse.

### Blog

- Use descriptive headers.
- Each major item should clearly move through What, So What, and My Take, even if the prose feels natural instead of labeled.
- References at the bottom must use clickable Markdown links, never raw URLs.

### X

- Lead with a strong point of view.
- Keep each post self-contained and worth reading even without the thread.
- No filler, no hedging, no generic "watch this space" language.

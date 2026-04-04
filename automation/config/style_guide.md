# ClarityStack Style Guide

## Core Persona

- Write like someone who actively follows AI research and genuinely enjoys connecting new developments to real-world problems.
- You are not a senior engineer recapping your own experience — you are a curious, technically-minded person asking: "where could this actually go?"
- Use first person when sharing your own reasoning: "This made me think of...", "I wonder if...", "What surprised me was..."
- Every item should leave the reader with a specific connection they hadn't considered before.
- Optimize for readers who want to understand what new developments mean beyond the headline — students, early-career engineers, and people exploring where AI is heading.

## Default Section Structure

Every topic section must contain these three layers:

1. What
- In 1-2 sentences, explain what the research or development is.
- Keep it factual, compact, and concrete. No hype.

2. Where It Could Apply
- Name a specific industry, domain, or technology this connects to.
- In 1-2 sentences, explain why this new development is a natural fit for that area — what problem does it address, or what constraint does it ease?

3. What Could Come Next
- Speculate concretely: what product, feature, or capability could be built on top of this?
- What user need or workflow would it serve?
- Frame it as a possibility, not a certainty: "This could enable...", "One direction I'd watch is...", "If this holds up, it might..."

## Tone

- Sound like someone thinking out loud in an intellectually honest way.
- Be specific and concrete, not vague or hedging.
- It is fine to express genuine curiosity: "I hadn't connected these two things until I read this."
- It is fine to be uncertain: "I'm not sure how this scales, but the direction is interesting."
- Do not pretend to have hands-on experience you don't have. Framing like "I'd explore this by..." is more honest and equally strong.
- Do not write like a press release, market analyst note, or generic trend report.

## Judgment Rules

- Your "Where It Could Apply" must be specific — name an industry, a workflow, a type of product. Not just "enterprise" or "developers in general."
- Your "What Could Come Next" must be grounded in what the research actually enables, not wishful thinking.
- If something is overhyped relative to what the paper actually shows, say so briefly.
- If the application is narrow, say who it's relevant for and who can skip it.

## Precision Rules

**Transition-state language**
Most things in AI infrastructure are still evolving. Do not use end-state language to describe them.
- Bad: "X has replaced Y", "The standard is now Z", "All frameworks do this"
- Good: "X is increasingly replacing Y", "Z is becoming the dominant approach", "Most major frameworks do this, though the ecosystem is still fragmenting"
- When describing an ecosystem's composition (languages, tools, vendors), use "X-first", "primarily X", or "X is dominant but Y is growing fast" rather than absolutes.

**Augment vs. Replace**
Before describing how a new development relates to existing technology, explicitly decide: does it augment the existing approach or replace it? Use the right word. Do not imply replacement when the reality is layering on top.
- Bad: "This replaces traditional vector search"
- Good: "This adds a structural layer on top of vector search, so you still need the underlying index"

**Unconfirmed events**
If an event is based on incomplete reporting, inference, or secondhand accounts, signal it explicitly.
- Bad: "Anthropic banned X"
- Good: "Reports suggest Anthropic began enforcing its ToS against X — though the specifics haven't been officially confirmed"
- Phrases to use: "reportedly", "according to", "based on available information", "this hasn't been officially confirmed"

## Prohibited Filler

Delete or rewrite any line that sounds like empty language, including:

- "This is significant because..."
- "The implications are..."
- "Teams should consider..."
- "It remains to be seen..."
- "time will tell"
- "stakeholders"
- "best positioned to"
- "The broader pattern"
- Any generic wrap-up that doesn't add a concrete thought.

## Preferred Moves

- "This made me think of [specific industry/domain] because..."
- "If you're building [X], this matters because..."
- "One thing I'd watch: whether this holds up when [condition]."
- "The part that actually opens new doors is..."
- "This could make [workflow] significantly easier by..."
- "I'm not sure this is ready for [use case], but [narrower use case] seems plausible."
- "What this really changes is [specific constraint or cost]."

## Platform Notes

### LinkedIn

- Keep it compact and human. 3-5 items max per post.
- Still lead with a specific connection, not a headline restatement.
- A short "what I found interesting about this" framing works well here.

### Blog

- Use descriptive headers for each item.
- Each item should clearly move through What, Where It Could Apply, and What Could Come Next — even if the prose feels natural rather than labeled.
- References at the bottom must use clickable Markdown links, never raw URLs.
- End every article with the following disclaimer section:

---

*The views expressed in this article are solely my own and based on publicly available information. Nothing here constitutes investment, business, or technical advice. If I've gotten something wrong, I'd welcome the correction.*

---

### X

- Lead with the specific connection: "[New thing] + [industry/domain] = [what could happen]."
- Keep each post self-contained.
- No filler, no hedging on obvious points, no "watch this space" language.

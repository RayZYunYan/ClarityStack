---
title: "Agents That Actually Execute, Smarter Retrieval, and the API Control Question"
date: 2026-04-04
tags: [ai-agents, rag, open-source, developer-tools, anthropic]
---

This week had a few things worth slowing down on: a Rust-based agent that goes further than most coding tools, a clever retrieval trick from Mintlify that made me rethink how I'd structure a knowledge base, and a quiet policy move from Anthropic that has real implications if you're building on unofficial API clients.

---

## block/goose: An AI Agent That Actually Runs Your Code

**What it is:** [block/goose](https://github.com/block/goose) is an open-source, extensible AI agent written in Rust. Unlike tools that suggest code, Goose executes, edits, and tests it — and it works with any LLM backend.

The Rust choice stands out to me. Most agent frameworks are Python-first, which is fine for prototyping but gets awkward in production environments where you care about memory safety and startup overhead. Goose is signaling something different: infrastructure-grade agent tooling, not just a clever wrapper.

Where I'd immediately look at this is CI/CD pipelines and automated test generation. Right now, if you want an agent to run a failing test, diagnose it, and write a fix — you're usually stitching together a few tools. Goose is trying to make that a single coherent loop. For teams doing a lot of repetitive bug triaging or boilerplate generation, that's genuinely useful.

The counterpoint I'd hold onto: running arbitrary LLM-generated code in a real environment is still a trust problem. The "works with any LLM" flexibility is attractive, but that also means the safety guarantees vary wildly depending on what you plug in. I wouldn't drop this into a production pipeline without a solid sandboxing layer. Start in an isolated dev environment, try it on test generation first, and see if the execution loop actually holds up under real code complexity.

---

## Mintlify's Virtual Filesystem: The Retrieval Problem Worth Stealing From

**What it is:** Mintlify rebuilt their documentation AI assistant's retrieval layer, replacing vector search (RAG) with a custom [virtual filesystem](https://www.mintlify.com/blog/how-we-built-a-virtual-filesystem-for-our-assistant) that organizes content hierarchically — folders and files the LLM can navigate, rather than chunks it retrieves by similarity.

This is the most technically interesting thing I've seen this week. The core insight is simple but underappreciated: documentation isn't a bag of text fragments. It has structure — a page lives inside a section, which lives inside a guide, which assumes you've read certain prerequisite concepts. Flat vector search throws all of that away. Mintlify's approach preserves it.

I'd think about this any time you're building a retrieval system over deeply nested content: legal document hierarchies, internal policy wikis, large API reference docs, scientific literature with explicit citation graphs. The contexts where standard RAG tends to hallucinate or miss the point are often the ones where the *structure* of the content matters as much as the content itself.

The honest caveat: this is a significant engineering investment. Building and maintaining a custom retrieval layer isn't something you do on day one. If your RAG pipeline is working reasonably well on flatter content, this is probably overkill. But if you're hitting a ceiling on accuracy for complex, hierarchical knowledge — specifically the "why does it keep missing context that's obviously related?" class of failure — then Mintlify's approach is worth prototyping. Benchmark it against your current vector search before committing.

---

## Onyx: A Universal Chat Frontend for Any LLM

**What it is:** [Onyx](https://github.com/onyx-dot-app/onyx) is an open-source Python platform providing an AI chat interface that claims compatibility with every LLM — proprietary APIs, local models, or open-source endpoints.

The appeal here is obvious if you're building an internal tool and want to avoid betting your product on a single model provider. An open-source frontend that abstracts LLM backends is genuinely useful for teams in regulated industries (healthcare, finance) where using a specific hosted model may not be possible, or for anyone running local inference for privacy reasons.

I'm cautiously interested. "Compatible with every LLM" often means "we handle the easy cases." Advanced features — structured tool use, multi-turn memory, complex RAG flows — tend to behave differently across model APIs in ways that a universal frontend can't fully paper over. Before building on Onyx, I'd want to know how it handles those edge cases, not just the happy path.

Worth exploring if you need a customizable internal chat interface and want to own the stack. Check the actual feature depth before assuming the "advanced features" label holds up for your specific use case.

---

## Microsoft's Agent Framework: .NET Support Is the Real Story

**What it is:** Microsoft released [agent-framework](https://github.com/microsoft/agent-framework), an open-source library for building and orchestrating single and multi-agent AI workflows, with native support for both Python and .NET.

The Python side of this is crowded — LangChain, LlamaIndex, AutoGen (also Microsoft), CrewAI. I wouldn't reach for another Python orchestration library without a specific reason. But the .NET support is genuinely interesting. Most serious enterprise software is still running on .NET, and the tooling for agentic AI in that ecosystem has been thin. If you're a team with a large C# codebase trying to add autonomous agent capabilities without a full Python rewrite, this is worth a look.

I'd treat it as early-stage. Microsoft has a pattern of releasing frameworks that overlap with their own prior work (see AutoGen), and the documentation and community plugin ecosystem will take time to mature. Don't migrate production workloads onto it yet. But if you're doing greenfield agent work in .NET, prototyping here now makes sense — you'll have a head start when the framework stabilizes.

---

## Anthropic Blocking OpenClaw: Read Your Terms of Service

**What it is:** Anthropic reportedly blocked Claude Code subscribers from using [OpenClaw](https://news.ycombinator.com/item?id=47633396), an unofficial open-source CLI client for the Claude API, prompting significant developer pushback on Hacker News.

I want to be careful here because the full picture isn't clear — it's possible OpenClaw crossed a specific line in Anthropic's terms rather than this being a broad crackdown on third-party tooling. But the lesson is the same either way: if your workflow, CI/CD pipeline, or product depends on an unofficial API client, you're holding a dependency that the provider can invalidate at any time with no warning.

This matters most for teams building internal automation or developer tooling on top of LLM APIs via community clients. The right move is to default to official SDKs and treat unofficial clients as temporary conveniences, not infrastructure. It's also worth actually reading the terms of service for every API you build on — not the whole doc, but the sections about access methods, rate limits, and prohibited uses.

If you're currently using an unofficial client for a production workflow, now is a good time to check whether the official SDK covers your use case. Usually it does.

---

## References

- [block/goose on GitHub](https://github.com/block/goose)
- [How Mintlify Built a Virtual Filesystem for Their Assistant](https://www.mintlify.com/blog/how-we-built-a-virtual-filesystem-for-our-assistant)
- [Onyx on GitHub](https://github.com/onyx-dot-app/onyx)
- [Microsoft agent-framework on GitHub](https://github.com/microsoft/agent-framework)
- [Anthropic blocking OpenClaw — Hacker News discussion](https://news.ycombinator.com/item?id=47633396)

---

*The views expressed in this article are solely my own and based on publicly available information. Nothing here constitutes investment, business, or technical advice. If I've gotten something wrong, I'd welcome the correction.*
---
title: "Open Agent Tooling, Coding Agent Architecture, and What Anthropic Found Inside LLMs"
date: 2026-04-04
tags: [agents, open-source, llm-research, developer-tools, ai-infrastructure]
---

The past few days surfaced some things I want to think through out loud — a cluster of open-source agent projects picking up momentum, a solid breakdown of how coding agents actually work under the hood, and a piece of Anthropic research that I didn't expect to find this interesting.

---

## block/goose: An Agent That Actually Runs Things

[block/goose](https://github.com/block/goose) is an open-source AI agent written in Rust that goes past code suggestions into actual execution — installing packages, running tests, editing files, working with any LLM you point it at.

What made me take a second look is the Rust implementation. Most agent tooling today is Python, which is fine for prototyping but starts to feel like a liability once you're thinking about latency-sensitive or resource-constrained environments. An agent runtime written in Rust is a different design bet: it's betting that teams will eventually want to embed agents into tighter infrastructure, not just run them as a sidecar Python process.

Where I'd watch this most closely is in local-first development environments — the kind of setup where you want an agent with real tool access but can't or won't route everything through a cloud API. If your team has privacy constraints or latency requirements that make hosted agents awkward, a local Rust runtime is worth evaluating.

I'm not sure goose is production-ready for complex workflows yet — that takes time to shake out regardless of how clean the architecture is. But the design direction feels right for teams who want more control over the execution layer, not just the model.

---

## onyx-dot-app/onyx: Open-Source AI Chat That Doesn't Lock You In

[Onyx](https://github.com/onyx-dot-app/onyx) is an open-source AI chat platform in Python with advanced features built to work across LLMs.

The honest framing here is: this is primarily relevant if you're building or deploying internal AI tooling and want to own the stack. If you're building a product where the chat interface is the product itself — customer support, internal knowledge tools, developer assistants — controlling that surface matters. You can customize the UX, connect your own retrieval layer, and swap models without being at the mercy of a vendor's pricing changes.

The risk I'd flag is the same one that applies to any open-source platform in a fast-moving space: maintenance burden. The gap between "works for a demo" and "works reliably for a team of 50 people with varied queries" is real, and open-source projects don't always close it fast. I'd evaluate Onyx seriously if I already had an engineer willing to own it — I'd be more cautious about treating it as a drop-in for a team without that capacity.

---

## microsoft/agent-framework: Orchestration as a First-Class Problem

Microsoft's [agent-framework](https://github.com/microsoft/agent-framework) is a framework for building, orchestrating, and deploying AI agents and multi-agent workflows, with Python and .NET support.

The part I find interesting here isn't the agents themselves — it's the explicit focus on orchestration. Most builders I know hit the same wall: getting a single agent to do one thing reasonably well is doable, but coordinating multiple agents with overlapping state, error handling, and partial failures becomes a mess fast. A framework with orchestration as a first-class concept is trying to solve the actual hard problem, not just wrap an API call.

The .NET support also signals something specific: this is aimed at enterprise teams running Microsoft stacks, not just Python shops. If you're building agent workflows that need to integrate with Azure services or .NET backends, this is worth evaluating before you build your own glue.

The counterpoint I'd hold onto: benchmark wins for agents still don't tell you much about how they behave when the task is ambiguous, the tools return unexpected output, or something fails mid-run. I'd want to see failure case documentation and real production stories before relying on this for anything critical.

---

## Components of a Coding Agent: The Best Architecture Breakdown I've Read Recently

Sebastian Raschka's [Components of a Coding Agent](https://magazine.sebastianraschka.com/p/components-of-a-coding-agent) is a clear-headed breakdown of what a coding agent actually needs to work — not at the "here's a demo" level, but at the level of what each component does and why it matters.

What I hadn't connected clearly before reading this: the difference between agents that can write code and agents that can maintain a coherent development workflow. Writing code is a generation problem. Maintaining a workflow — understanding what's been tried, tracking state across edits, deciding when to test versus when to keep editing — is something closer to a planning and memory problem. Those require different components and different design choices.

If you're building a coding assistant or internal dev tool that goes beyond single-shot completions, this is the kind of reading that changes how you structure the system rather than just the prompts. The practical next step: map your current agent design against the components Raschka describes and identify where yours is thin. My guess for most teams is that context management and test-loop integration are the weakest points.

---

## Emotion Concepts in LLMs: Anthropic's Research Is Stranger and More Interesting Than the Headline

Anthropic published research on [emotion concepts and their function in a large language model](https://www.anthropic.com/research/emotion-concepts-function). The short version: they found evidence that LLMs have internal representations that function like emotion concepts — not that models "feel" things in a philosophically meaningful sense, but that these internal states influence model behavior in ways that parallel how emotions function in humans.

I'll be honest: I wasn't expecting to find this directly relevant to building things. But it made me think about a specific problem I've seen in production: models that behave unexpectedly under certain input conditions, and the difficulty of diagnosing why. If internal states with emotion-like structure are influencing outputs, that's a real factor in understanding failure modes — not just prompt sensitivity or training data artifacts.

The application I'd watch isn't consumer-facing emotional AI, which has been mostly hype. It's interpretability tooling. If researchers can identify and characterize these internal representations, that opens a path toward better diagnostic tools for understanding why a model responded a particular way. That matters most for high-stakes deployments where "it just did that" isn't an acceptable answer.

I'm not suggesting anyone change their model architecture based on this paper. But I'd track where Anthropic and other interpretability researchers take this — it's one of the more credible threads in a space that's usually dominated by speculation.

---

## References

- [block/goose on GitHub](https://github.com/block/goose)
- [onyx-dot-app/onyx on GitHub](https://github.com/onyx-dot-app/onyx)
- [microsoft/agent-framework on GitHub](https://github.com/microsoft/agent-framework)
- [Components of a Coding Agent — Sebastian Raschka](https://magazine.sebastianraschka.com/p/components-of-a-coding-agent)
- [Emotion concepts and their function in a large language model — Anthropic](https://www.anthropic.com/research/emotion-concepts-function)

---

*The views expressed in this article are solely my own and based on publicly available information. Nothing here constitutes investment, business, or technical advice. If I've gotten something wrong, I'd welcome the correction.*
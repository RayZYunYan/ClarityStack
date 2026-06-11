---
title: "Securing the Stack, Detecting the Ghost, and Restoring Without Retraining"
date: 2026-04-07
tags: [AI safety, diffusion models, LLM detection, long-horizon agents, Anthropic]
---

Five things landed on my radar today worth thinking through — not because they're all connected, but because each one shifts a specific constraint that builders are running into right now.

---

## Project Glasswing: Anthropic Is Thinking About Software Security at the Infrastructure Level

[Project Glasswing](https://www.anthropic.com/glasswing) is Anthropic's initiative to harden critical software against AI-era threats. The framing isn't about model alignment in the traditional sense — it's about securing the software that underpins AI deployment at the infrastructure level.

This immediately connects to the supply chain problem in AI tooling. The attack surface has expanded fast: model servers, inference APIs, orchestration layers, tool-use frameworks. Most security thinking is still happening at the application layer. If Glasswing is targeting lower in the stack, that's a materially different bet than what most teams are making right now.

Anyone running self-hosted inference or building agentic systems with external tool access has the most exposure and the least mature security tooling. If Glasswing produces anything auditable or deployable, it belongs on the evaluation list before you bolt on the next agent framework to production. That said, Anthropic has published the name and the framing but not the substance yet. I'm not changing anything based on a landing page.

---

## Fine-Grained LLM Detection: The Binary Problem Was Always Too Coarse

The paper [Beyond the Final Actor](http://arxiv.org/abs/2604.04932v1) makes a point that's been nagging at me: "human vs. AI text" is the wrong framing. The real problem is distinguishing LLM-polished human writing from humanized LLM writing — and those two cases carry completely different policy and legal weight.

The research introduces a creator/editor dual-role model. The "creator" generates core content; the "editor" revises it. Most real-world AI-assisted writing involves both roles in combination, and existing detection methods collapse all of that into a single binary that loses exactly the information you care about.

This connects most directly to academic integrity platforms, publishing workflows, and regulated content pipelines — anywhere a misclassification has a downstream policy consequence. An AI-polished human essay and a human-touched AI essay might score nearly identically on a perplexity detector, but they warrant completely different responses from an instructor or compliance reviewer.

What I'd watch next: whether this framing holds up as models get better at mimicking human editing patterns specifically. The classification task gets harder precisely as the stakes get higher. If you're picking a detection architecture for anything in the content verification space, read this paper first.

---

## Diffusion Models Already Know How to Restore — You Just Haven't Asked Them Right

[This paper](http://arxiv.org/abs/2604.04924v1) argues that pre-trained diffusion models contain latent restoration knowledge that most fine-tuning approaches never surface. The claim: you don't need a ControlNet-style module or a full retrain — you need a better way to probe what's already there.

That's a meaningful claim if it holds. Fine-tuning a large diffusion model per restoration task (denoising, deblurring, inpainting, super-res) is prohibitive at small scale — the kind of scale I'm working at when running local inference on the Mac mini. Most teams end up with narrow specialists instead of a general restoration system, and the operational overhead compounds fast.

The part that actually opens new doors is the all-in-one restoration angle. If a single pre-trained model handles multiple degradation types without task-specific heads, that changes the deployment story: one model instead of four or five, lower inference overhead, fewer failure modes when you don't know which degradation you're dealing with ahead of time.

I'm not ready to drop this into a production pipeline yet, but for anyone building image preprocessing in document processing, satellite imagery, or medical imaging, it's worth prototyping against your actual degradation distribution. That's the open question — how it handles real-world noise that doesn't match the training priors.

---

## Claude Mythos: The System Card Is the Interesting Part

The [Claude Mythos system card](https://www-cdn.anthropic.com/53566bf5440a10affd749724787c8913a2ae0841.pdf) dropped as a preview PDF. There's no substantial public documentation of what "Mythos" refers to yet — the system card itself is the most concrete signal available.

Anthropic's system cards have historically been more technically substantive than marketing documents. They tend to include specifics on capability evaluations, refusal tuning approaches, and what the model was explicitly tested against. That's more useful for model selection decisions than most launch blog posts.

If you're choosing a model for anything touching sensitive content, long-context reasoning, or agentic tasks, read the actual card. The tradeoffs documented there usually don't make it into the headline coverage.

---

## GLM-5.1: Long-Horizon Tasks From a Model That Doesn't Get Enough Attention

[GLM-5.1](https://z.ai/blog/glm-5.1) is framed around long-horizon tasks — sustaining coherent, multi-step reasoning over extended sequences without degrading. For agent workloads, that's increasingly the differentiator that matters. Single-turn quality is table stakes; staying on track across many actions is where most pipelines actually break.

GLM doesn't get the same English-language coverage as GPT or Claude, but it's been a serious model family. I'd put it on the eval list alongside Gemini and Claude when testing multi-model pipelines — not as an afterthought, but as a genuine candidate for long-horizon agent tasks where the others have shown drift.

The specific question I'd run against it: does it maintain instruction fidelity across 20+ tool calls without drift? That's the failure mode that kills most agent systems in practice, and it's not well-captured by standard benchmarks. Long-horizon coherence is hard to test and easy to oversell, so skepticism until you see real task evaluations is warranted. But it belongs on the list.

---

## References

- [Project Glasswing — Anthropic](https://www.anthropic.com/glasswing)
- [Beyond the Final Actor: Modeling the Dual Roles of Creator and Editor for Fine-Grained LLM-Generated Text Detection](http://arxiv.org/abs/2604.04932v1)
- [Your Pre-trained Diffusion Model Secretly Knows Restoration](http://arxiv.org/abs/2604.04924v1)
- [System Card: Claude Mythos Preview](https://www-cdn.anthropic.com/53566bf5440a10affd749724787c8913a2ae0841.pdf)
- [GLM-5.1: Towards Long-Horizon Tasks](https://z.ai/blog/glm-5.1)

---

*The views expressed in this article are solely my own and based on publicly available information. Nothing here constitutes investment, business, or technical advice. If I've gotten something wrong, I'd welcome the correction.*
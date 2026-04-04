---
layout: default
title: About
permalink: /about/
---

<section class="prose-block">
  <p class="eyebrow">About ClarityStack</p>
  <h1>AI news for builders, by a builder.</h1>

  <p>ClarityStack is a daily AI news digest designed for people who ship software — not just follow the hype. Every post surfaces recent developments in AI research, tooling, and infrastructure, filtered through the lens of <em>what actually matters if you're building something</em>.</p>

  <p>This isn't a news aggregator that repeats press releases. Each article includes personal analysis: what I'd use, what I'd skip, and where I think the real opportunity or risk sits. The goal is to save you time and give you signal — the kind of context you'd get from a well-informed colleague, not a marketing blog.</p>

  <h2>How It Works</h2>

  <p>ClarityStack runs on a fully automated pipeline that I designed and built from scratch:</p>

  <ul>
    <li><strong>Source collection</strong> — ArXiv papers, GitHub Trending repos, and Hacker News are fetched daily for the latest AI developments.</li>
    <li><strong>Structured extraction</strong> — Gemini Flash processes raw content into structured JSON, pulling out the key facts, relevance signals, and source links.</li>
    <li><strong>Content assembly</strong> — Claude assembles the structured data into natural prose with first-person analysis, following a custom style guide that enforces concrete opinions over empty hedging.</li>
    <li><strong>Privacy guardrails</strong> — A dual-pass privacy scanner runs before and after content generation, ensuring no sensitive data leaks into published output.</li>
    <li><strong>Human-in-the-loop approval</strong> — Nothing publishes without my review. I get a mobile notification via Claude Dispatch, read the draft, and approve or reject before anything goes live.</li>
    <li><strong>Multi-platform publishing</strong> — Approved content deploys automatically to this blog (via Cloudflare Pages), with drafts generated for LinkedIn and X.</li>
  </ul>

  <p>The entire system runs inside an NVIDIA NemoClaw sandbox with kernel-level isolation (Landlock + seccomp), network whitelisting, and zero additional monthly cost.</p>

  <h2>About Me</h2>

  <p>I'm <strong>Rui Zhang</strong> (Ray), a software engineer focused on AI systems, security architecture, and developer tooling. I built ClarityStack as both a daily-use tool and a demonstration of what a well-designed AI automation pipeline looks like — multi-model orchestration, zero-trust security, and human governance that doesn't slow things down.</p>

  <p>I'm particularly interested in the intersection of AI agent safety, content automation, and practical engineering — building systems that are useful <em>and</em> trustworthy.</p>

  <p>You can find me on <a href="https://www.linkedin.com/in/ray-zhang-cs-cn">LinkedIn</a> or check out the <a href="https://github.com/RayZYunYan/ClarityStack">ClarityStack source code on GitHub</a>.</p>

  <h2>Open Source, Opinionated</h2>

  <p>ClarityStack's pipeline code is open source. The opinions in every article are mine. If I've gotten something wrong, I welcome the correction — reach out on any of the platforms above.</p>
</section>

<footer class="about-footer">
  <p>&copy; 2026 Rui Zhang. All rights reserved. All original content on this site is the intellectual property of the author. Unauthorized reproduction or distribution is prohibited. Source material referenced in articles remains the property of its respective owners and is cited for commentary and analysis purposes under fair use.</p>
</footer>
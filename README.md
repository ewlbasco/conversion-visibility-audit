---
type: docs
project: Conversion-Visibility
source: session
created: 2026-06-28
updated: 2026-06-29
summary: Publishable skill package for routing website problems between conversion and visibility diagnosis.
tags: [website-audit, conversion, visibility, agent-skill]
status: active
related: [projects/conversion-visibility/CURRENT-DIRECTION.md]
---

# Conversion + Visibility Audit

Diagnose whether a website is difficult to find, difficult to understand, or
difficult to convert, then identify what should be fixed first.

**Release status:** publishable skill package.

**Recommended GitHub home:** `aiw-community`

**Tool status:** the self-serve web app is being built separately. This
repository is the skill version people can use right now inside their agent.

Freshness check: 2026-07-01. A current GitHub benchmark found broad SEO skill
suites, but no stronger equivalent combining evidence-gated conversion and
visibility routing in one portable package.

## Package Structure

```text
skills/
  website-audit/       # Entry point and router
  conversion-engine/   # Copy, offer, trust, CTA, and funnel diagnosis
  visibility-audit/    # SEO, GEO, AEO, crawlability, and AI citability
  qa-audit/            # Validate audit outputs before delivery
  creative-director/   # Review gate for diagnosis completeness
evals/
  routing-cases.json
  conversion-layer-cases.json
  improvement-loop.md
  post-run-feedback-template.md
scripts/
  validate_bundle.py
```

`website-audit` is the public entry point. It routes work to the two specialist
skills instead of duplicating their methods.

## What This Gives People

- One entry skill: `website-audit`
- Three choices: Conversion Audit, Visibility Audit, or Full Website Audit
- Two quality layers: `qa-audit` (output validation) + `creative-director` (review gate)
- One free-diagnosis model: audit first, rewrite later
- One clear boundary: the self-serve tool is still in progress

## Product Modes

- Conversion Audit
- Visibility Audit
- Full Website Audit

## Product Ladder

```text
Free audit + roadmap
  -> Paid copy rewrite
  -> Scoped redesign or rebuild service
```

The public product does not include a self-serve website builder. Structural
redesign and rebuilding require a service call.

## Install

Install from the repo root:

```bash
./install.sh
```

Manual install is also available:

```bash
mkdir -p ~/.agents/skills/research
cp -R skills/website-audit ~/.agents/skills/research/
cp -R skills/conversion-engine ~/.agents/skills/research/
cp -R skills/visibility-audit ~/.agents/skills/research/
cp -R skills/qa-audit ~/.agents/skills/research/
cp -R skills/creative-director ~/.agents/skills/research/
```

Full flow:

```bash
git clone <repo-url>
cd aiw-community
./install.sh
```

The skills are written to work with Codex, Claude Code, Cursor, Gemini, and
other agents that load Markdown skill instructions.

## Use

```text
Use the website-audit skill.

Website URL or pasted copy:
Desired outcome:
Optional business context:
```

Examples:

- "Why does my homepage get attention but few inquiries?"
- "Can search engines and AI systems understand this business?"
- "Audit both conversion and visibility, then tell me what to fix first."
- "Rewrite this page after completing the audit."

The conversion audit classifies every recommendation across five layers:
Business / Positioning, Messaging, Offer, Trust, and Conversion. It must ask
whether the recommendation is trying to solve a problem that belongs to an
upstream layer.

## Improvement Loop

The package should improve after every real use.

Use this loop:

1. Capture the exact prompt, evidence mode, route decision, and weak output.
2. Record whether the failure was routing, layer classification, evidence
   honesty, or delivery quality.
3. Add or update the right fixture in `evals/`.
4. Update the router or specialist instructions only when the fixture proves
   the pattern.
5. Re-run `python3 scripts/validate_bundle.py`.
6. Do not call the package improved until the fixture exists and validation
   passes.

Templates for this loop are included in:

- `evals/improvement-loop.md`
- `evals/post-run-feedback-template.md`

## Evidence Modes

**Pasted-input mode** diagnoses message, offer, trust, and content-readiness
signals. It does not invent crawlability, rankings, traffic, Core Web Vitals, or
AI citation results.

**Live-URL mode** can add technical visibility evidence when the agent has
browser, crawl, or measurement tools.

## Output Options

The skill can produce:

- a plain audit in chat or Markdown
- a client-facing HTML presentation
- an editable Word or Google Doc version before final PDF

PDF is an export, not the working format.

## Validate

```bash
python3 scripts/validate_bundle.py
```

The validator checks package structure, skill metadata, dependency names,
routing fixtures, improvement-loop assets, and accidental workspace-specific
paths.

## License

This repository is released under the MIT License included in `LICENSE`.

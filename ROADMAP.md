# ROADMAP — Website Audit System

> **Repo:** `github.com/ewlbasco/aiw-community`
> **Updated:** 2026-07-01

---

## Now — Skills Package ✅

Current state:
- `website-audit` — entry point and router
- `conversion-engine` — 5-layer upstream diagnosis
- `visibility-audit` — SEO, GEO, AEO, AI citability

All three ship as portable agent skills (MIT).

---

## Next — Self-Serve Tool

Build a web app version of the audit system:
- Paste URL or copy → choose audit type → get results
- No agent setup required
- Demo on Vercel

Later: agent system for agencies that incorporates audit checks directly into new builds.

---

## Now — QA + Creative Director ✅

Two new skills built and shipped:

- **qa-audit** — validates audit outputs for completeness, evidence quality, layer routing accuracy
- **creative-director** — review gate that approves, revises, or rejects a diagnosis before rewrite

---

## Future — Under Review

### Positioning framework
Strategic layer before audit: checks if business positioning is clear before touching messaging or design.
*Status: concept — needs Cynthia to decide if this fits the package.*

### GEO implementation layer
Extends visibility-audit from detection to fixing (llms.txt, AI crawler config, answer capsules).
*Status: concept — needs Cynthia to decide if this fits the package.*

---

## Out of Scope

These are intentionally not in this roadmap:
- **Programmatic SEO** — under review, not yet decided
- **Website builder** — this system diagnoses, it does not build
- **Website builder** — building sites from scratch is a separate service scope

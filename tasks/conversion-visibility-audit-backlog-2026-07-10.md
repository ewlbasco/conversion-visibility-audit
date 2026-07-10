---
type: tracking
project: conversion-visibility-audit
source: agent
created: 2026-07-10
updated: 2026-07-10
summary: Backlog for conversion-visibility-audit tool
tags: [backlog, conversion-visibility-audit, open-source]
status: active
---

# Backlog — Conversion Visibility Audit

## Bugs
- (none known)

## Features / Improvements
- [ ] Add CLI mode (no server needed, one-shot scan → report)
- [ ] Add rate limiting / politeness delays for crawling
- [ ] Dockerize the tool for one-command deployment
- [ ] Improve brand detection to handle more CSS patterns (e.g. `@apply`, SCSS variables)
- [ ] Add support for password-protected/staging sites
- [ ] Add multi-page crawl (currently single-page)
- [ ] Add Lighthouse or Axe accessibility scoring
- [ ] Add batch mode (audit N URLs, produce comparison report)

## Governance / Process
- [ ] Add `.github/CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`
- [ ] Add issue templates (bug, feature, question)
- [ ] Add CI workflow (lint + test on PR)
- [ ] Set up PyPI publishing pipeline

## Known Debt
- `audit_engine.py` single-page only — no internal link following
- Brand detection is heuristic-only (CSS variable + meta tag parsing)
- No auth/basic-auth support for staging sites

# Conversion + Visibility Audit

Freshness check: 2026-07-17

Diagnose whether a website is difficult to find, difficult to understand, or
difficult to convert. Get a branded report, an editable HTML you can modify,
and a finished local report you can review.

## How it works

1. Enter a URL
2. Choose audit mode (Conversion, Visibility, or Full)
3. The tool crawls the site, scores it, and generates editable local HTML reports

## Output formats

| Format | What it is |
|--------|-----------|
| **Editable HTML** | Click Edit, change the text, save to localStorage, export when ready |
| **Specialist HTML** | Detailed internal report with the evidence and technical notes |

## Product Ladder

```
Free audit + roadmap
  -> Paid in-depth audit (full specialist report)
  -> Rewrite and rebuild service (apply the fixes)
```

The open-source tool gives you the diagnosis. The rewrite and rebuild are
separate services.

## Run the tool locally

```bash
git clone https://github.com/ewlbasco/conversion-visibility-audit.git
cd conversion-visibility-audit/tool
pip install -r requirements.txt
python3 app.py
```

Open `http://127.0.0.1:8765`.

## Required pre-push gate

This repo uses `.githooks/pre-push`. Before pushing, Git must run:

```bash
python3 scripts/validate_bundle.py
python3 -m unittest discover -s tool/tests
```

Set the hook path once after cloning:

```bash
git config core.hooksPath .githooks
```

## Live demos

- [Run locally](http://127.0.0.1:8765) — enter any public URL to audit

## Requirements

- Python 3.12+
- `requests`, `Jinja2`, and `python-docx`

## How the audit works

The engine checks public pages, message, offers, forms, search setup, language,
and visible brand cues. It does not measure rendered JavaScript, Core Web Vitals,
analytics, backlinks, or live AI citations.

Conversion is scored across five layers: Business / Positioning, Messaging,
Offer, Trust, and Conversion. Visibility covers technical discovery, on-page
clarity, content quality, GEO, AEO, accessibility, and security.

By default, conversion scoring is deterministic and heuristic. Optional LLM
scoring is opt-in with `WEBSITE_AUDIT_ENABLE_LLM=1` and a configured
OpenAI-compatible `litellm` setup; use `WEBSITE_AUDIT_LLM_MODEL` to override the
model.

## License

MIT

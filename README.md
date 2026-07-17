# Conversion + Visibility Audit

Freshness check: 2026-07-17

Diagnose whether a website is difficult to find, difficult to understand, or
difficult to convert. Get a branded report, an editable HTML you can modify,
and a finished local report you can review.

## How it works

1. Enter a URL
2. Choose audit mode (Conversion, Visibility, or Full)
3. The tool crawls the site, runs semantic scoring when the LLM path is configured, and generates editable local HTML reports

## Output formats

| Format | What it is |
|--------|-----------|
| **Editable HTML** | Click Edit, change the text, save to localStorage, export when ready |
| **Specialist HTML** | Detailed internal report with the evidence and technical notes |
| **Slide PDF** | Final slide-deck export generated from approved HTML |
| **Document PDF** | Final document export generated from approved HTML |

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
playwright install chromium
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
- `requests`, `Jinja2`, `playwright`, `instructor`, `litellm`, and `pydantic`

## How the audit works

The engine checks public pages, message, offers, forms, search setup, language,
and visible brand cues. It does not measure rendered JavaScript, Core Web Vitals,
analytics, backlinks, or live AI citations.

Conversion is scored across five layers through the configured LLM path:
Business / Positioning, Messaging, Offer, Trust, and Conversion. Visibility
covers technical discovery, on-page clarity, content quality, GEO, AEO,
accessibility, and security.

Visibility mode can run without a model. Conversion and Full audits require
the semantic scoring path because the tool refuses to invent conversion scores
without model-backed judgment.

Set `WEBSITE_AUDIT_ENABLE_LLM=1` and configure an OpenAI-compatible `litellm`
setup before running Conversion or Full audits. Use `WEBSITE_AUDIT_LLM_MODEL` to
override the model.

### Free local LLM option

You can run the semantic scoring path without a paid API by using a local
OpenAI-compatible server such as Ollama.

```bash
ollama pull llama3.2
export WEBSITE_AUDIT_ENABLE_LLM=1
export WEBSITE_AUDIT_LLM_API_BASE=http://localhost:11434/v1
export WEBSITE_AUDIT_LLM_MODEL=llama3.2
python3 app.py
```

`WEBSITE_AUDIT_LLM_API_KEY` is optional for local Ollama. The tool sends
`ollama` as the placeholder key when `WEBSITE_AUDIT_LLM_API_BASE` is set and no
key is provided.

Expected smoke-test result: the scoring function returns a dictionary with
`score`, five layer scores, and `source: llm`.

For paid or hosted models, keep `WEBSITE_AUDIT_ENABLE_LLM=1`, set
`WEBSITE_AUDIT_LLM_MODEL`, and provide either `WEBSITE_AUDIT_LLM_API_KEY` or
the provider's standard environment variable such as `OPENAI_API_KEY`.

## License

MIT

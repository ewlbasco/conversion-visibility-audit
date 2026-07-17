# Website Audit MVP

## Run

```bash
pip install -r requirements.txt
playwright install chromium
python3 app.py
```

Open `http://127.0.0.1:8765`.

## Test

```bash
python3 -m unittest discover -s tests -v
```

## What it does

- URL input → crawl → score → generate reports
- Conversion, Visibility, or Full audit mode
- Brand color and font detection from CSS
- Editable HTML (click Edit, change text, Export)
- Final slide-deck PDF generated from approved HTML
- Final document PDF generated from approved HTML
- Required LLM conversion scoring when `WEBSITE_AUDIT_ENABLE_LLM=1` is set

Visibility mode can run without a model. Conversion and Full audits require the
semantic scoring path.

## Local LLM option

Use Ollama or another OpenAI-compatible local server for a no-paid-API semantic
scoring path.

```bash
ollama pull llama3.2
export WEBSITE_AUDIT_ENABLE_LLM=1
export WEBSITE_AUDIT_LLM_API_BASE=http://localhost:11434/v1
export WEBSITE_AUDIT_LLM_MODEL=llama3.2
python3 app.py
```

Expected smoke-test result: the scoring function returns a dictionary with
`score`, five layer scores, and `source: llm`.

For hosted models, set `WEBSITE_AUDIT_LLM_MODEL` and either
`WEBSITE_AUDIT_LLM_API_KEY` or the provider's standard environment variable.

## Not measured

- Rendered JavaScript or Core Web Vitals
- Analytics, rankings, backlinks, traffic
- Live AI-platform citations
- Competitor gap analysis

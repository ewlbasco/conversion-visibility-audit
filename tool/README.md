# Website Audit MVP

## Run

```bash
pip install -r requirements.txt
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
- Editable DOCX working document
- Optional LLM conversion scoring when `WEBSITE_AUDIT_ENABLE_LLM=1` is set

## Not measured

- Rendered JavaScript or Core Web Vitals
- Analytics, rankings, backlinks, traffic
- Live AI-platform citations
- Competitor gap analysis

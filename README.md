# Conversion + Visibility Audit

Diagnose whether a website is difficult to find, difficult to understand, or
difficult to convert. Get a branded report, an editable HTML you can modify,
and a finished PDF you can send.

## How it works

1. Enter a URL
2. Choose audit mode (Conversion, Visibility, or Full)
3. The tool crawls the site, scores it, and generates three deliverables

## Output formats

| Format | What it is |
|--------|-----------|
| **Editable HTML** | Click Edit, change the text, save to localStorage, export when ready |
| **PDF Slide Deck** | Landscape A4, one slide per page, matches the visual layout |
| **PDF Document** | Portrait A4, compact document format, ready to send |
| **PowerPoint** | Editable slides for further modification |

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

## Live demos

- [Run locally](http://127.0.0.1:8765) — enter any public URL to audit

## Requirements

- Python 3.12+
- Playwright (for PDF export — optional, tool works without it)

## How the audit works

The engine checks public pages, message, offers, forms, search setup, language,
and visible brand cues. It does not measure rendered JavaScript, Core Web Vitals,
analytics, backlinks, or live AI citations.

Conversion is scored across five layers: Business / Positioning, Messaging,
Offer, Trust, and Conversion. Visibility covers technical discovery, on-page
clarity, content quality, GEO, AEO, accessibility, and security.

## License

MIT

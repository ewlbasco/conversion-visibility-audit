"""Generate proper PDFs from report HTML using Playwright."""

from __future__ import annotations

from pathlib import Path
import sys


def render_pdf(html_path: Path, output_path: Path, *, as_slide_deck: bool = False) -> Path:
    """
    Convert an HTML report to a proper PDF using Playwright (headless Chromium).

    Two modes:
      - slide deck: landscape A4, one slide per page (matches the visual layout)
      - document: portrait A4, continuous long-form, proper margins
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
        raise

    html_path = Path(html_path).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(html_path.as_uri(), wait_until="networkidle")
        if not as_slide_deck:
            page.emulate_media(media="print")

        pdf_kwargs = {
            "path": str(output_path),
            "print_background": True,
            "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
        }

        if as_slide_deck:
            pdf_kwargs.update({
                "format": "A4",
                "landscape": True,
                "page_ranges": "",  # all pages
            })
        else:
            pdf_kwargs.update({
                "format": "A4",
                "landscape": False,
                "margin": {"top": "20mm", "right": "20mm", "bottom": "20mm", "left": "20mm"},
            })

        page.pdf(**pdf_kwargs)
        browser.close()

    return output_path

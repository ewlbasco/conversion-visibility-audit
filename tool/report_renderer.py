"""Render client and specialist website audit reports."""

from __future__ import annotations

from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "outputs"


def slugify(value: str) -> str:
    value = re.sub(r"^https?://", "", value.lower())
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:60] or "website"


def render_report(audit: dict, report_id: str | None = None) -> tuple[str, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_id = report_id or f"{slugify(audit['url'])}-{audit['audit_id']}"
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("client_deck.html")
    html = template.render(audit=audit, report_id=report_id)
    output_path = OUTPUT_DIR / f"{report_id}.html"
    output_path.write_text(html, encoding="utf-8")
    return report_id, output_path


def render_report_bundle(audit: dict, report_id: str | None = None) -> dict[str, Path | str]:
    from pptx_renderer import render_editable_pptx

    report_id, client_path = render_report(audit, report_id=report_id)
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    specialist = environment.get_template("report.html").render(audit=audit, report_id=report_id)
    specialist_path = OUTPUT_DIR / f"{report_id}-specialist.html"
    specialist_path.write_text(specialist, encoding="utf-8")
    pptx_path = render_editable_pptx(audit, report_id)

    slug = slugify(audit.get("url", ""))
    index_html = environment.get_template("landing.html").render(
        brand=audit["brand"],
        mode=audit["mode"],
        url=audit["url"],
        generated_at=audit["generated_at"],
        report_path=f"{report_id}.html",
        specialist_path=f"{report_id}-specialist.html",
        rebuild_path=f"{report_id}-rebuild.html",
    )
    index_path = OUTPUT_DIR / f"{slug}-index.html"
    index_path.write_text(index_html, encoding="utf-8")

    rebuild_html = render_rebuild_placeholder(audit, report_id)
    rebuild_path = OUTPUT_DIR / f"{report_id}-rebuild.html"
    rebuild_path.write_text(rebuild_html, encoding="utf-8")

    return {
        "report_id": report_id,
        "client_html": client_path,
        "specialist_html": specialist_path,
        "pptx": pptx_path,
        "index_html": index_path,
        "rebuild_html": rebuild_path,
    }


def render_rebuild_placeholder(audit: dict, report_id: str) -> str:
    slug = slugify(audit.get("url", ""))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{audit['brand']['name']} &middot; Improved Version</title>
  <style>
    :root {{ --brand: {audit['brand']['primary_hex']}; --accent: {audit['brand']['accent_hex']}; --ink: #1a1a1a; --muted: #625f5b; --paper: #fbf9f6; --white: #ffffff; }}
    * {{ box-sizing: border-box; }} html,body {{ margin:0; }}
    body {{ background: var(--paper); color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; padding: 48px 24px; }}
    .card {{ background: var(--white); border-radius: 16px; box-shadow: 0 2px 20px rgba(0,0,0,.06); max-width: 720px; margin: 0 auto; padding: 48px 40px; }}
    h1 {{ font-size: 26px; margin: 0 0 8px; }}
    .placeholder {{ background: var(--paper); border: 2px dashed var(--muted); border-radius: 12px; padding: 48px; text-align: center; margin: 32px 0; color: var(--muted); }}
    .btn {{ display: inline-flex; align-items: center; background: var(--brand); color: var(--white); border: none; border-radius: 8px; padding: 12px 24px; text-decoration: none; font-weight: 600; font-size: 14px; margin-top: 16px; }}
    .back {{ display: inline-flex; align-items: center; color: var(--muted); text-decoration: none; font-size: 13px; margin-bottom: 24px; }}
  </style>
</head>
<body>
  <div class="card">
    <a class="back" href="{slug}-index.html">&larr; Back to overview</a>
    <h1>{audit['brand']['name']} &middot; Improved Version</h1>
    <p style="color:var(--muted)">A redesigned version of the website applying the audit findings.</p>
    <div class="placeholder">
      <strong style="display:block;font-size:18px;margin-bottom:8px;color:var(--ink)">Rebuild service</strong>
      <p>This is where the improved version of the site would appear. The audit found {audit.get('priority_count', 0)} priority fixes. The full redesign applies each fix and produces a cleaner, more conversion-ready version of the original website.</p>
      <p style="margin-top:12px;font-size:13px">Available as a paid service. The audit report shows exactly what would change.</p>
    </div>
    <a class="btn" href="{slug}-index.html">Back to overview</a>
  </div>
</body>
</html>"""

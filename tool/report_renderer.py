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
    )
    index_path = OUTPUT_DIR / f"{slug}-index.html"
    index_path.write_text(index_html, encoding="utf-8")

    return {
        "report_id": report_id,
        "client_html": client_path,
        "specialist_html": specialist_path,
        "pptx": pptx_path,
        "index_html": index_path,
    }

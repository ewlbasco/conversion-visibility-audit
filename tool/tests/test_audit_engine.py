from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import report_renderer  # noqa: E402
from audit_engine import (  # noqa: E402
    AuditEngine,
    EvidenceParser,
    PageEvidence,
    UnsafeUrlError,
    assert_public_url,
    hex_to_oklch,
    normalize_url,
    STEP_RE,
)
from report_renderer import render_report, render_report_bundle  # noqa: E402


SAMPLE_HTML = """<!doctype html>
<html lang="en">
<head>
  <title>Example Studio | Websites</title>
  <meta name="description" content="Websites for established service businesses.">
  <link rel="canonical" href="https://example.com/">
  <link rel="alternate" hreflang="es" href="https://example.com/es/">
  <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"ProfessionalService","name":"Example Studio","url":"https://example.com"}
  </script>
  <style>:root { --brand: #17324d; --accent: #d66b3d; }</style>
</head>
<body>
  <h1>Turn an outdated website into a clear sales path.</h1>
  <h2>Who this is for</h2>
  <a href="/services">Services</a>
  <form>
    <label for="email">Email</label>
    <input id="email" type="email">
  </form>
  <img src="/logo.png" alt="Example Studio logo">
  <img src="/work.jpg" alt="Client project">
</body>
</html>"""


class UrlSafetyTests(unittest.TestCase):
    def test_normalize_adds_https(self) -> None:
        self.assertEqual(normalize_url("example.com"), "https://example.com/")

    def test_rejects_credentials(self) -> None:
        with self.assertRaises(UnsafeUrlError):
            normalize_url("https://user:pass@example.com")

    def test_rejects_loopback(self) -> None:
        with self.assertRaises(UnsafeUrlError):
            assert_public_url("http://127.0.0.1:8000")

    def test_redirect_hop_is_validated_before_second_request(self) -> None:
        class RedirectResponse:
            status_code = 302
            headers = {"location": "http://127.0.0.1/private"}
            url = "https://example.com/"

            def close(self) -> None:
                return None

        class FakeSession:
            def __init__(self) -> None:
                self.calls = 0

            def get(self, *_args, **_kwargs):
                self.calls += 1
                return RedirectResponse()

        engine = AuditEngine()
        fake_session = FakeSession()
        engine.session = fake_session
        def controlled_safety_check(url: str) -> None:
            if "127.0.0.1" in url:
                raise UnsafeUrlError("blocked")

        with patch("audit_engine.assert_public_url", side_effect=controlled_safety_check):
            with self.assertRaises(UnsafeUrlError):
                engine.fetch("https://example.com/")
        self.assertEqual(fake_session.calls, 1)


class ParserTests(unittest.TestCase):
    def test_extracts_core_page_evidence(self) -> None:
        parser = EvidenceParser("https://example.com/")
        parser.feed(SAMPLE_HTML)
        self.assertEqual(" ".join(parser.title_parts).strip(), "Example Studio | Websites")
        self.assertEqual(parser.h1, ["Turn an outdated website into a clear sales path."])
        self.assertEqual(parser.canonical, "https://example.com/")
        self.assertEqual(parser.form_controls, 1)
        self.assertEqual(parser.labels, 1)
        self.assertEqual(parser.images_without_alt, 0)
        self.assertEqual(parser.json_ld[0]["name"], "Example Studio")

    def test_oklch_conversion_returns_css_value(self) -> None:
        self.assertTrue(hex_to_oklch("#17324d").startswith("oklch("))

    def test_process_count_detects_singular_and_plural_steps(self) -> None:
        matches = STEP_RE.findall("A four steps process and a five-step foundation.")
        self.assertEqual([match.lower() for match in matches], ["four", "five"])

    def test_brand_name_is_not_overwritten_by_css_variable_names(self) -> None:
        engine = AuditEngine()
        parser = EvidenceParser("https://example.com/")
        parser.feed(SAMPLE_HTML)
        from audit_engine import PageEvidence

        page = PageEvidence(
            url="https://example.com/",
            status=200,
            elapsed_ms=10,
            size_bytes=len(SAMPLE_HTML),
            headers={},
            title="Example Studio | Websites",
            description=parser.meta["description"],
            html_lang="en",
            canonical=parser.canonical,
            h1=parser.h1,
            h2=parser.h2,
            links=parser.links,
            json_ld=parser.json_ld,
            text=" ".join(parser.visible_parts),
            raw_html=SAMPLE_HTML,
        )
        brand = engine.extract_brand([page], ":root { --gold: #d66b3d; --serif: 'Cormorant Garamond'; }")
        self.assertEqual(brand["name"], "Example Studio")

    def test_brand_extracts_logo_and_hero_image(self) -> None:
        engine = AuditEngine()
        parser = EvidenceParser("https://example.com/")
        parser.feed(SAMPLE_HTML)
        from audit_engine import PageEvidence

        page = PageEvidence(
            url="https://example.com/",
            status=200,
            elapsed_ms=10,
            size_bytes=len(SAMPLE_HTML),
            headers={},
            title="Example Studio | Websites",
            description=parser.meta["description"],
            html_lang="en",
            canonical=parser.canonical,
            h1=parser.h1,
            h2=parser.h2,
            links=parser.links,
            json_ld=parser.json_ld,
            text=" ".join(parser.visible_parts),
            image_assets=parser.image_assets,
            meta=parser.meta,
            raw_html=SAMPLE_HTML,
        )
        brand = engine.extract_brand(
            [page],
            ".hero { background-image: url('/hero.jpg'); } :root { --brand: #17324d; --accent: #d66b3d; }",
        )
        self.assertEqual(brand["logo_url"], "https://example.com/logo.png")
        self.assertEqual(brand["hero_image_url"], "https://example.com/hero.jpg")


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_output_dir = ROOT / "outputs" / "_archived" / "test-runs"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

    def test_app_contract_uses_html_source_and_pdf_exports(self) -> None:
        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        static_text = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        audit_engine_text = (ROOT / "audit_engine.py").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("/pdf/slide", app_text)
        self.assertIn("/pdf/document", app_text)
        self.assertIn("slide_pdf_url", app_text)
        self.assertIn("document_pdf_url", app_text)
        self.assertIn("Slide PDF", static_text)
        self.assertIn("Document PDF", static_text)
        self.assertIn("playwright", requirements)
        self.assertIn("openai", requirements)
        self.assertIn("WEBSITE_AUDIT_LLM_API_BASE", audit_engine_text)
        self.assertIn("WEBSITE_AUDIT_LLM_API_KEY", audit_engine_text)
        self.assertIn("litellm.OpenAI(**client_kwargs)", audit_engine_text)
        self.assertIn("from openai import OpenAI", audit_engine_text)
        self.assertIn("conversion_not_run() if mode == \"visibility\"", audit_engine_text)
        self.assertNotIn("/docx", app_text)
        self.assertNotIn("docx_url", app_text)
        self.assertNotIn("python-docx", requirements)
        self.assertNotIn("pattern-scoring fallback", audit_engine_text)

    def test_visibility_mode_does_not_call_conversion_scoring(self) -> None:
        engine = AuditEngine()
        page = PageEvidence(
            url="https://example.com/",
            status=200,
            elapsed_ms=10,
            size_bytes=len(SAMPLE_HTML),
            headers={},
            title="Example Studio",
            description="Websites for established service businesses.",
            h1=["Turn an outdated website into a clear sales path."],
            h2=[],
            links=[],
            text="Example Studio helps service businesses improve website visibility.",
            raw_html=SAMPLE_HTML,
        )
        visibility = {
            "measured_score": 30,
            "measured_max": 70,
            "normalized_score": 43,
            "categories": [],
            "unmeasured": [],
            "findings": [],
        }

        with patch.object(engine, "crawl", return_value=[page]), \
             patch.object(engine, "fetch_status", return_value={"status": 200}), \
             patch.object(engine, "external_assets", return_value=("", "")), \
             patch.object(engine, "extract_brand", return_value={
                 "name": "Example Studio",
                 "primary_hex": "#17324d",
                 "accent_hex": "#d66b3d",
                 "primary_oklch": "oklch(0.3 0.05 250)",
                 "accent_oklch": "oklch(0.6 0.12 40)",
                 "fonts": [],
                 "display_font": "",
                 "body_font": "",
                 "logo_url": "",
                 "hero_image_url": "",
                 "source": "Test brand.",
             }), \
             patch.object(engine, "visibility_audit", return_value=visibility), \
             patch.object(engine, "design_audit", return_value={"score": 100, "findings": [], "note": "Test."}), \
             patch.object(engine, "conversion_audit", side_effect=AssertionError("conversion scoring should not run")):
            audit = engine.audit("https://example.com/", mode="visibility")

        self.assertEqual(audit["conversion"]["score_source"], "not_run")
        self.assertEqual(audit["conversion"]["score"], "N/A")
        self.assertEqual(audit["visibility"]["normalized_score"], 43)

    def test_report_renderer_escapes_site_text(self) -> None:
        audit = {
            "audit_id": "test",
            "generated_at": "2026-06-28T00:00:00+00:00",
            "url": "https://example.com/",
            "mode": "full",
            "brand": {
                "name": "Example <script>alert(1)</script>",
                "primary_oklch": "oklch(0.3 0.05 250)",
                "accent_oklch": "oklch(0.6 0.12 40)",
                "fonts": [],
                "display_font": "",
                "body_font": "",
                "primary_hex": "#17324d",
                "accent_hex": "#d66b3d",
                "logo_url": "",
                "hero_image_url": "",
                "source": "Detected.",
            },
            "executive_summary": "Evidence summary.",
            "conversion": {
                "score": 70,
                "root_layer": "Offer",
                "rewrite_eligible": False,
                "layers": [{"name": "Offer", "score": 10, "max": 20}],
                "findings": [],
            },
            "visibility": {
                "normalized_score": 60,
                "measured_score": 42,
                "measured_max": 70,
                "categories": [{"name": "Technical discovery", "score": 6, "max": 10}],
                "findings": [],
                "unmeasured": ["Core Web Vitals"],
            },
            "priorities": [],
            "what_to_keep": ["Existing title"],
            "client_review": {
                "headline": "Make the buying path easier.",
                "strengths": ["The opening is clear."],
                "visitor_view": [{"title": "Clear start", "text": "The first message is easy to understand.", "tone": "positive"}],
                "copy": {"quote": "Clear promise", "works": ["Direct."], "risks": ["Needs proof."]},
                "design": {"works": "Consistent.", "risk": "Review rendered pages."},
                "main_next_step": "Lead with one clear audit CTA before the full inquiry.",
                "conversion_path": [
                    {"name": "Offer", "plain_name": "What people can buy", "score": 10, "max": 20, "to_10": "Clarify the offer."}
                ],
                "visibility_path": [
                    {"name": "Can search engines find it?", "score": 6, "max": 10, "to_10": "Complete crawl files."}
                ],
                "visibility_explanation": "Clear answers and clear business facts are different checks.",
            },
            "opportunities": [
                {
                    "title": "Add a small-favor lead magnet before the main inquiry",
                    "why": "The site asks for commitment before giving a small win.",
                    "format": "Scorecard or audit",
                    "next_step": "Use it to open the sales conversation.",
                }
            ],
            "seven_day_plan": ["Fix the offer ladder."],
            "limitations": ["Directional score."],
        }
        with patch.object(report_renderer, "OUTPUT_DIR", self.test_output_dir):
            report_id, path = render_report(audit, "test-report")
        html = path.read_text(encoding="utf-8")
        self.assertEqual(report_id, "test-report")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("Example &lt;script&gt;", html)
        self.assertNotIn(".pptx", html)
        self.assertNotIn("PowerPoint", html)
        self.assertNotIn(".docx", html)
        self.assertNotIn("Word", html)
        self.assertIn('href="test-report-specialist.html"', html)
        self.assertIn("Direct.", html)
        self.assertIn("Needs proof.", html)
        self.assertIn("Main next step:", html)

    def test_report_bundle_creates_html_source_specialist_and_index_reports(self) -> None:
        audit = {
            "audit_id": "test",
            "generated_at": "2026-06-29T00:00:00+00:00",
            "url": "https://example.com/",
            "mode": "full",
            "desired_outcome": "",
            "brand": {
                "name": "Example Studio",
                "primary_hex": "#17324d",
                "accent_hex": "#d66b3d",
                "primary_oklch": "oklch(0.3 0.05 250)",
                "accent_oklch": "oklch(0.6 0.12 40)",
                "fonts": [],
                "display_font": "Georgia",
                "body_font": "Arial",
                "logo_url": "",
                "hero_image_url": "",
                "source": "Detected.",
            },
            "executive_summary": "Evidence summary.",
            "conversion": {
                "score": 70,
                "root_layer": "Offer",
                "rewrite_eligible": False,
                "layers": [{"name": "Offer", "score": 10, "max": 20}],
                "findings": [],
            },
            "visibility": {
                "normalized_score": 60,
                "measured_score": 42,
                "measured_max": 70,
                "categories": [{"name": "Technical discovery", "score": 6, "max": 10}],
                "findings": [],
                "unmeasured": ["Core Web Vitals"],
            },
            "priorities": [],
            "what_to_keep": ["Existing title"],
            "client_review": {
                "headline": "Make the buying path easier.",
                "strengths": ["The opening is clear."],
                "visitor_view": [{"title": "Clear start", "text": "The first message is easy to understand.", "tone": "positive"}],
                "copy": {"quote": "Clear promise", "works": ["Direct."], "risks": ["Needs proof."]},
                "design": {"works": "Consistent.", "risk": "Review rendered pages."},
                "main_next_step": "Lead with one clear audit CTA before the full inquiry.",
                "conversion_path": [
                    {"name": "Offer", "plain_name": "What people can buy", "score": 10, "max": 20, "to_10": "Clarify the offer."}
                ],
                "visibility_path": [
                    {"name": "Can search engines find it?", "score": 6, "max": 10, "to_10": "Complete crawl files."}
                ],
                "visibility_explanation": "Clear answers and clear business facts are different checks.",
            },
            "opportunities": [
                {
                    "title": "Add a small-favor lead magnet before the main inquiry",
                    "why": "The site asks for commitment before giving a small win.",
                    "format": "Scorecard or audit",
                    "next_step": "Use it to open the sales conversation.",
                }
            ],
            "seven_day_plan": ["Fix the offer ladder."],
            "limitations": ["Automated check."],
        }
        with patch.object(report_renderer, "OUTPUT_DIR", self.test_output_dir):
            bundle = render_report_bundle(audit, "test-report-bundle")
        self.assertTrue(bundle["client_html"].is_file())
        self.assertTrue(bundle["specialist_html"].is_file())
        self.assertTrue(bundle["index_html"].is_file())
        self.assertNotIn("pptx", bundle)
        self.assertNotIn("docx", bundle)
        client_html = bundle["client_html"].read_text(encoding="utf-8")
        specialist_html = bundle["specialist_html"].read_text(encoding="utf-8")
        self.assertIn("Current conversion readiness", client_html)
        self.assertIn("Detailed audit", client_html)
        self.assertIn("Growth ideas", client_html)
        self.assertIn("Conversion readiness / 100", specialist_html)
        self.assertIn("priority__body", specialist_html)
        self.assertIn("Growth opportunities", specialist_html)


if __name__ == "__main__":
    unittest.main()

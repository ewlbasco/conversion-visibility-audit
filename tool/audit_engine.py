"""Bounded public-website evidence collection and directional audit scoring."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from ipaddress import ip_address
import json
import math
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests


MAX_RESPONSE_BYTES = 2_000_000
MAX_PAGES = 8
REQUEST_TIMEOUT = (4, 12)
USER_AGENT = "EdgewiseWebsiteAuditMVP/0.1 (+local evidence tool)"

PRICE_RE = re.compile(r"(?<!\w)(?:[$€£]\s?\d[\d,.]*|\d[\d,.]*\s?(?:USD|EUR|GBP))(?!\w)", re.I)
HEX_RE = re.compile(r"(?<![\w-])#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})(?![0-9a-fA-F])")
STEP_RE = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)[ -]?steps?\b",
    re.I,
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d[\d ().-]{7,}\d)")

DESIGN_BASICS = (
    "message",
    "contrast",
    "coherence",
    "whitespace",
    "spacing",
    "alignment",
)

PREMIUM_TERMS = (
    "luxury",
    "premium",
    "exclusive",
    "curated",
    "boutique",
    "bespoke",
    "artisanal",
    "high-end",
)

AMATEUR_PATTERNS = (
    "welcome to",
    "welcome to our website",
    "welcome to my",
    "click here",
    "learn more",
    "read more",
)

STEP_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

ABSTRACT_TERMS = (
    "clarity",
    "elevate",
    "elevated",
    "refined",
    "strategic",
    "premium",
    "intentional",
    "transform",
    "transformation",
)

PROOF_TERMS = (
    "testimonial",
    "case study",
    "case studies",
    "client results",
    "results",
    "review",
    "reviews",
    "portfolio",
    "before and after",
)

STRONG_PROOF_TERMS = (
    "testimonial",
    "case study",
    "case studies",
    "client result",
    "client results",
    "verified review",
    "verified reviews",
    "before and after",
    "before-and-after",
)

AUDIENCE_TERMS = (
    "for business owners",
    "for founders",
    "for teams",
    "for companies",
    "for small businesses",
    "for established businesses",
    "business owners",
    "entrepreneurs",
    "service businesses",
)

OUTCOME_TERMS = (
    "so you can",
    "helps you",
    "help you",
    "from",
    "to",
    "increase",
    "reduce",
    "avoid",
    "grow",
    "book",
    "launch",
    "outgrown",
)

GENERIC_BUSINESS_OPENERS = (
    "we help",
    "we provide",
    "we create",
    "we offer",
    "our mission",
    "our goal",
    "welcome to",
)

PRIMARY_CTA_TERMS = (
    "start",
    "book",
    "apply",
    "contact",
    "project",
    "get",
    "check",
    "schedule",
    "inquire",
    "enquire",
    "call",
    "audit",
    "review",
    "roadmap",
)

LOW_FRICTION_TERMS = (
    "quiz",
    "guide",
    "checklist",
    "template",
    "toolkit",
    "calculator",
    "estimate",
    "scorecard",
    "audit",
    "roadmap",
    "download",
    "free review",
)

HIGH_COMMITMENT_TERMS = (
    "book",
    "contact",
    "apply",
    "project",
    "call",
    "consultation",
    "inquire",
    "enquire",
)

BUSINESS_SEGMENTS = {
    "home-services": (
        "kitchen",
        "bathroom",
        "roof",
        "roofing",
        "remodel",
        "renovation",
        "hvac",
        "plumbing",
        "electric",
        "contractor",
        "landscaping",
        "home services",
    ),
    "beauty-wellness": (
        "salon",
        "beauty",
        "hair",
        "stylist",
        "spa",
        "lissage",
        "skincare",
        "wellness",
        "medspa",
        "treatment",
    ),
    "professional-services": (
        "agency",
        "studio",
        "consultant",
        "consulting",
        "coach",
        "strategy",
        "design",
        "branding",
        "marketing",
        "website",
        "copywriting",
        "creative",
    ),
}


class UnsafeUrlError(ValueError):
    """Raised when a submitted URL could reach a non-public network target."""


@dataclass
class Finding:
    title: str
    layer: str
    location: str
    evidence: str
    impact: str
    root_cause: str
    fix: str
    owner: str
    severity: str = "medium"
    category: str = "conversion"

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "layer": self.layer,
            "location": self.location,
            "evidence": self.evidence,
            "impact": self.impact,
            "root_cause": self.root_cause,
            "fix": self.fix,
            "owner": self.owner,
            "severity": self.severity,
            "category": self.category,
        }


@dataclass
class DesignFinding:
    title: str
    category: str
    location: str
    evidence: str
    impact: str
    fix: str
    severity: str = "medium"
    source: str = "visual-creator-html"

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "category": self.category,
            "location": self.location,
            "evidence": self.evidence,
            "impact": self.impact,
            "fix": self.fix,
            "severity": self.severity,
            "source": self.source,
        }


@dataclass
class PageEvidence:
    url: str
    status: int
    elapsed_ms: int
    size_bytes: int
    headers: dict[str, str]
    title: str = ""
    description: str = ""
    html_lang: str = ""
    canonical: str = ""
    hreflangs: list[dict[str, str]] = field(default_factory=list)
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    stylesheets: list[str] = field(default_factory=list)
    inline_css: str = ""
    json_ld: list[Any] = field(default_factory=list)
    text: str = ""
    form_controls: int = 0
    labels: int = 0
    images: int = 0
    images_without_alt: int = 0
    buttons: list[str] = field(default_factory=list)
    image_assets: list[dict[str, str]] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)
    raw_html: str = ""

    def as_dict(self) -> dict[str, Any]:
        result = self.__dict__.copy()
        result.pop("raw_html", None)
        result.pop("inline_css", None)
        result.pop("headers", None)
        result["text"] = self.text[:500]
        return result


class EvidenceParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.current_heading: str | None = None
        self.heading_parts: list[str] = []
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.meta: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.current_link: dict[str, str] | None = None
        self.current_link_text: list[str] = []
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.inline_css_parts: list[str] = []
        self.collect_style = False
        self.collect_json = False
        self.json_parts: list[str] = []
        self.json_ld: list[Any] = []
        self.visible_parts: list[str] = []
        self.ignore_depth = 0
        self.form_controls = 0
        self.labels = 0
        self.images = 0
        self.images_without_alt = 0
        self.image_assets: list[dict[str, str]] = []
        self.buttons: list[str] = []
        self.current_button = False
        self.button_parts: list[str] = []
        self.html_lang = ""
        self.canonical = ""
        self.hreflangs: list[dict[str, str]] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): (value or "") for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        data = self._attrs(attrs)
        if tag == "html":
            self.html_lang = data.get("lang", "")
        if tag in {"script", "style", "noscript", "template"}:
            self.ignore_depth += 1
        if tag == "title":
            self.current_heading = "title"
        elif tag in {"h1", "h2"}:
            self.current_heading = tag
            self.heading_parts = []
        elif tag == "meta":
            key = (data.get("name") or data.get("property") or "").lower()
            if key:
                self.meta[key] = data.get("content", "").strip()
        elif tag == "link":
            rel = data.get("rel", "").lower().split()
            href = urljoin(self.base_url, data.get("href", ""))
            if "canonical" in rel:
                self.canonical = href
            if "alternate" in rel and data.get("hreflang"):
                self.hreflangs.append({"lang": data["hreflang"], "href": href})
            if "stylesheet" in rel and href:
                self.stylesheets.append(href)
        elif tag == "a":
            self.current_link = {"href": urljoin(self.base_url, data.get("href", "")), "text": ""}
            self.current_link_text = []
        elif tag == "script":
            src = urljoin(self.base_url, data.get("src", ""))
            if src:
                self.scripts.append(src)
            if data.get("type", "").lower() == "application/ld+json":
                self.collect_json = True
                self.json_parts = []
        elif tag == "style":
            self.collect_style = True
        elif tag in {"input", "select", "textarea"}:
            if not (tag == "input" and data.get("type", "").lower() == "hidden"):
                self.form_controls += 1
        elif tag == "label":
            self.labels += 1
        elif tag == "img":
            self.images += 1
            if "alt" not in data:
                self.images_without_alt += 1
            src = urljoin(self.base_url, data.get("src") or data.get("data-src") or "")
            if src:
                self.image_assets.append(
                    {
                        "src": src,
                        "alt": clean_text(data.get("alt", "")),
                        "class": clean_text(data.get("class", "")),
                    }
                )
        elif tag == "button":
            self.current_button = True
            self.button_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template"}:
            self.ignore_depth = max(0, self.ignore_depth - 1)
        if tag == "title" and self.current_heading == "title":
            self.current_heading = None
        elif tag in {"h1", "h2"} and self.current_heading == tag:
            text = clean_text(" ".join(self.heading_parts))
            if text:
                (self.h1 if tag == "h1" else self.h2).append(text)
            self.current_heading = None
            self.heading_parts = []
        elif tag == "a" and self.current_link is not None:
            self.current_link["text"] = clean_text(" ".join(self.current_link_text))
            self.links.append(self.current_link)
            self.current_link = None
            self.current_link_text = []
        elif tag == "script" and self.collect_json:
            payload = "".join(self.json_parts).strip()
            if payload:
                try:
                    parsed = json.loads(payload)
                    if isinstance(parsed, list):
                        self.json_ld.extend(parsed)
                    else:
                        self.json_ld.append(parsed)
                except json.JSONDecodeError:
                    pass
            self.collect_json = False
            self.json_parts = []
        elif tag == "style":
            self.collect_style = False
        elif tag == "button" and self.current_button:
            text = clean_text(" ".join(self.button_parts))
            if text:
                self.buttons.append(text)
            self.current_button = False
            self.button_parts = []

    def handle_data(self, data: str) -> None:
        if self.collect_json:
            self.json_parts.append(data)
            return
        if self.collect_style:
            self.inline_css_parts.append(data)
            return
        if self.current_heading == "title":
            self.title_parts.append(data)
        elif self.current_heading in {"h1", "h2"}:
            self.heading_parts.append(data)
        if self.current_link is not None:
            self.current_link_text.append(data)
        if self.current_button:
            self.button_parts.append(data)
        if self.ignore_depth == 0:
            text = clean_text(data)
            if text:
                self.visible_parts.append(text)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Enter a website URL.")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Use a valid http or https website URL.")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URLs containing credentials are not allowed.")
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def assert_public_url(url: str) -> None:
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrlError("The URL has no hostname.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve {hostname}.") from exc
    for raw in addresses:
        candidate = ip_address(raw)
        if (
            candidate.is_private
            or candidate.is_loopback
            or candidate.is_link_local
            or candidate.is_multicast
            or candidate.is_reserved
            or candidate.is_unspecified
        ):
            raise UnsafeUrlError("Local, private, and reserved network targets are blocked.")


def normalize_hex(raw: str) -> str:
    raw = raw.lower()
    if len(raw) == 3:
        raw = "".join(char * 2 for char in raw)
    return f"#{raw}"


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def relative_luminance(value: str) -> float:
    rgb = [component / 255 for component in hex_rgb(value)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = [linear(channel) for channel in rgb]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def color_distance(first: str, second: str) -> float:
    a = hex_rgb(first)
    b = hex_rgb(second)
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


def hex_to_oklch(value: str) -> str:
    red, green, blue = [component / 255 for component in hex_rgb(value)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = linear(red), linear(green), linear(blue)
    l_value = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    m_value = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    s_value = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    l_root, m_root, s_root = (
        math.copysign(abs(channel) ** (1 / 3), channel)
        for channel in (l_value, m_value, s_value)
    )
    lightness = 0.2104542553 * l_root + 0.793617785 * m_root - 0.0040720468 * s_root
    a_value = 1.9779984951 * l_root - 2.428592205 * m_root + 0.4505937099 * s_root
    b_value = 0.0259040371 * l_root + 0.7827717662 * m_root - 0.808675766 * s_root
    chroma = math.sqrt(a_value * a_value + b_value * b_value)
    hue = math.degrees(math.atan2(b_value, a_value)) % 360
    return f"oklch({lightness:.3f} {chroma:.3f} {hue:.1f})"


class AuditEngine:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})

    def fetch(self, url: str, *, allow_non_html: bool = False) -> tuple[requests.Response, bytes]:
        current_url = url
        response: requests.Response | None = None
        for _ in range(6):
            assert_public_url(current_url)
            response = self.session.get(
                current_url,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=False,
            )
            if response.status_code not in {301, 302, 303, 307, 308}:
                break
            location = response.headers.get("location")
            response.close()
            if not location:
                break
            current_url = urljoin(current_url, location)
        else:
            raise ValueError("The site exceeded the five-redirect MVP limit.")
        if response is None:
            raise ValueError("The website returned no response.")
        assert_public_url(response.url)
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(32_768):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ValueError(f"Response exceeded the {MAX_RESPONSE_BYTES // 1_000_000} MB MVP limit.")
            chunks.append(chunk)
        payload = b"".join(chunks)
        content_type = response.headers.get("content-type", "").lower()
        if not allow_non_html and "html" not in content_type:
            raise ValueError(f"Expected HTML but received {content_type or 'an unknown content type'}.")
        return response, payload

    def parse_page(self, url: str) -> PageEvidence:
        response, payload = self.fetch(url)
        encoding = response.encoding or "utf-8"
        html = payload.decode(encoding, errors="replace")
        parser = EvidenceParser(response.url)
        parser.feed(html)
        return PageEvidence(
            url=response.url,
            status=response.status_code,
            elapsed_ms=round(response.elapsed.total_seconds() * 1000),
            size_bytes=len(payload),
            headers={key.lower(): value for key, value in response.headers.items()},
            title=clean_text(" ".join(parser.title_parts)),
            description=parser.meta.get("description", ""),
            html_lang=parser.html_lang,
            canonical=parser.canonical,
            hreflangs=parser.hreflangs,
            h1=parser.h1,
            h2=parser.h2,
            links=parser.links,
            scripts=parser.scripts,
            stylesheets=parser.stylesheets,
            inline_css="\n".join(parser.inline_css_parts),
            json_ld=parser.json_ld,
            text=clean_text(" ".join(parser.visible_parts)),
            form_controls=parser.form_controls,
            labels=parser.labels,
            images=parser.images,
            images_without_alt=parser.images_without_alt,
            buttons=parser.buttons,
            image_assets=parser.image_assets,
            meta=parser.meta,
            raw_html=html,
        )

    def crawl(self, root_url: str) -> list[PageEvidence]:
        homepage = self.parse_page(root_url)
        root = urlsplit(homepage.url)
        candidates: list[tuple[int, str]] = []
        priority_terms = {
            "service": 1,
            "offer": 1,
            "pricing": 1,
            "blueprint": 1,
            "process": 2,
            "faq": 2,
            "about": 3,
            "contact": 3,
            "connect": 3,
            "work": 4,
            "case": 4,
        }
        seen = {homepage.url.rstrip("/")}
        for link in homepage.links:
            href = link["href"].split("#", 1)[0]
            parsed = urlsplit(href)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != root.netloc:
                continue
            normalized = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))
            key = normalized.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            lowered = f"{parsed.path} {link['text']}".lower()
            priority = min((rank for term, rank in priority_terms.items() if term in lowered), default=8)
            candidates.append((priority, normalized))
        pages = [homepage]
        for _, url in sorted(candidates, key=lambda item: (item[0], len(item[1])))[: MAX_PAGES - 1]:
            try:
                pages.append(self.parse_page(url))
            except (requests.RequestException, ValueError):
                continue
        return pages

    def fetch_status(self, url: str) -> dict[str, Any]:
        try:
            response, payload = self.fetch(url, allow_non_html=True)
            return {
                "url": response.url,
                "status": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "size_bytes": len(payload),
            }
        except (requests.RequestException, ValueError) as exc:
            return {"url": url, "status": 0, "error": str(exc), "size_bytes": 0}

    def external_assets(self, homepage: PageEvidence) -> tuple[str, str]:
        css_parts = [homepage.inline_css, homepage.raw_html]
        for stylesheet in homepage.stylesheets[:3]:
            if urlsplit(stylesheet).netloc != urlsplit(homepage.url).netloc:
                continue
            try:
                _, payload = self.fetch(stylesheet, allow_non_html=True)
                css_parts.append(payload.decode("utf-8", errors="replace"))
            except (requests.RequestException, ValueError):
                continue
        script_parts: list[str] = []
        for script in homepage.scripts[:3]:
            if urlsplit(script).netloc != urlsplit(homepage.url).netloc:
                continue
            try:
                _, payload = self.fetch(script, allow_non_html=True)
                script_parts.append(payload.decode("utf-8", errors="replace"))
            except (requests.RequestException, ValueError):
                continue
        return "\n".join(css_parts), "\n".join(script_parts)

    def extract_brand(self, pages: list[PageEvidence], css_text: str) -> dict[str, Any]:
        homepage = pages[0]
        schema_names: list[str] = []
        for item in homepage.json_ld:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                schema_names.append(item["name"])
        title_name = re.split(r"\s+[|–—-]\s+", homepage.title)[0].strip()
        name = schema_names[0] if schema_names else title_name or urlsplit(homepage.url).hostname or "Website"

        colors = Counter(normalize_hex(match) for match in HEX_RE.findall(css_text))
        all_usable = [c for c, _ in colors.most_common(100) if relative_luminance(c) < 0.97]

        var_colors: dict[str, str] = {}
        for var_match in re.finditer(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*", css_text):
            vname = var_match.group(1).lower()
            vhex = normalize_hex(var_match.group(2).lstrip("#"))
            var_colors[vname] = vhex

        primary_hint = next(
            (h for name, h in var_colors.items() if any(k in name for k in ("brand", "primary", "navy", "dark"))),
            "",
        )
        accent_hint = next(
            (h for name, h in var_colors.items() if any(k in name for k in ("accent", "orange", "secondary", "highlight", "cta"))),
            "",
        )

        if primary_hint:
            primary = primary_hint
        else:
            dark_candidates = [c for c in all_usable if relative_luminance(c) < 0.18]
            primary = dark_candidates[0] if dark_candidates else (all_usable[0] if all_usable else "#1f2937")

        if accent_hint and color_distance(primary, accent_hint) > 40:
            accent = accent_hint
        else:
            chromatic = [c for c in all_usable if max(hex_rgb(c)) - min(hex_rgb(c)) >= 35 and 0.05 < relative_luminance(c) < 0.85]
            accent = next((c for c in chromatic if color_distance(primary, c) > 70), "#b85c38")
        variable_fonts: dict[str, str] = {}
        for variable_name, raw_value in re.findall(r"(--[\w-]+)\s*:\s*([^;}{]+)", css_text, re.I):
            candidate = raw_value.split(",")[0].strip().strip("'\"")
            candidate = re.sub(r"[^A-Za-z0-9 _-]", "", candidate).strip()
            if candidate:
                variable_fonts[variable_name.lower()] = candidate
        display_font = next(
            (
                value
                for name, value in variable_fonts.items()
                if any(term in name for term in ("serif", "display", "heading", "title"))
            ),
            "",
        )
        body_font = next(
            (
                value
                for name, value in variable_fonts.items()
                if any(term in name for term in ("sans", "body", "text"))
            ),
            "",
        )
        font_matches = re.findall(r"font-family\s*:\s*([^;}{]+)", css_text, re.I)
        fonts = []
        for raw in font_matches:
            candidate = raw.split(",")[0].strip().strip("'\"")
            variable_match = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", candidate)
            if variable_match:
                definition = re.search(
                    rf"{re.escape(variable_match.group(1))}\s*:\s*([^;}}{{]+)",
                    css_text,
                    re.I,
                )
                if definition:
                    candidate = definition.group(1).split(",")[0].strip().strip("'\"")
            candidate = re.sub(r"[^A-Za-z0-9 _-]", "", candidate).strip()
            if (
                candidate
                and not candidate.startswith("--")
                and candidate.lower() not in {"inherit", "initial", "sans-serif", "serif", "var"}
            ):
                fonts.append(candidate)
        font_counts = Counter(fonts)
        detected_fonts = [name for name, _ in font_counts.most_common(2)]
        if not display_font:
            display_font = detected_fonts[0] if detected_fonts else ""
        if not body_font:
            body_font = next((font for font in detected_fonts if font != display_font), "")

        logo_url = ""
        for asset in homepage.image_assets:
            marker = f"{asset.get('src', '')} {asset.get('alt', '')} {asset.get('class', '')}".lower()
            if "logo" in marker or clean_text(name).lower() in marker:
                logo_url = asset["src"]
                break

        css_image_urls = [
            urljoin(homepage.url, clean_text(raw))
            for raw in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)['\"]?\s*\)", css_text, re.I)
            if not raw.lower().endswith((".ttf", ".otf", ".woff", ".woff2", ".eot"))
        ]
        social_image = homepage.meta.get("og:image") or homepage.meta.get("twitter:image") or ""
        hero_url = urljoin(homepage.url, social_image) if social_image else ""
        if not hero_url:
            hero_url = next(
                (
                    image_url
                    for image_url in css_image_urls
                    if re.search(r"\.(?:jpe?g|png|webp|avif)(?:\?|$)", image_url, re.I)
                    and image_url != logo_url
                ),
                "",
            )
        if not hero_url:
            hero_url = next(
                (
                    asset["src"]
                    for asset in homepage.image_assets
                    if asset["src"] != logo_url
                ),
                "",
            )
        hero_url = re.sub(r"['\"()]", "", hero_url)

        button_radius = ""
        radius_match = re.search(
            r"(?:button|btn|cta)[^{]*\{[^}]*border-radius\s*:\s*([^;}{]+)",
            css_text,
            re.I,
        )
        if radius_match:
            button_radius = clean_text(radius_match.group(1))
        return {
            "name": clean_text(name),
            "primary_hex": primary,
            "accent_hex": accent,
            "primary_oklch": hex_to_oklch(primary),
            "accent_oklch": hex_to_oklch(accent),
            "fonts": detected_fonts,
            "display_font": display_font,
            "body_font": body_font,
            "logo_url": logo_url,
            "hero_image_url": hero_url,
            "button_radius": button_radius,
            "source": "Detected from public HTML, CSS, fonts, and image assets. A rendered-page check is still required.",
        }

    def audit(self, url: str, mode: str = "full", context: str = "") -> dict[str, Any]:
        root_url = normalize_url(url)
        if mode not in {"conversion", "visibility", "full"}:
            raise ValueError("Choose conversion, visibility, or full.")
        pages = self.crawl(root_url)
        homepage = pages[0]
        origin = f"{urlsplit(homepage.url).scheme}://{urlsplit(homepage.url).netloc}"
        robots = self.fetch_status(urljoin(origin, "/robots.txt"))
        sitemap = self.fetch_status(urljoin(origin, "/sitemap.xml"))
        css_text, script_text = self.external_assets(homepage)
        brand = self.extract_brand(pages, css_text)
        conversion = self.conversion_audit(pages, context)
        visibility = self.visibility_audit(pages, robots, sitemap, script_text)
        design = self.design_audit(pages, css_text)
        findings: list[Finding] = []
        if mode in {"conversion", "full"}:
            findings.extend(conversion["findings"])
        if mode in {"visibility", "full"}:
            findings.extend(visibility["findings"])
        findings.sort(key=lambda item: {"critical": 0, "high": 1, "medium": 2, "low": 3}[item.severity])
        priorities = findings[:7]
        keep = self.what_to_keep(pages, robots, sitemap)
        plan = self.seven_day_plan(priorities)
        executive = self.executive_summary(brand["name"], conversion, visibility, mode)
        client_review = self.client_review(pages, conversion, visibility, keep)
        opportunities = self.opportunity_scan(pages, conversion)
        return {
            "audit_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "url": homepage.url,
            "mode": mode,
            "desired_outcome": clean_text(context),
            "brand": brand,
            "executive_summary": executive,
            "conversion": {
                "score": conversion["score"],
                "layers": conversion["layers"],
                "root_layer": conversion["root_layer"],
                "rewrite_eligible": conversion["rewrite_eligible"],
                "findings": [finding.as_dict() for finding in conversion["findings"]],
            },
            "visibility": {
                "measured_score": visibility["measured_score"],
                "measured_max": visibility["measured_max"],
                "normalized_score": visibility["normalized_score"],
                "categories": visibility["categories"],
                "unmeasured": visibility["unmeasured"],
                "findings": [finding.as_dict() for finding in visibility["findings"]],
            },
            "design": design,
            "priorities": [finding.as_dict() for finding in priorities],
            "what_to_keep": keep,
            "client_review": client_review,
            "opportunities": opportunities,
            "seven_day_plan": plan,
            "pages": [page.as_dict() for page in pages],
            "crawl": {"robots": robots, "sitemap": sitemap},
            "limitations": [
                "Scores are automated directional indicators, not a substitute for final strategic review.",
                "This local build reads server HTML and linked public CSS/JavaScript, but it does not execute a rendered browser session.",
                "Core Web Vitals, rendered visual hierarchy, contrast, keyboard behavior, analytics, backlinks, rankings, competitors, and AI-platform citations are not measured in this MVP.",
                "Detected brand colors and fonts are public-code cues and must be verified before client delivery.",
                "A complete conversion judgment also requires rendered desktop and mobile review plus strategic copy review.",
                "The design score is a heuristic scan based on HTML/CSS signals (typography count, color palette size, premium language balance, alt-text coverage). A full rendered visual audit requires the hallmark skill or a human designer.",
            ],
        }

    def conversion_audit(self, pages: list[PageEvidence], context: str) -> dict[str, Any]:
        homepage = pages[0]
        all_text = " ".join(page.text for page in pages).lower()
        title_meta = " ".join([homepage.title, homepage.description, context]).lower()
        findings: list[Finding] = []
        business_context = self.infer_business_context(pages)
        layers = {
            "Business / Positioning": 20,
            "Messaging": 20,
            "Offer": 20,
            "Trust": 20,
            "Conversion": 20,
        }

        audience_signal = any(term in all_text for term in AUDIENCE_TERMS)
        outcome_signal = any(term in f"{title_meta} {all_text[:4000]}" for term in OUTCOME_TERMS)
        descriptor_groups = {
            label
            for label, terms in {
                "premium": ("premium", "luxury", "high-end"),
                "small-business": ("small business", "new business", "startup"),
                "local": ("local", "near me", "key west"),
                "worldwide": ("worldwide", "global", "nationwide"),
                "established": ("established", "years of experience", "outgrown"),
            }.items()
            if any(term in all_text for term in terms)
        }
        if not audience_signal:
            layers["Business / Positioning"] -= 5
            findings.append(
                Finding(
                    "The target buyer is not stated explicitly",
                    "Business / Positioning",
                    "Homepage opening and audited service pages",
                    "No direct audience phrase such as 'for business owners' or 'for established businesses' was detected.",
                    "Visitors must infer whether the service is intended for them.",
                    "The site describes services before fixing a concrete buyer boundary.",
                    "State one primary buyer and one disqualifying boundary in the homepage opening and service introduction.",
                    "conversion-engine",
                    "high",
                )
            )
        if not outcome_signal:
            layers["Business / Positioning"] -= 5
            findings.append(
                Finding(
                    "The transformation is difficult to verify",
                    "Business / Positioning",
                    "Homepage title, description, and opening copy",
                    f"Title and description: {homepage.title!r} / {homepage.description!r}.",
                    "The visitor cannot quickly name the business result they are buying.",
                    "The opening relies on category language without a concrete before-and-after state.",
                    "Define the before state, after state, and business consequence in one short promise.",
                    "conversion-engine",
                    "high",
                )
            )
        if len(descriptor_groups) >= 4:
            layers["Business / Positioning"] -= 4
            findings.append(
                Finding(
                    "The business category sends competing audience signals",
                    "Business / Positioning",
                    "Homepage, metadata, schema, and service pages",
                    f"Detected positioning groups: {', '.join(sorted(descriptor_groups))}.",
                    "Different buyers can read the same brand as serving different market levels or geographies.",
                    "Tactical offers and category descriptors are not governed by one positioning source.",
                    "Choose one primary market frame and label secondary offers as explicit exceptions.",
                    "conversion-engine",
                    "high",
                )
            )

        if not homepage.h1:
            layers["Messaging"] -= 8
            findings.append(
                Finding(
                    "The homepage has no detectable H1",
                    "Messaging",
                    homepage.url,
                    "No H1 was found in the returned HTML.",
                    "Visitors and search systems lose the page's primary message.",
                    "The page template does not expose a semantic primary heading.",
                    "Add one visitor-outcome H1 that matches the visible opening.",
                    "conversion-engine",
                    "critical",
                )
            )
        else:
            opening = homepage.h1[0].lower()
            if any(opening.startswith(term) for term in GENERIC_BUSINESS_OPENERS):
                layers["Messaging"] -= 4
                findings.append(
                    Finding(
                        "The opening starts from the business instead of the buyer",
                        "Messaging",
                        "Homepage H1",
                        homepage.h1[0],
                        "The visitor must translate the service language into their own problem before they can care.",
                        "The opening introduces the company before naming the buyer's costly situation or desired outcome.",
                        "Lead with the buyer's stuck moment, desired outcome, or costly problem before naming the service.",
                        "conversion-engine",
                        "medium",
                    )
                )
            if len(homepage.h1[0]) > 100:
                layers["Messaging"] -= 3
                findings.append(
                    Finding(
                        "The primary message carries too many ideas",
                        "Messaging",
                        "Homepage H1",
                        homepage.h1[0],
                        "The visitor must parse a long statement before understanding the page.",
                        "The headline is doing the work of both promise and explanation.",
                        "Keep the H1 to one decision or outcome and move mechanism detail below it.",
                        "conversion-engine",
                        "medium",
                    )
                )
        step_numbers: set[int] = set()
        for page in pages:
            source = f"{page.description} {page.text}"
            for match in STEP_RE.findall(source):
                step_numbers.add(STEP_WORDS.get(match.lower(), int(match) if match.isdigit() else 0))
        step_numbers.discard(0)
        if len(step_numbers) > 1:
            layers["Messaging"] -= 6
            findings.append(
                Finding(
                    "The stated process count contradicts itself",
                    "Messaging",
                    "Process-related metadata and body copy",
                    f"Detected process counts: {', '.join(str(number) for number in sorted(step_numbers))}.",
                    "A process meant to reduce uncertainty instead creates doubt about delivery details.",
                    "Metadata and page copy were updated independently.",
                    "Choose one process count and update metadata, headings, translations, and FAQ references together.",
                    "conversion-engine",
                    "high",
                )
            )
        abstract_count = sum(all_text.count(term) for term in ABSTRACT_TERMS)
        proof_count = sum(all_text.count(term) for term in STRONG_PROOF_TERMS)
        if abstract_count >= 18 and proof_count < 3:
            layers["Messaging"] -= 4
            findings.append(
                Finding(
                    "Abstract brand language outweighs concrete evidence",
                    "Messaging",
                    "Audited page copy",
                    f"Detected {abstract_count} uses of abstract positioning terms and {proof_count} proof-term references.",
                    "The site can sound polished without helping the buyer verify what changes.",
                    "Repeated category language is compensating for limited examples and outcomes.",
                    "Replace repeated abstractions with specific decisions, deliverables, before/after evidence, and buyer consequences.",
                    "conversion-engine",
                    "medium",
                )
            )

        prices = []
        for page in pages:
            prices.extend(PRICE_RE.findall(page.text))
        unique_prices = list(dict.fromkeys(prices))
        has_low_friction_asset = any(term in all_text for term in LOW_FRICTION_TERMS)
        if len(unique_prices) > 6:
            layers["Offer"] -= 8
            findings.append(
                Finding(
                    "The offer architecture creates excessive choice",
                    "Offer",
                    "Audited service and pricing pages",
                    f"Detected {len(unique_prices)} distinct visible price points: {', '.join(unique_prices[:10])}.",
                    "The buyer must compare many possible entry points before knowing the intended path.",
                    "Packages are presented as a catalogue instead of a small decision ladder.",
                    "Reduce the public offer ladder to three primary routes and move seasonal or custom work beneath them.",
                    "conversion-engine",
                    "critical",
                )
            )
        elif not unique_prices:
            layers["Offer"] -= 3
            findings.append(
                Finding(
                    "The site gives no visible price anchor",
                    "Offer",
                    "Audited pages",
                    "No currency-based price was detected.",
                    "Qualified buyers cannot estimate fit before entering the inquiry path.",
                    "Pricing is fully deferred to sales.",
                    "Add a starting price, range, or clear qualification threshold.",
                    "conversion-engine",
                    "medium",
                )
            )
        if len(unique_prices) >= 2:
            numeric_prices = []
            for price in unique_prices:
                digits = re.sub(r"[^\d]", "", price)
                if digits:
                    numeric_prices.append((int(digits), price))
            close_pairs = [
                (left[1], right[1])
                for index, left in enumerate(numeric_prices)
                for right in numeric_prices[index + 1 :]
                if 0 < abs(left[0] - right[0]) <= 150
            ]
            if close_pairs:
                layers["Offer"] -= 3
                first, second = close_pairs[0]
                findings.append(
                    Finding(
                        "Adjacent price points need a sharper fit distinction",
                        "Offer",
                        "Audited pricing copy",
                        f"Detected nearby price points {first} and {second}.",
                        "Buyers may not understand why one engagement exists separately from the other.",
                        "Package names and deliverables do not create a strong decision boundary.",
                        "State who should choose each offer, the outcome difference, and whether one fee credits toward the next.",
                    "conversion-engine",
                    "high",
                )
            )
        if len(unique_prices) >= 3 and not has_low_friction_asset:
            layers["Offer"] -= 3
            findings.append(
                Finding(
                    "The offer ladder has no chooser asset",
                    "Offer",
                    "Public offer pages and CTA path",
                    f"The site shows multiple routes or prices ({len(unique_prices)} price signals) without a diagnostic aid.",
                    "Visitors must self-select the right service path without guidance, which increases hesitation.",
                    "The public offer structure depends on the visitor making a strategic choice alone.",
                    business_context["chooser_fix"],
                    "conversion-engine",
                    "medium",
                )
            )

        if proof_count < 2:
            layers["Trust"] -= 8
            findings.append(
                Finding(
                    "Proof is not prominent enough for the promise",
                    "Trust",
                    "Audited homepage, service, process, and FAQ copy",
                    f"Only {proof_count} proof-term references were detected across {len(pages)} pages.",
                    "Buyers cannot independently verify the level of result or delivery quality.",
                    "The site relies on positioning and process language without enough outcome evidence.",
                    "Add validated case studies, named testimonials, before/after examples, or specific process artifacts beside major claims.",
                    "conversion-engine",
                    "high",
                )
            )
        if proof_count < 2 and business_context["segment"] in {"professional-services", "home-services", "beauty-wellness"}:
            layers["Trust"] -= 3
            findings.append(
                Finding(
                    "The site has no visible proof loop for a high-trust service",
                    "Trust",
                    "Homepage and audited service pages",
                    "The audit found limited case-study or testimonial evidence and no clear repeatable proof mechanism.",
                    "The buyer must trust the promise without seeing how proof is regularly created and captured.",
                    "Proof is treated as decoration instead of part of the service motion.",
                    business_context["proof_loop_fix"],
                    "conversion-engine",
                    "medium",
                )
            )
        if "recommend you first" in all_text:
            layers["Trust"] -= 5
            findings.append(
                Finding(
                    "An AI visibility claim exceeds what the service controls",
                    "Trust",
                    "AI visibility promise",
                    "The phrase 'recommend you first' was detected.",
                    "An absolute platform claim can reduce trust when the site shows no supporting measurement.",
                    "A desired outcome is written as a guarantee.",
                    "Describe controllable deliverables such as entity clarity, crawlability, structured data, and citable answers.",
                    "conversion-engine",
                    "high",
                )
            )
        if EMAIL_RE.search(all_text) or PHONE_RE.search(all_text):
            layers["Trust"] = min(20, layers["Trust"] + 2)

        max_controls = max((page.form_controls for page in pages), default=0)
        if max_controls > 10:
            layers["Conversion"] -= 6
            page = max(pages, key=lambda candidate: candidate.form_controls)
            findings.append(
                Finding(
                    "The first inquiry step collects discovery-level detail",
                    "Conversion",
                    page.url,
                    f"The largest form contains {page.form_controls} controls and {page.labels} labels.",
                    "High-intent visitors must invest substantial effort before fit is confirmed.",
                    "Lead capture and project discovery are combined into one form.",
                    "Lead with one primary audit or review CTA, keep the first form to six essential fields, and reveal project detail only after fit is confirmed.",
                    "conversion-engine",
                    "high",
                )
            )
        multi_h1_pages = [page for page in pages if len(page.h1) > 1]
        if multi_h1_pages:
            layers["Conversion"] -= 2
            findings.append(
                Finding(
                    "A page contains competing primary headings",
                    "Conversion",
                    multi_h1_pages[0].url,
                    f"Detected {len(multi_h1_pages[0].h1)} H1 elements: {multi_h1_pages[0].h1[:3]}.",
                    "The visual and semantic hierarchy can become ambiguous.",
                    "A section title is using the same heading level as the page title.",
                    "Keep one H1 and move subsequent major section titles to H2.",
                    "conversion-engine",
                    "medium",
                )
            )
        ctas = [text for page in pages for text in page.buttons + [link["text"] for link in page.links] if text]
        unique_ctas = list(dict.fromkeys(clean_text(text).lower() for text in ctas if clean_text(text)))
        low_friction_cta = any(any(term in text for term in LOW_FRICTION_TERMS) for text in unique_ctas)
        high_commitment_cta = any(any(term in text for term in HIGH_COMMITMENT_TERMS) for text in unique_ctas)
        if not any(term in " ".join(ctas).lower() for term in PRIMARY_CTA_TERMS):
            layers["Conversion"] -= 5
            findings.append(
                Finding(
                    "The next action is not explicit",
                    "Conversion",
                    "Audited links and buttons",
                    f"Detected CTA examples: {', '.join(ctas[:8]) or 'none'}.",
                    "Visitors cannot predict what happens after the click.",
                    "Navigation labels are carrying the conversion path.",
                    "Use one primary action label that names the next step and its commitment level.",
                    "conversion-engine",
                    "high",
                )
            )
        elif high_commitment_cta and not low_friction_cta and business_context["high_consideration"]:
            layers["Conversion"] -= 5
            findings.append(
                Finding(
                    "The site asks for commitment before giving a small win",
                    "Conversion",
                    "Primary CTAs and first-step offer path",
                    f"Detected CTA labels: {', '.join(unique_ctas[:10])}. No low-friction asset such as a quiz, guide, calculator, scorecard, audit, or template was detected.",
                    "Interested visitors are pushed toward a call or project inquiry before they have received a low-risk reason to continue.",
                    "The site jumps from explanation to consultation instead of using a small-favor entry point.",
                    business_context["small_favor_fix"],
                    "conversion-engine",
                    "high",
                )
            )
        elif len(unique_ctas) >= 7:
            layers["Conversion"] -= 4
            findings.append(
                Finding(
                    "Too many action labels compete with the main next step",
                    "Conversion",
                    "Audited links and buttons",
                    f"Detected CTA labels: {', '.join(unique_ctas[:10])}.",
                    "The page can explain the service and still leave the visitor unsure which click is the real starting point.",
                    "Navigation, education, and conversion CTAs are carrying the same visual weight.",
                    "Choose one primary CTA, one secondary reassurance CTA, and demote the rest to supporting navigation.",
                    "conversion-engine",
                    "medium",
                )
            )

        root_layer = min(layers, key=layers.get)
        unresolved_upstream = root_layer in {"Business / Positioning", "Offer"} and layers[root_layer] < 14
        return {
            "score": sum(max(0, value) for value in layers.values()),
            "layers": [{"name": name, "score": max(0, score), "max": 20} for name, score in layers.items()],
            "root_layer": root_layer,
            "rewrite_eligible": not unresolved_upstream,
            "findings": findings,
        }

    @staticmethod
    def infer_business_context(pages: list[PageEvidence]) -> dict[str, Any]:
        all_text = " ".join(
            f"{page.title} {page.description} {' '.join(page.h1)} {' '.join(page.h2)} {page.text[:3000]}"
            for page in pages
        ).lower()
        segment_scores = {
            name: sum(all_text.count(term) for term in terms)
            for name, terms in BUSINESS_SEGMENTS.items()
        }
        segment = max(segment_scores, key=segment_scores.get) if any(segment_scores.values()) else "professional-services"
        high_consideration = bool(
            PRICE_RE.search(all_text)
            or any(term in all_text for term in ("project", "custom", "package", "consultation", "renovation", "strategy"))
        )
        context = {
            "segment": segment,
            "high_consideration": high_consideration,
            "small_favor_fix": "Add one low-friction entry asset before the main inquiry, such as a scorecard, guided audit, template, calculator, or fit quiz that gives the visitor a small win.",
            "chooser_fix": "Add a chooser mechanism such as a scorecard, quiz, or guided decision tree so visitors can identify the right starting offer without guessing.",
            "proof_loop_fix": "Install a proof loop inside the service motion: document audits, before/after examples, client walkthroughs, or structured case studies so proof is created continuously, not added later.",
        }
        if segment == "home-services":
            context.update(
                {
                    "small_favor_fix": "Add an estimate-first or project-fit asset before the main inquiry, such as a budget calculator, scope guide, or renovation fit quiz that helps the visitor understand the right next step.",
                    "chooser_fix": "Add a guided estimator or fit quiz so visitors can separate quick projects, custom work, and premium engagements before they contact you.",
                    "proof_loop_fix": "Build a proof loop with before/after projects, process walk-throughs, and customer-result stories captured from every completed job.",
                }
            )
        elif segment == "beauty-wellness":
            context.update(
                {
                    "small_favor_fix": "Add a style-fit, treatment-fit, or readiness asset before the booking CTA so the visitor receives a useful next step without committing to a full consultation first.",
                    "chooser_fix": "Use a short fit quiz or guided service selector so visitors know which treatment path or package matches their situation.",
                    "proof_loop_fix": "Use a proof loop built from before/after galleries, client stories, and documented treatment journeys gathered from real sessions.",
                }
            )
        return context

    def design_audit(self, pages: list[PageEvidence], css_text: str) -> dict[str, Any]:
        homepage = pages[0]
        all_text = " ".join(page.text for page in pages).lower()
        findings: list[DesignFinding] = []
        score = 100
        design_source = "visual-creator-html (5 design basics + Modern Luxe Rules) and hallmark (anti-AI-slop)"

        brand = self.extract_brand(pages, css_text)
        font_count = 0
        if brand.get("display_font"):
            font_count += 1
        if brand.get("body_font"):
            font_count += 1
        detected_fonts = brand.get("fonts", [])
        if len(detected_fonts) > 2:
            score -= 15
            findings.append(
                DesignFinding(
                    "More than 2 fonts detected",
                    "Typography",
                    "CSS font-family declarations",
                    f"Detected font names: {', '.join(detected_fonts[:6])}.",
                    "Typographic hierarchy loses clarity when too many faces compete.",
                    "Keep 1 display font and 1 body font. Assign weights and sizes for hierarchy instead of adding new faces.",
                    "high",
                )
            )
        elif len(detected_fonts) <= 1:
            score -= 5
            findings.append(
                DesignFinding(
                    "Only one font detected or none",
                    "Typography",
                    "CSS font-family declarations",
                    f"Detected font names: {', '.join(detected_fonts[:6]) or 'none'}.",
                    "The site may lack typographic contrast between headings and body text.",
                    "Add a second font family (serif + sans-serif pairing) or use distinct weights and sizes for visual hierarchy.",
                    "medium",
                )
            )

        css_lower = css_text.lower()
        color_count = 0
        for line in css_lower.splitlines():
            stripped = line.strip()
            if stripped.startswith("--") and "color" in stripped and ":" in stripped:
                color_count += 1
        if color_count > 8:
            score -= 10
            findings.append(
                DesignFinding(
                    "Excessive CSS color variables suggest a broad palette",
                    "Color",
                    "CSS custom properties",
                    f"Detected {color_count} color-related CSS variables.",
                    "Too many colors reduce brand recognition and visual coherence.",
                    "Limit the palette to 3 core colors + 2 neutral shades. Consolidate similar values.",
                    "high",
                )
            )

        premium_count = sum(all_text.count(term) for term in PREMIUM_TERMS)
        if premium_count >= 5:
            score -= 8
            findings.append(
                DesignFinding(
                    "Premium language overused without visual backing",
                    "Brand coherence",
                    "Audited page copy",
                    f"Detected {premium_count} uses of premium descriptors such as 'luxury', 'premium', 'bespoke'.",
                    "Calling something premium without design proof creates a trust gap.",
                    "Match premium language with actual visual quality: whitespace, restrained palette, refined typography. Remove unsupported claims.",
                    "medium",
                )
            )

        amateur_count = sum(all_text.count(term) for term in AMATEUR_PATTERNS)
        if amateur_count:
            score -= 10
            findings.append(
                DesignFinding(
                    "Generic amateur phrasing detected",
                    "Copy quality",
                    "Audited page copy",
                    f"Detected amateur patterns: {', '.join(term for term in AMATEUR_PATTERNS if term in all_text)}.",
                    "Phrases like 'welcome to' and 'learn more' signal a template-built site.",
                    "Replace generic phrases with specific, decision-oriented language.",
                    "high",
                )
            )

        hero = homepage.image_assets[:1]
        if hero and not hero[0].get("src", "").endswith((".jpg", ".jpeg", ".png", ".webp")):
            score -= 5
            findings.append(
                DesignFinding(
                    "Hero image may be missing or low-quality",
                    "Visual hierarchy",
                    "Homepage primary image",
                    f"Primary image source: {hero[0].get('src', 'unknown')}.",
                    "The first visual the visitor sees sets the brand tone.",
                    "Use a high-resolution hero image in JPG, PNG, or WebP format that communicates the transformation.",
                    "medium",
                )
            )

        if homepage.images_without_alt and homepage.images_without_alt / max(homepage.images, 1) > 0.5:
            score -= 8
            findings.append(
                DesignFinding(
                    "More than half of images lack alt text",
                    "Accessibility",
                    "Audited images",
                    f"{homepage.images_without_alt} of {homepage.images} images have no alt attribute.",
                    "The site fails accessibility basics and signals inattention to detail.",
                    "Add descriptive alt text to every meaningful image.",
                    "high",
                )
            )

        return {
            "score": max(0, score),
            "findings": [finding.as_dict() for finding in findings],
            "design_source": design_source,
            "note": "This design score is a heuristic scan of public HTML and CSS. A rendered visual review by hallmark or a human designer is required for a complete assessment.",
        }

    def opportunity_scan(
        self,
        pages: list[PageEvidence],
        conversion: dict[str, Any],
    ) -> list[dict[str, str]]:
        business_context = self.infer_business_context(pages)
        all_text = " ".join(page.text for page in pages).lower()
        ctas = list(
            dict.fromkeys(
                clean_text(text).lower()
                for page in pages
                for text in page.buttons + [link["text"] for link in page.links]
                if clean_text(text)
            )
        )
        proof_count = sum(all_text.count(term) for term in STRONG_PROOF_TERMS)
        has_low_friction_asset = any(term in all_text for term in LOW_FRICTION_TERMS) or any(
            any(term in cta for term in LOW_FRICTION_TERMS) for cta in ctas
        )
        prices = list(dict.fromkeys(PRICE_RE.findall(" ".join(page.text for page in pages))))
        opportunities: list[dict[str, str]] = []

        if not has_low_friction_asset:
            if business_context["segment"] == "home-services":
                opportunities.append(
                    {
                        "title": "Add an estimate-first entry offer",
                        "why": "The business sells a high-consideration service, but the site jumps toward contact before helping the buyer understand scope, fit, or budget.",
                        "format": "Budget calculator, project-fit quiz, or estimate roadmap",
                        "next_step": "Give the visitor a low-risk first answer, then route them to the right consultation or project path.",
                    }
                )
            elif business_context["segment"] == "beauty-wellness":
                opportunities.append(
                    {
                        "title": "Add a treatment-fit or style-fit diagnostic",
                        "why": "Visitors often want help choosing the right treatment or result path before they book.",
                        "format": "Fit quiz, readiness guide, or style selector",
                        "next_step": "Use the result to recommend the right booking path and collect better-qualified leads.",
                    }
                )
            else:
                opportunities.append(
                    {
                        "title": "Add a small-favor lead magnet before the main inquiry",
                        "why": "The site asks for a call or project contact before delivering a concrete small win.",
                        "format": "Homepage clarity audit, website rewrite readiness scorecard, brand-fit review, or guided diagnostic quiz",
                        "next_step": "Show the visitor where the site loses clarity or trust, then offer the rewrite, strategy call, or implementation plan that fixes it.",
                    }
                )
        if proof_count < 2:
            opportunities.append(
                {
                    "title": "Turn delivery into a repeatable proof loop",
                    "why": "High-trust services convert faster when every job creates reusable proof instead of relying on generic claims.",
                    "format": "Case-study engine, annotated before/after mockups, audit walk-throughs, or client-story interviews",
                    "next_step": "If case studies are still thin, start with teardown audits, annotated sample work, and process walk-throughs until live client proof compounds.",
                }
            )
        if len(prices) >= 3:
            opportunities.append(
                {
                    "title": "Use a chooser asset for the offer ladder",
                    "why": "Multiple offers create hesitation when the visitor has to self-diagnose the right starting point.",
                    "format": "Decision tree, offer-fit quiz, audit scorecard, or guided calculator",
                    "next_step": "Use the asset to tell visitors which offer fits them, why that path is the right one, and what to do next.",
                }
            )
        if business_context["segment"] in {"home-services", "beauty-wellness"}:
            opportunities.append(
                {
                    "title": "Use reviews and before/after proof as the main growth lever",
                    "why": "For local and visual services, trust rises when buyers can see real outcomes and hear from similar customers.",
                    "format": "Review request workflow, before/after gallery, or customer story reel",
                    "next_step": "Pair every service outcome with visible proof so the next buyer does less guesswork.",
                }
            )
        else:
            opportunities.append(
                {
                    "title": "Package the best insight as a reusable entry product",
                    "why": "Service businesses create authority faster when the first proof is productized into a simple diagnostic or roadmap.",
                    "format": "Website audit, homepage scorecard, template toolkit, or mini-workshop",
                    "next_step": "Make the first asset useful on its own, then bridge it directly into the paid rewrite, roadmap, or implementation service.",
                }
            )
        return opportunities[:4]

    @staticmethod
    def client_review(
        pages: list[PageEvidence],
        conversion: dict[str, Any],
        visibility: dict[str, Any],
        strengths: list[str],
    ) -> dict[str, Any]:
        homepage = pages[0]
        business_context = AuditEngine.infer_business_context(pages)
        all_text = " ".join(page.text for page in pages)
        all_text_lower = all_text.lower()
        prices = list(dict.fromkeys(PRICE_RE.findall(all_text)))
        ctas = list(
            dict.fromkeys(
                clean_text(text)
                for page in pages
                for text in page.buttons + [link["text"] for link in page.links]
                if clean_text(text)
            )
        )
        proof_count = sum(all_text_lower.count(term) for term in STRONG_PROOF_TERMS)
        abstract_count = sum(all_text_lower.count(term) for term in ABSTRACT_TERMS)
        largest_form = max((page.form_controls for page in pages), default=0)
        main_quote = homepage.h1[0] if homepage.h1 else homepage.description or homepage.title
        has_low_friction_asset = any(term in all_text_lower for term in LOW_FRICTION_TERMS) or any(
            any(term in clean_text(cta).lower() for term in LOW_FRICTION_TERMS) for cta in ctas
        )

        visitor_view = []
        if main_quote:
            visitor_view.append(
                {
                    "title": "The opening names a real problem",
                    "text": f'The first message is: "{main_quote}" This helps the right visitor recognize that the site is speaking to them.',
                    "tone": "positive",
                }
            )
        if len(prices) > 6:
            visitor_view.append(
                {
                    "title": "The next choice becomes harder",
                    "text": f"The audited pages show {len(prices)} prices. A visitor may understand the services but still be unsure which one is the right starting point.",
                    "tone": "risk",
                }
            )
        elif prices:
            visitor_view.append(
                {
                    "title": "Prices reduce uncertainty",
                    "text": "Visible starting prices help visitors decide whether the service is within reach before they inquire.",
                    "tone": "positive",
                }
            )
        if proof_count < 2:
            visitor_view.append(
                {
                    "title": "The promise is easier to understand than to verify",
                    "text": "The site explains the service, but it gives visitors little proof of the result. That can slow down a high-value buying decision.",
                    "tone": "risk",
                }
            )
        if business_context["high_consideration"] and not has_low_friction_asset:
            visitor_view.append(
                {
                    "title": "The site asks for trust before giving a small win",
                    "text": "A visitor is pushed toward contact or consultation before receiving a low-risk tool, audit, estimate, or fit check that proves the site understands their situation.",
                    "tone": "risk",
                }
            )
        if largest_form > 10:
            visitor_view.append(
                {
                    "title": "The inquiry asks for too much too soon",
                    "text": f"The longest form has {largest_form} fields. A visitor must complete part of the discovery process before knowing whether the fit is right.",
                    "tone": "risk",
                }
            )
        elif largest_form:
            visitor_view.append(
                {
                    "title": "There is a direct way to inquire",
                    "text": "Visitors do not have to search for a contact path.",
                    "tone": "positive",
                }
            )

        copy_works = []
        if any(term in all_text_lower for term in ("feeling stuck", "not sure where to start", "outgrown")):
            copy_works.append("The copy uses language that matches how a frustrated business owner may describe the problem.")
        if main_quote:
            copy_works.append("The headline starts with the visitor's situation instead of a list of services.")
        if any("faq" in page.url.lower() for page in pages):
            copy_works.append("The FAQ gives buyers a place to resolve practical questions.")
        if prices:
            copy_works.append("Visible pricing cues reduce uncertainty because buyers can estimate fit before they inquire.")
        if not copy_works:
            copy_works.append("The site gives visitors a clear description of the business and its services.")

        copy_risks = []
        conversion_findings = [
            finding
            for finding in conversion["findings"]
            if finding.layer in {"Messaging", "Offer", "Trust", "Conversion"}
        ]
        if conversion_findings:
            copy_risks.append(conversion_findings[0].impact)
        if abstract_count >= 18:
            copy_risks.append(
                "Words such as clear, refined, elevated, and intentional appear often. They sound polished, but they do not show what changes for the client."
            )
        if len(ctas) > 6:
            copy_risks.append(
                "The site uses several action labels. One main next step would make the buying path easier to follow."
            )
        if proof_count < 2:
            copy_risks.append(
                "The story stops before the result. Add real before-and-after examples, client decisions, and outcomes."
            )
        if business_context["high_consideration"] and not has_low_friction_asset:
            copy_risks.append(
                "The site goes from explanation to inquiry too quickly. A scorecard, audit, guide, estimate, or quiz would make the next step easier to say yes to."
            )
        if not copy_risks:
            copy_risks.append("Keep the strongest message, then support it with more specific proof and examples.")

        primary_next_step = "Choose one primary CTA that names the lowest-friction next step and demote the rest."
        if business_context["segment"] == "professional-services":
            if business_context["high_consideration"] and not has_low_friction_asset:
                primary_next_step = (
                    "Make the first CTA a Website Clarity Audit, homepage scorecard, or brand-fit review, then route qualified buyers into the full inquiry."
                )
            elif len(ctas) > 6:
                primary_next_step = (
                    "Reduce the page to one primary CTA. For this kind of service, the clearest first move is a focused audit or review, not six equal buttons."
                )
        elif business_context["segment"] == "home-services":
            primary_next_step = (
                "Lead with one estimate-first CTA, such as a budget guide or project-fit quiz, then move qualified visitors into the consultation."
            )
        elif business_context["segment"] == "beauty-wellness":
            primary_next_step = (
                "Lead with one fit CTA, such as a treatment-fit or style-fit quiz, then move the right visitor into the booking path."
            )

        layer_help = {
            "Business / Positioning": "Make it obvious who the site is for and what changes after the work.",
            "Messaging": "Use one clear promise, specific language, and one consistent process.",
            "Offer": "Give visitors a small number of clear ways to start and explain who each option is for.",
            "Trust": "Place real proof beside the claims that require the most belief.",
            "Conversion": "Make the next step easy, specific, and low effort.",
        }
        findings_by_layer: dict[str, list[Finding]] = {name: [] for name in layer_help}
        for finding in conversion["findings"]:
            findings_by_layer.setdefault(finding.layer, []).append(finding)
        score_path = []
        for layer in conversion["layers"]:
            relevant = findings_by_layer.get(layer["name"], [])
            score_path.append(
                {
                    "name": layer["name"],
                    "score": layer["score"],
                    "max": layer["max"],
                    "plain_name": {
                        "Business / Positioning": "Who it is for",
                        "Messaging": "What the site says",
                        "Offer": "What people can buy",
                        "Trust": "Why people should believe it",
                        "Conversion": "How easy it is to act",
                    }[layer["name"]],
                    "to_10": relevant[0].fix if relevant else layer_help[layer["name"]],
                }
            )

        visibility_names = {
            "Technical discovery": ("Can search engines find it?", "Keep crawl files, preferred URLs, and public routes complete."),
            "On-page clarity": ("Can search engines understand each page?", "Give every page one clear title, description, and main heading."),
            "Content quality and authority": ("Does the site show real expertise?", "Add specific examples, results, sources, and named experience."),
            "GEO readiness": ("Can AI understand the business?", "Keep the business name, services, language, domain, and structured facts consistent."),
            "AEO readiness": ("Does the site answer real questions clearly?", "Use direct questions, short answers, and supporting proof."),
            "Source-level accessibility": ("Is the page structure clear?", "Use clear headings, image descriptions, and form labels."),
            "Security and response basics": ("Does the site send basic trust signals?", "Add the missing browser security rules and keep HTTPS active."),
        }
        visibility_path = [
            {
                "name": visibility_names[item["name"]][0],
                "score": item["score"],
                "max": item["max"],
                "to_10": visibility_names[item["name"]][1],
            }
            for item in visibility["categories"]
        ]

        root_plain = {
            "Business / Positioning": "The site first needs a clearer answer to who it is for and what changes.",
            "Messaging": "The service may be sound, but the message is making it harder to understand.",
            "Offer": "The main problem is not the design. It is choosing what to buy and where to start.",
            "Trust": "The promise needs more proof before visitors can feel confident.",
            "Conversion": "The offer is understandable, but the path to action has too much friction.",
        }[conversion["root_layer"]]

        return {
            "headline": root_plain,
            "strengths": strengths,
            "visitor_view": visitor_view[:5],
            "copy": {
                "quote": main_quote,
                "works": copy_works[:3],
                "risks": copy_risks[:3],
            },
            "design": {
                "works": "The public HTML and CSS suggest that the site has a defined visual direction. An automated heuristic scan was run against typography, color palette, and accessibility basics.",
                "risk": "This automated scan does not replace a rendered desktop and mobile review. Readability, spacing, overlap, hierarchy, trust cues, and interaction still need a visual pass using the hallmark skill or a human designer.",
            },
            "main_next_step": primary_next_step,
            "conversion_path": score_path,
            "visibility_path": visibility_path,
            "visibility_explanation": (
                "A site can answer questions well and still confuse AI systems about the business. "
                "Clear FAQs help answer engines. Consistent business facts, language URLs, schema, and domain signals help AI understand the entity."
            ),
        }

    def visibility_audit(
        self,
        pages: list[PageEvidence],
        robots: dict[str, Any],
        sitemap: dict[str, Any],
        script_text: str,
    ) -> dict[str, Any]:
        homepage = pages[0]
        findings: list[Finding] = []
        categories = {
            "Technical discovery": 10,
            "On-page clarity": 10,
            "Content quality and authority": 10,
            "GEO readiness": 10,
            "AEO readiness": 10,
            "Source-level accessibility": 10,
            "Security and response basics": 10,
        }

        if robots.get("status") != 200:
            categories["Technical discovery"] -= 4
            findings.append(
                Finding(
                    "robots.txt is unavailable",
                    "Technical discovery",
                    "/robots.txt",
                    f"HTTP status: {robots.get('status') or 'request failed'}.",
                    "Search and AI crawlers receive no explicit crawl policy or sitemap location.",
                    "The production deployment does not serve a valid robots file.",
                    "Publish robots.txt at the domain root and include the canonical sitemap URL.",
                    "visibility-audit",
                    "critical",
                    "visibility",
                )
            )
        if sitemap.get("status") != 200:
            categories["Technical discovery"] -= 4
            findings.append(
                Finding(
                    "sitemap.xml is unavailable",
                    "Technical discovery",
                    "/sitemap.xml",
                    f"HTTP status: {sitemap.get('status') or 'request failed'}.",
                    "Search systems lose a direct list of canonical public pages.",
                    "The production deployment does not generate or serve a sitemap.",
                    "Publish a valid XML sitemap and reference it from robots.txt.",
                    "visibility-audit",
                    "critical",
                    "visibility",
                )
            )
        pages_without_canonical = [page.url for page in pages if not page.canonical]
        if pages_without_canonical:
            categories["Technical discovery"] -= 2
            categories["GEO readiness"] -= 1
            findings.append(
                Finding(
                    "Preferred URL signals are missing",
                    "Technical discovery",
                    ", ".join(pages_without_canonical[:5]),
                    f"{len(pages_without_canonical)} of {len(pages)} audited pages have no canonical tag.",
                    "Bots receive no explicit preferred URL for duplicate or translated states.",
                    "Canonical metadata is absent from the shared templates.",
                    "Add one absolute self-referencing canonical to every indexable page.",
                    "visibility-audit",
                    "high",
                    "visibility",
                )
            )

        if not homepage.title:
            categories["On-page clarity"] -= 4
        if not homepage.description:
            categories["On-page clarity"] -= 3
        if not homepage.h1:
            categories["On-page clarity"] -= 3
        if not homepage.title or not homepage.description or not homepage.h1:
            findings.append(
                Finding(
                    "Core homepage metadata is incomplete",
                    "On-page clarity",
                    homepage.url,
                    f"Title: {bool(homepage.title)}; description: {bool(homepage.description)}; H1: {bool(homepage.h1)}.",
                    "Search snippets and page understanding lose essential context.",
                    "The page template does not consistently expose core metadata.",
                    "Provide a unique title, description, and one H1 aligned to the primary search intent.",
                    "visibility-audit",
                    "high",
                    "visibility",
                )
            )

        all_text = " ".join(page.text for page in pages).lower()
        proof_count = sum(all_text.count(term) for term in STRONG_PROOF_TERMS)
        if proof_count < 2:
            categories["Content quality and authority"] -= 5
        if len(all_text.split()) < 500:
            categories["Content quality and authority"] -= 3
        if proof_count < 2 or len(all_text.split()) < 500:
            findings.append(
                Finding(
                    "Authority signals are thin in the audited content",
                    "Content quality and authority",
                    "Audited public pages",
                    f"Approximate audited word count: {len(all_text.split())}; proof references: {proof_count}.",
                    "Search and AI systems have limited evidence for expertise and outcomes.",
                    "Service claims are not supported by enough verifiable examples or source-backed detail.",
                    "Add case studies, named expertise, specific outcomes, and source-backed answers where claims are made.",
                    "visibility-audit",
                    "medium",
                    "visibility",
                )
            )

        schema_items = [item for page in pages for item in page.json_ld if isinstance(item, dict)]
        if not schema_items:
            categories["GEO readiness"] -= 5
            findings.append(
                Finding(
                    "No structured entity data was detected",
                    "GEO readiness",
                    "Audited raw HTML",
                    "No valid JSON-LD object was parsed.",
                    "Search and AI systems receive fewer explicit entity and service signals.",
                    "Structured data is missing or invalid.",
                    "Add relevant Organization, LocalBusiness, or ProfessionalService schema using verified facts.",
                    "visibility-audit",
                    "high",
                    "visibility",
                )
            )
        else:
            schema_urls = [
                item.get("url")
                for item in schema_items
                if isinstance(item.get("url"), str)
            ]
            domain = urlsplit(homepage.url).netloc.lower()
            mismatches = [value for value in schema_urls if urlsplit(value).netloc.lower() != domain]
            if mismatches:
                categories["GEO readiness"] -= 6
                findings.append(
                    Finding(
                        "Structured data identifies a different domain",
                        "GEO readiness",
                        "JSON-LD",
                        f"Schema URL values outside {domain}: {', '.join(mismatches[:3])}.",
                        "Search and AI systems receive conflicting entity identity signals.",
                        "Structured data and production-domain configuration do not share one source of truth.",
                        "Use the production canonical domain in schema and align its service description with visible copy.",
                        "visibility-audit",
                        "critical",
                        "visibility",
                    )
                )

        faq_signal = any("faq" in page.url.lower() or "frequently asked" in page.text.lower() for page in pages)
        question_headings = sum(
            1 for page in pages for heading in page.h2 if heading.rstrip().endswith("?")
        )
        if not faq_signal:
            categories["AEO readiness"] -= 4
        if question_headings == 0:
            categories["AEO readiness"] -= 2
        if not faq_signal or question_headings == 0:
            findings.append(
                Finding(
                    "Direct answer structure is limited",
                    "AEO readiness",
                    "Audited headings and FAQ routes",
                    f"FAQ route/content detected: {faq_signal}; question headings detected: {question_headings}.",
                    "Answer engines have fewer concise passages to retrieve and cite.",
                    "Important buyer questions are not consistently expressed as direct questions and answers.",
                    "Add specific buyer questions with short direct answers followed by evidence and detail.",
                    "visibility-audit",
                    "medium",
                    "visibility",
                )
            )

        pages_with_alt_gaps = [page for page in pages if page.images_without_alt]
        if pages_with_alt_gaps:
            categories["Source-level accessibility"] -= 4
        form_label_gaps = [
            page for page in pages if page.form_controls and page.labels < page.form_controls
        ]
        if form_label_gaps:
            categories["Source-level accessibility"] -= 3
        multi_h1 = [page for page in pages if len(page.h1) != 1]
        if multi_h1:
            categories["Source-level accessibility"] -= 2
        if pages_with_alt_gaps or form_label_gaps or multi_h1:
            findings.append(
                Finding(
                    "Source-level accessibility semantics need correction",
                    "Source-level accessibility",
                    "Audited images, forms, and headings",
                    f"Pages with missing image alt: {len(pages_with_alt_gaps)}; form label gaps: {len(form_label_gaps)}; non-single-H1 pages: {len(multi_h1)}.",
                    "Assistive technology can receive incomplete names or ambiguous hierarchy.",
                    "Shared content components do not enforce semantic requirements.",
                    "Require alt attributes, explicit control labels, and one H1 per indexable page.",
                    "visibility-audit",
                    "high",
                    "visibility",
                )
            )

        headers = homepage.headers
        if urlsplit(homepage.url).scheme != "https":
            categories["Security and response basics"] -= 6
        if "strict-transport-security" not in headers:
            categories["Security and response basics"] -= 2
        missing_headers = [
            header
            for header in (
                "content-security-policy",
                "x-content-type-options",
                "referrer-policy",
                "permissions-policy",
            )
            if header not in headers
        ]
        categories["Security and response basics"] -= min(3, len(missing_headers))
        if missing_headers:
            findings.append(
                Finding(
                    "Common browser security headers are absent",
                    "Security and response basics",
                    homepage.url,
                    f"Missing from inspected response: {', '.join(missing_headers)}.",
                    "The browser receives fewer explicit restrictions for content, referrers, and permissions.",
                    "The hosting response policy is minimal.",
                    "Add appropriate security headers at the hosting layer and test the production response.",
                    "visibility-audit",
                    "medium",
                    "visibility",
                )
            )

        bilingual_signal = bool(
            re.search(r"data-i18n|lang-toggle|translations", homepage.raw_html, re.I)
            or re.search(r"document\.documentElement\.lang|bc_lang|savedLang", script_text, re.I)
        )
        if bilingual_signal and not any(page.hreflangs for page in pages):
            categories["GEO readiness"] -= 3
            default_match = re.search(r"localStorage\.getItem\([^)]*\)\s*\|\|\s*['\"]([a-z-]+)['\"]", script_text)
            default_language = default_match.group(1) if default_match else "client-side state"
            findings.append(
                Finding(
                    "The bilingual experience lacks stable language URLs",
                    "GEO readiness",
                    "HTML language attributes, language script, canonical and hreflang tags",
                    f"Client-side language behavior detected; default signal: {default_language}; hreflang links: 0.",
                    "Visitors and search systems can receive different languages without stable indexable alternatives.",
                    "Language selection is stored in browser state instead of URL and server metadata.",
                    "Create stable language routes with localized metadata, reciprocal hreflang, x-default, and self-canonical tags.",
                    "visibility-audit",
                    "critical",
                    "visibility",
                )
            )

        legal_paths = {
            urlsplit(link["href"]).path
            for page in pages
            for link in page.links
            if urlsplit(link["href"]).path in {"/privacy", "/terms", "/privacy-policy", "/terms-of-service"}
        }
        for path in sorted(legal_paths):
            status = self.fetch_status(urljoin(homepage.url, path))
            if status.get("status") != 200:
                categories["Technical discovery"] = max(0, categories["Technical discovery"] - 1)
                findings.append(
                    Finding(
                        "A legal footer route is broken",
                        "Technical discovery",
                        path,
                        f"HTTP status: {status.get('status') or 'request failed'}.",
                        "Visitors cannot inspect the policy before submitting information.",
                        "Shared footer navigation points to an undeployed route.",
                        "Publish the policy or remove the link until a valid page exists.",
                        "visibility-audit",
                        "high",
                        "visibility",
                    )
                )

        for key in categories:
            categories[key] = max(0, categories[key])
        measured_score = sum(categories.values())
        measured_max = len(categories) * 10
        normalized = round(measured_score / measured_max * 100)
        return {
            "measured_score": measured_score,
            "measured_max": measured_max,
            "normalized_score": normalized,
            "categories": [
                {"name": name, "score": score, "max": 10}
                for name, score in categories.items()
            ],
            "unmeasured": [
                "Rendered JavaScript state, Core Web Vitals, and mobile runtime performance",
                "Live AI-platform citations and recommendation tests",
                "Competitive search and answer-engine gap",
                "Backlinks, rankings, traffic, and conversions",
            ],
            "findings": findings,
        }

    @staticmethod
    def what_to_keep(
        pages: list[PageEvidence],
        robots: dict[str, Any],
        sitemap: dict[str, Any],
    ) -> list[str]:
        homepage = pages[0]
        items = []
        if homepage.title and homepage.description:
            items.append("The homepage already exposes a title and meta description.")
        if homepage.h1:
            items.append(f"Preserve the primary message direction: {homepage.h1[0]}")
        if all(page.images_without_alt == 0 for page in pages if page.images):
            items.append("Audited image elements include alt attributes.")
        if any(page.form_controls for page in pages):
            items.append("The site already provides a direct inquiry path.")
        if any(page.json_ld for page in pages):
            items.append("Structured data exists and can be corrected rather than introduced from zero.")
        if homepage.headers.get("strict-transport-security"):
            items.append("HTTPS transport security is active.")
        if robots.get("status") == 200 and sitemap.get("status") == 200:
            items.append("Core crawl-support files are available.")
        return items[:6] or ["Preserve any verified offer, proof, and contact assets during revision."]

    @staticmethod
    def seven_day_plan(priorities: list[Finding]) -> list[str]:
        defaults = [
            "Confirm the primary buyer, outcome, and public offer ladder.",
            "Repair critical crawl, canonical, schema, and broken-route issues.",
            "Align the homepage promise, service path, and metadata.",
            "Add verifiable proof beside the strongest claims.",
            "Reduce inquiry friction and clarify the next action.",
            "Complete mobile, accessibility, and Core Web Vitals measurement.",
            "Rerun the audit and compare measured evidence.",
        ]
        mapped = []
        for finding in priorities:
            if finding.fix not in mapped:
                mapped.append(finding.fix)
        return (mapped + defaults)[:7]

    @staticmethod
    def executive_summary(
        brand_name: str,
        conversion: dict[str, Any],
        visibility: dict[str, Any],
        mode: str,
    ) -> str:
        if mode == "conversion":
            return (
                f"{brand_name} shows {conversion['score']}/100 current conversion readiness in this evidence pass. "
                f"The first issue to solve is {conversion['root_layer']}. Fix that before rewriting the whole site."
            )
        if mode == "visibility":
            return (
                f"{brand_name} shows {visibility['normalized_score']}/100 across the visibility checks this tool could run. "
                "Checks that require analytics, live search results, or a rendered browser are listed separately."
            )
        return (
            f"{brand_name} shows {conversion['score']}/100 current conversion readiness and "
            f"{visibility['normalized_score']}/100 measured visibility readiness in this evidence pass. "
            f"The first business issue to solve is {conversion['root_layer']}."
        )

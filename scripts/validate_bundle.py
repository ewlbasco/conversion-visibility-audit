#!/usr/bin/env python3
"""Validate the portable conversion and visibility skill bundle."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
SKILLS = ("website-audit", "conversion-engine", "visibility-audit", "qa-audit", "creative-director", "geo-implementation", "positioning-clarity-check")
REQUIRED_EVAL_FILES = (
    "routing-cases.json",
    "conversion-layer-cases.json",
    "improvement-loop.md",
    "post-run-feedback-template.md",
)
FORBIDDEN_TEXT = (
    "/Users/",
    "EDGEWISE_WORKSPACE_MASTER",
    "license: Proprietary",
)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")

    _, frontmatter, _ = text.split("---", 2)
    data: dict[str, str] = {}
    for line in frontmatter.strip().splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{path}: invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    failures: list[str] = []

    for filename in REQUIRED_EVAL_FILES:
        path = ROOT / "evals" / filename
        if not path.is_file():
            failures.append(f"Missing eval asset: evals/{filename}")

    for skill in SKILLS:
        skill_dir = ROOT / "skills" / skill
        skill_file = skill_dir / "SKILL.md"
        agent_file = skill_dir / "agents" / "openai.yaml"

        if not skill_file.is_file():
            failures.append(f"Missing {skill_file.relative_to(ROOT)}")
            continue
        if not agent_file.is_file():
            failures.append(f"Missing {agent_file.relative_to(ROOT)}")

        try:
            metadata = parse_frontmatter(skill_file)
        except ValueError as error:
            failures.append(str(error))
            continue

        if set(metadata) != {"name", "description"}:
            failures.append(
                f"{skill_file.relative_to(ROOT)} frontmatter must contain only "
                "'name' and 'description'"
            )
        if metadata.get("name") != skill:
            failures.append(
                f"{skill_file.relative_to(ROOT)} name must be '{skill}'"
            )
        if not metadata.get("description"):
            failures.append(
                f"{skill_file.relative_to(ROOT)} needs a description"
            )

        text = skill_file.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_TEXT:
            if forbidden in text:
                failures.append(
                    f"{skill_file.relative_to(ROOT)} contains forbidden text: "
                    f"{forbidden}"
                )

    router = (ROOT / "skills" / "website-audit" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for dependency in ("conversion-engine", "visibility-audit", "geo-implementation", "positioning-clarity-check", "hallmark"):
        if dependency not in router:
            failures.append(f"website-audit does not name {dependency}")

    cases_path = ROOT / "evals" / "routing-cases.json"
    try:
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f"Invalid routing fixtures: {error}")
        cases = []

    routes = {case.get("expected_route") for case in cases}
    expected_routes = {"conversion-engine", "visibility-audit", "combined"}
    if not expected_routes.issubset(routes):
        failures.append("Routing fixtures do not cover all expected routes")

    if len(cases) < 10:
        failures.append("Routing fixtures need at least 10 cases")

    for index, case in enumerate(cases, start=1):
        prompt = case.get("prompt", "")
        if not isinstance(prompt, str) or not prompt.strip():
            failures.append(f"Routing case {index} has no prompt")
        route = case.get("expected_route")
        if route not in expected_routes:
            failures.append(f"Routing case {index} has invalid route: {route}")

    layer_cases_path = ROOT / "evals" / "conversion-layer-cases.json"
    try:
        layer_cases = json.loads(layer_cases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f"Invalid conversion layer fixtures: {error}")
        layer_cases = []

    expected_layers = {
        "business-positioning",
        "messaging",
        "offer",
        "trust",
        "conversion",
    }
    covered_layers = {case.get("expected_layer") for case in layer_cases}
    if not expected_layers.issubset(covered_layers):
        failures.append("Conversion fixtures do not cover all five layers")

    if len(layer_cases) < 10:
        failures.append("Conversion layer fixtures need at least 10 cases")

    conversion_skill = (
        ROOT / "skills" / "conversion-engine" / "SKILL.md"
    ).read_text(encoding="utf-8")
    required_conversion_phrases = (
        "Are we trying to solve a problem that belongs to another layer?",
        "Business / Positioning",
        "Paid",
        "self-serve website builder",
    )
    for phrase in required_conversion_phrases:
        if phrase not in conversion_skill:
            failures.append(f"conversion-engine is missing required phrase: {phrase}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if not re.search(r"Freshness check:\s*2026-07-(0[1-9]|[12][0-9]|3[01])", readme):
        failures.append("README is missing the current freshness check")

    hook = ROOT / ".githooks" / "pre-push"
    if not hook.is_file():
        failures.append("Missing required pre-push gate: .githooks/pre-push")
    else:
        hook_text = hook.read_text(encoding="utf-8")
        required_hook_commands = (
            "python3 scripts/validate_bundle.py",
            "python3 -m unittest discover -s tool/tests",
        )
        for command in required_hook_commands:
            if command not in hook_text:
                failures.append(f"pre-push hook is missing required command: {command}")
        if not hook.stat().st_mode & 0o111:
            failures.append("pre-push hook exists but is not executable")

    active_surface_files = [
        ROOT / "README.md",
        ROOT / "tool" / "README.md",
        ROOT / "tool" / "app.py",
        ROOT / "tool" / "report_renderer.py",
        ROOT / "tool" / "templates" / "client_deck.html",
        ROOT / "tool" / "templates" / "report.html",
        ROOT / "tool" / "static" / "app.js",
        ROOT / "tool" / "requirements.txt",
    ]
    forbidden_export_markers = (
        "PowerPoint",
        ".pptx",
        "pptx_url",
        "/pptx",
        "PDF",
        ".pdf",
        "pdf_url",
        "/pdf",
        "pdf_renderer",
        "Playwright",
        "playwright",
    )
    for path in active_surface_files:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden_export_markers:
            if marker in text:
                failures.append(
                    f"{path.relative_to(ROOT)} contains forbidden export marker: {marker}"
                )

    stale_export_files = (
        ROOT / "tool" / "pptx_renderer.py",
        ROOT / "tool" / "pdf_renderer.py",
    )
    for path in stale_export_files:
        if path.exists():
            failures.append(f"Stale export renderer must not be active: {path.relative_to(ROOT)}")

    if failures:
        print("BUNDLE VALIDATION: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("BUNDLE VALIDATION: PASS")
    print(f"- skills: {len(SKILLS)}")
    print(f"- routing cases: {len(cases)}")
    print(f"- conversion layer cases: {len(layer_cases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

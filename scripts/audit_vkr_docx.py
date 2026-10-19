"""Independently inspect the public thesis package without altering it or running science."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import shlex
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
THESIS = ROOT / "docs/thesis"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}
W = "{" + NS["w"] + "}"
R = "{" + NS["r"] + "}"
PRIVATE = re.compile(
    r"sc-[a-f0-9]{24}|Unit[a-f0-9]{8}|sk-[A-Za-z0-9_-]{16,}"
    r"|/Users/|/home/|/private/|file://|[A-Za-z]:[\\/]Users[\\/]",
    re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_name(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return path.name


def text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter() if node.tag in {W + "t"})


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def enabled(element: ET.Element) -> bool:
    return element.get(W + "val", "true").lower() not in {"0", "false", "off", "no"}


@dataclass
class Audit:
    checks: list[dict[str, Any]] = field(default_factory=list)
    measurements: dict[str, Any] = field(default_factory=dict)

    def check(self, name: str, condition: bool, detail: Any) -> None:
        self.checks.append(
            {"check": name, "status": "PASS" if condition else "FAIL", "detail": detail}
        )

    def note(self, name: str, detail: Any) -> None:
        self.checks.append({"check": name, "status": "INFO", "detail": detail})

    @property
    def failed(self) -> bool:
        return any(c["status"] == "FAIL" for c in self.checks)


def fields(root: ET.Element) -> tuple[list[str], list[str]]:
    """Reassemble fragmented/nested complex fields, and support simple fields as well."""
    result: list[str] = []
    errors: list[str] = []
    stack: list[dict[str, Any]] = []
    for node in root.iter():
        if node.tag == W + "fldSimple":
            result.append(node.get(W + "instr", "").strip())
        elif node.tag == W + "fldChar":
            kind = node.get(W + "fldCharType")
            if kind == "begin":
                stack.append({"instruction": [], "separated": False})
            elif kind == "separate":
                if stack:
                    stack[-1]["separated"] = True
                else:
                    errors.append("orphan field separator")
            elif kind == "end":
                if stack:
                    result.append("".join(stack.pop()["instruction"]).strip())
                else:
                    errors.append("orphan field end")
        elif node.tag == W + "instrText":
            if stack and not stack[-1]["separated"]:
                stack[-1]["instruction"].append(node.text or "")
            elif not stack:
                errors.append("instruction outside complex field")
    errors.extend(["unclosed field"] * len(stack))
    return result, errors


def inspect_package(path: Path, audit: Audit) -> dict[str, ET.Element]:
    trees: dict[str, ET.Element] = {}
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            audit.check(
                "zip_integrity", archive.testzip() is None, "CRC validation of every member"
            )
            audit.check("zip_unique_members", len(names) == len(set(names)), len(names))
            unsafe = [n for n in names if n.startswith("/") or ".." in n.split("/") or "\\" in n]
            audit.check("zip_safe_member_names", not unsafe, unsafe)
            junk = [
                n
                for n in names
                if re.search(r"(?:^|/)(?:\.DS_Store|Thumbs\.db|__MACOSX)(?:/|$)", n)
                or re.search(
                    r"(?:vbaProject\.bin|/embeddings/|/activeX/|comments\d*\.xml)", n, re.I
                )
            ]
            audit.check("no_junk_macros_comments_embedded_objects", not junk, junk)
            for name in names:
                if not name.endswith((".xml", ".rels")):
                    continue
                raw = archive.read(name)
                if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
                    audit.check("xml_no_dtd_" + name, False, "DTD/entity declarations prohibited")
                    continue
                try:
                    trees[name] = ET.fromstring(raw)
                except ET.ParseError:
                    audit.check("xml_well_formed_" + name, False, "XML parse failure")
                if PRIVATE.search(raw.decode("utf-8", errors="replace")):
                    audit.check(
                        "public_safe_xml_" + name,
                        False,
                        "Private token/path pattern found; value redacted",
                    )
            audit.check(
                "all_xml_parts_parse",
                len(trees) == len([n for n in names if n.endswith((".xml", ".rels"))]),
                {"parsed_parts": len(trees)},
            )
            audit.check(
                "public_safe_package_text",
                not any(c["check"].startswith("public_safe_xml_") for c in audit.checks),
                "All XML parts, properties, relationship targets and custom XML inspected",
            )
            media = [n for n in names if n.startswith("word/media/") and not n.endswith("/")]
            audit.check(
                "embedded_media_count", len(media) == 17, {"actual": len(media), "expected": 17}
            )
            audit.check(
                "media_nonempty", all(archive.getinfo(n).file_size > 0 for n in media), len(media)
            )
            audit.measurements["media_parts"] = media
            relation_errors: list[str] = []
            relation_ids: dict[str, set[str]] = {}
            image_targets: set[str] = set()
            for name, tree in trees.items():
                if not name.endswith(".rels"):
                    continue
                source = (
                    ""
                    if name == "_rels/.rels"
                    else posixpath.join(
                        posixpath.dirname(posixpath.dirname(name)),
                        posixpath.basename(name).removesuffix(".rels"),
                    )
                )
                ids: set[str] = set()
                for rel in tree:
                    rid, target = rel.get("Id", ""), rel.get("Target", "")
                    kind = rel.get("Type", "")
                    if not rid or rid in ids:
                        relation_errors.append(name + ": duplicate/empty relationship ID")
                    ids.add(rid)
                    if rel.get("TargetMode") == "External":
                        if not kind.endswith("/hyperlink") or urlsplit(target).scheme not in {
                            "https",
                            "http",
                            "mailto",
                        }:
                            relation_errors.append(name + ": unsupported external relationship")
                        continue
                    resolved = posixpath.normpath(
                        posixpath.join(posixpath.dirname(source), unquote(target))
                    ).lstrip("/")
                    if resolved not in names:
                        relation_errors.append(name + ": unresolved internal relationship")
                    if kind.endswith("/image"):
                        image_targets.add(resolved)
                relation_ids[source] = ids
            for name, tree in trees.items():
                if name.endswith(".rels"):
                    continue
                for node in tree.iter():
                    for attr, value in node.attrib.items():
                        if attr in {
                            R + "id",
                            R + "embed",
                            R + "link",
                        } and value not in relation_ids.get(name, set()):
                            relation_errors.append(name + ": unresolved relationship attribute")
            audit.check("relationship_targets_resolve", not relation_errors, relation_errors)
            content_types = trees.get("[Content_Types].xml")
            if content_types is not None:
                extensions = {
                    n.get("Extension", "") for n in content_types.findall("ct:Default", NS)
                }
                overrides = {
                    n.get("PartName", "").lstrip("/")
                    for n in content_types.findall("ct:Override", NS)
                }
                untyped = [
                    n
                    for n in names
                    if not n.endswith("/")
                    and n != "[Content_Types].xml"
                    and n not in overrides
                    and n.rsplit(".", 1)[-1] not in extensions
                ]
                audit.check("all_parts_have_content_types", not untyped, untyped)
            audit.check(
                "every_image_embedded_and_used",
                image_targets == set(media),
                {"linked_images": len(image_targets), "media": len(media)},
            )
            audit.measurements["zip_members"] = len(names)
            audit.measurements["xml_parts"] = len(trees)
    except (BadZipFile, OSError):
        audit.check("zip_integrity", False, "Unreadable or invalid DOCX ZIP")
    return trees


def inspect_structure(trees: dict[str, ET.Element], audit: Audit) -> None:
    required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml"}
    audit.check("required_ooxml_parts", required <= trees.keys(), sorted(required - trees.keys()))
    if not required <= trees.keys():
        return
    document = trees["word/document.xml"]
    forbidden_tags = {
        "ins",
        "del",
        "delText",
        "moveFrom",
        "moveTo",
        "moveFromRangeStart",
        "moveToRangeStart",
        "commentRangeStart",
        "commentRangeEnd",
        "commentReference",
        "altChunk",
        "object",
    }
    forbidden: Counter[str] = Counter()
    hidden = 0
    all_fields: list[str] = []
    field_errors: list[str] = []
    for name, tree in trees.items():
        if not name.startswith("word/") or name.endswith(".rels"):
            continue
        for node in tree.iter():
            if node.tag in {W + tag for tag in forbidden_tags}:
                forbidden[node.tag.split("}")[-1]] += 1
            if node.tag in {W + "vanish", W + "webHidden"} and enabled(node):
                hidden += 1
        found, errors = fields(tree)
        all_fields.extend(found)
        field_errors.extend(name + ": " + e for e in errors)
    audit.check("no_revisions_comments_objects", not forbidden, dict(forbidden))
    audit.check("no_hidden_text", hidden == 0, hidden)
    audit.check("field_structure_balanced", not field_errors, field_errors)
    field_types = Counter(code.split()[0].upper() for code in all_fields if code.split())
    audit.check(
        "required_native_fields",
        {"TOC", "PAGE", "NUMPAGES", "REF", "SEQ"} <= field_types.keys(),
        dict(field_types),
    )
    starts = document.findall(".//w:bookmarkStart", NS)
    ends = document.findall(".//w:bookmarkEnd", NS)
    names = [node.get(W + "name", "") for node in starts]
    ids = [node.get(W + "id", "") for node in starts]
    end_ids = [node.get(W + "id", "") for node in ends]
    audit.check("bookmark_names_unique", len(names) == len(set(names)), len(names))
    audit.check(
        "bookmark_pairs_complete",
        Counter(ids) == Counter(end_ids) and len(ids) == len(set(ids)),
        len(ids),
    )
    bad_refs: list[str] = []
    reference_count = 0
    for code in all_fields:
        try:
            tokens = shlex.split(code, posix=False)
        except ValueError:
            bad_refs.append("malformed field instruction")
            continue
        if tokens and tokens[0].upper() in {"REF", "PAGEREF"}:
            reference_count += 1
            if len(tokens) < 2 or tokens[1].strip('"') not in names:
                bad_refs.append("unresolved REF/PAGEREF bookmark")
    audit.check(
        "native_references_resolve",
        not bad_refs,
        {"references": reference_count, "errors": bad_refs},
    )
    visible = "\n".join(text_of(p) for p in document.findall(".//w:p", NS))
    for label, value in {
        "author": "Бендас Роман Александрович",
        "department": "кафедра программной инженерии",
        "group": "ПО-51м",
        "supervisor": "Петрик Е. А.",
    }.items():
        audit.check("confirmed_admin_" + label, visible.count(value) >= 2, value)
    bad_errors = re.findall(r"Error! [^\n]{0,80}|Ошибка! [^\n]{0,80}", visible)
    audit.check("no_cached_field_errors", not bad_errors, bad_errors)
    settings = trees.get("word/settings.xml")
    update = settings.find("w:updateFields", NS) if settings is not None else None
    audit.check(
        "fields_update_on_open", update is not None and enabled(update), "Word updateFields"
    )
    audit.measurements["fields"] = dict(field_types)
    audit.measurements["bookmarks"] = len(names)
    sections = document.findall(".//w:sectPr", NS)
    dimensions: list[dict[str, Any]] = []
    for index, section in enumerate(sections):
        page_size, margins = section.find("w:pgSz", NS), section.find("w:pgMar", NS)
        if page_size is None or margins is None:
            audit.check(f"section_{index + 1}_geometry", False, "Missing page geometry")
            continue
        width, height = int(page_size.get(W + "w", "0")), int(page_size.get(W + "h", "0"))
        landscape = page_size.get(W + "orient", "portrait") == "landscape"
        expected = (16838, 11906) if landscape else (11906, 16838)
        actual_margins = {
            k: int(margins.get(W + k, "0")) for k in ["left", "right", "top", "bottom"]
        }
        good_margins = all(
            abs(actual_margins[k] - v) <= 1
            for k, v in {"left": 1701, "right": 850, "top": 1134, "bottom": 1134}.items()
        )
        audit.check(
            f"section_{index + 1}_geometry",
            abs(width - expected[0]) <= 1 and abs(height - expected[1]) <= 1 and good_margins,
            {
                "orientation": "landscape" if landscape else "portrait",
                "size_twips": [width, height],
                "margins_twips": actual_margins,
            },
        )
        dimensions.append({"width": width, "height": height, "landscape": landscape})
    audit.check(
        "portrait_and_landscape_sections",
        any(d["landscape"] for d in dimensions) and any(not d["landscape"] for d in dimensions),
        len(dimensions),
    )
    styles = trees["word/styles.xml"]
    for name, size, spacing, indent in [
        ("Normal", 28, 360, 850),
        ("Heading1", 28, 360, 850),
        ("Heading2", 28, 360, 850),
        ("Heading3", 28, 360, 850),
        ("TableText", 24, 240, 0),
        ("Equation", 28, 360, 0),
        ("Bibliography", 28, 360, 850),
    ]:
        style = styles.find(f"w:style[@w:styleId='{name}']", NS)
        if style is None:
            audit.check("style_" + name, False, "Missing style")
            continue
        font = style.findall("w:rPr/w:rFonts", NS)
        sz = style.find("w:rPr/w:sz", NS)
        line = style.find("w:pPr/w:spacing", NS)
        first = style.find("w:pPr/w:ind", NS)
        matches = bool(font) and all(
            font[-1].get(W + k) == "Times New Roman" for k in ["ascii", "hAnsi"]
        )
        matches = matches and sz is not None and sz.get(W + "val") == str(size)
        matches = matches and line is not None and line.get(W + "line") == str(spacing)
        matches = matches and first is not None and first.get(W + "firstLine") == str(indent)
        audit.check(
            "style_" + name,
            matches,
            {"half_points": size, "line_twips": spacing, "first_line_twips": indent},
        )
    maths = document.findall(".//m:oMath", NS)
    audit.check("eight_editable_omml_equations", len(maths) == 8, len(maths))
    math_text = " ".join("".join(n.itertext()) for n in maths)
    audit.check(
        "math_no_source_tex_commands",
        not re.search(r"\\[A-Za-z]+|\$\$", math_text),
        "OMML math text; field switches excluded",
    )
    audit.check(
        "native_math_fractions",
        bool(document.findall(".//m:f/m:num", NS)) and bool(document.findall(".//m:f/m:den", NS)),
        "Editable OMML numerator and denominator nodes",
    )
    audit.check(
        "no_unexpanded_authoring_markers",
        not re.search(
            r"\[@[\w-]+\]|\[(?:рисунок|таблица):|<!--\s*(?:FIGURE|TABLE):|\$\$|UI_SCREENSHOTS_PENDING",
            visible,
        ),
        "Rendered visible body text",
    )
    placeholders = sorted(set(re.findall(r"\[ЗАПОЛНИТЬ:[^\]]+\]", visible)))
    audit.note(
        "administrative_placeholders",
        {
            "count": len(placeholders),
            "values": placeholders,
            "meaning": (
                "User-supplied administrative details remain visibly unfilled; "
                "no invented signatures"
            ),
        },
    )
    audit.measurements["equations"] = len(maths)
    audit.measurements["paragraphs"] = len(document.findall(".//w:p", NS))
    audit.measurements["table_parts"] = len(document.findall(".//w:tbl", NS))
    audit.measurements["section_geometry"] = dimensions


def inspect_sources(trees: dict[str, ET.Element], audit: Audit) -> None:
    manifest = load_json(THESIS / "internal/build-manifest.json")
    files = [THESIS / "source" / name for name in manifest["manuscript"]]
    audit.check("manuscript_sources_present", all(p.is_file() for p in files), len(files))
    if not all(p.is_file() for p in files) or "word/document.xml" not in trees:
        return
    source_text = "\n".join(p.read_text(encoding="utf-8") for p in files)
    code_lines: list[str] = []
    for path in files:
        inside_code = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("```"):
                inside_code = not inside_code
            elif inside_code:
                code_lines.append(line)
    library = load_json(THESIS / "internal/references.json")
    by_key = {item["key"]: item for item in library}
    citations: dict[str, int] = {}
    for match in re.finditer(r"\[@([\w-]+)\]", source_text):
        citations.setdefault(match[1], len(citations) + 1)
    audit.check(
        "65_verified_source_citations",
        len(citations) == 65
        and all(k in by_key and by_key[k].get("verified") is True for k in citations),
        {"cited_keys": len(citations), "library_entries": len(library)},
    )
    document = trees["word/document.xml"]
    paragraphs = document.findall(".//w:p", NS)
    bibliography: list[str] = []
    actual_code: list[str] = []
    actual_citations: Counter[int] = Counter()
    for paragraph in paragraphs:
        style = paragraph.find("w:pPr/w:pStyle", NS)
        text = text_of(paragraph)
        if style is not None and style.get(W + "val") == "Bibliography":
            bibliography.append(normalized(text))
        else:
            actual_citations.update(int(n) for n in re.findall(r"\[(\d{1,3})\]", text))
        if style is not None and style.get(W + "val") == "CodeExample":
            actual_code.append(text)
    audit.check(
        "code_examples_preserved_verbatim",
        actual_code == code_lines,
        {
            "source_lines": len(code_lines),
            "word_lines": len(actual_code),
            "meaning": "Literal code must preserve glob asterisks and indentation",
        },
    )
    expected_bibliography = [
        normalized(f"{number} {by_key[key]['bibliography']}")
        for key, number in citations.items()
        if key in by_key
    ]
    audit.check(
        "bibliography_matches_verified_entries",
        bibliography == expected_bibliography and len(bibliography) == 65,
        {"actual_entries": len(bibliography), "expected_entries": len(expected_bibliography)},
    )
    expected_citations: Counter[int] = Counter(
        citations[m[1]] for m in re.finditer(r"\[@([\w-]+)\]", source_text)
    )
    audit.check(
        "all_numeric_citations_resolve_and_match",
        actual_citations == expected_citations and set(actual_citations) <= set(range(1, 66)),
        {
            "actual_occurrences": sum(actual_citations.values()),
            "expected_occurrences": sum(expected_citations.values()),
            "unique_numbers": len(actual_citations),
        },
    )
    bookmarks = {n.get(W + "name", "") for n in document.findall(".//w:bookmarkStart", NS)}
    markers = re.findall(r"<!--\s*(FIGURE|TABLE):([\w-]+)\s*\|", source_text)
    expected_bookmarks = [
        ("fig_" if kind == "FIGURE" else "tbl_") + key.replace("-", "_") for kind, key in markers
    ]
    audit.check(
        "all_caption_bookmarks_resolve",
        all(k[:40] in bookmarks for k in expected_bookmarks)
        and len({k[:40] for k in expected_bookmarks}) == len(expected_bookmarks),
        {
            "figures": sum(k == "FIGURE" for k, _ in markers),
            "tables": sum(k == "TABLE" for k, _ in markers),
        },
    )
    audit.check(
        "source_equation_count",
        len(re.findall(r"^\$\$", source_text, re.M)) == 8,
        "Independent manuscript equation markers",
    )
    counts = load_json(THESIS / "internal/build-counts.json")
    mismatched = [
        public_name(p)
        for p in files
        if counts.get("source_sha256", {}).get(public_name(p)) != sha(p)
    ]
    audit.check("docx_build_source_snapshot_current", not mismatched, mismatched)
    audit.measurements["source_sha256"] = {public_name(p): sha(p) for p in files}
    audit.measurements["references_sha256"] = sha(THESIS / "internal/references.json")
    visible = "\n".join(text_of(p) for p in paragraphs)
    flat = normalized(visible)
    requirements = {
        "feature_leakage_retained": r"утечк[а-яё]*.{0,120}(?:признак|seed)|seed.{0,160}утечк",
        "natural_oss_no_positives": r"OSS.{0,120}без положительных|без положительных.{0,150}OSS",
        "context_quality_decrease": r"снижен[а-яё]*.{0,45}качеств|потер[а-яё]*.{0,45}качеств",
        "architecture_error_retained": r"TP=149, FP=0, TN=149, FN=1",
        "provider_missing_retained": (
            r"298.{0,100}два.{0,100}(?:пропуск|отсутств)|"
            r"два.{0,100}(?:пропуск|отсутств).{0,100}298"
        ),
        "security_positive_nondefinitive": r"47 из 85",
        "security_negative_nondefinitive": r"103.{0,80}неокончательн|неокончательн.{0,80}103",
        "security_no_definitive_negatives": (
            r"окончательных отрицательных.{0,100}нет|"
            r"отрицательных решений нет|ни один из 106"
        ),
        "security_final_decline": r"56,76.{0,30}44,71|−12,0509",
        "no_blind_v2_final_baseline": r"FINAL.{0,30}V2 не проводилась|FINAL-база V2 отсутствует",
        "invoice_not_measured": (
            r"фактическая сумма не была установлена|"
            r"счет.{0,100}не.{0,50}измерен|invoice.{0,30}null"
        ),
        "not_production_claim": (
            r"промышленн.{0,60}готовност.{0,80}не|не.{0,80}промышленн.{0,60}готовност|"
            r"SECURITY_PRODUCTION_READINESS.{0,20}NOT_CLAIMED"
        ),
    }
    for name, pattern in requirements.items():
        audit.check(
            "negative_presence_" + name,
            re.search(pattern, flat, re.I) is not None,
            "Required limitation located in actual DOCX visible text",
        )
    risk_patterns = {
        "universal_security_guarantee": r"гарантирует отсутствие (?:уязвимостей|ошибок)",
        "all_vulnerabilities_found": r"обнаружены все уязвимости",
        "claimed_production_readiness": r"доказана промышленная готовность",
        "cost_called_actual": (
            r"фактическ[а-яё ]{0,50}(?:затрат|расход|стоимост)"
            r"[^.!?\n]{0,70}0[.,]1467331"
        ),
        "claimed_quality_preservation": r"качество не снизилось|качество полностью сохранено",
    }
    risky: list[dict[str, str]] = []
    for name, pattern in risk_patterns.items():
        for match in re.finditer(pattern, visible, re.I):
            context = visible[max(0, match.start() - 120) : min(len(visible), match.end() + 120)]
            negated = bool(
                re.search(
                    r"не |нельзя|не означает|не доказывает|не утверждается|не установлено",
                    context[: match.start() - max(0, match.start() - 120)],
                    re.I,
                )
            )
            risky.append(
                {
                    "category": name,
                    "context": normalized(context),
                    "assessment": "QUALIFIED" if negated else "REVIEW_REQUIRED",
                }
            )
    audit.check(
        "overclaim_context_review", all(r["assessment"] == "QUALIFIED" for r in risky), risky
    )
    audit.note(
        "scientific_review_boundary",
        "Presence and contextual language checks complement THESIS_FACT_AUDIT.md and the "
        "independent manuscript review; they are not an automated proof of scientific validity. "
        "No truth/case data or scientific execution is used.",
    )


def write_report(audit: Audit, docx: Path, output: Path) -> None:
    status = "FAIL" if audit.failed else "PASS"
    report = {
        "schema": "archguard-thesis-docx-independent-audit-v1",
        "audited_at_utc": datetime.now(UTC).isoformat(),
        "artifact": public_name(docx),
        "sha256": sha(docx) if docx.is_file() else None,
        "result": status,
        "public_only": True,
        "scientific_runs": 0,
        "private_case_reads": 0,
        "artifact_modified": False,
        "visual_layout_verified_by_this_script": False,
        "checks": audit.checks,
        "measurements": audit.measurements,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    totals = Counter(c["status"] for c in audit.checks)
    lines = [
        "# Независимый аудит целостности Word-файла",
        "",
        f"Результат: **{status}**. Артефакт: `{public_name(docx)}`.",
        f"SHA-256: `{report['sha256']}`.",
        f"Проверки: PASS={totals['PASS']}, FAIL={totals['FAIL']}, INFO={totals['INFO']}.",
        "",
        "Аудитор читает ZIP/OOXML и новые публичные авторские материалы. "
        "Он не изменяет Word-файл, не открывает приватные случаи и не запускает "
        "научные вычисления. Проверены все XML-части, связи, поля, закладки, "
        "формулы, источники и явно сохраненные отрицательные результаты.",
        "",
        "Геометрия и стили проверены по OOXML. Эта проверка не подтверждает визуальную "
        "верстку: ее завершает отдельное чтение отрендеренных страниц. Административные "
        "поля [ЗАПОЛНИТЬ: …] сохранены явно и не выданы за подписи или установленные сведения.",
        "",
        "| Проверка | Результат |",
        "|---|---|",
    ]
    lines.extend(f"| {c['check']} | {c['status']} |" for c in audit.checks)
    lines.extend(
        [
            "",
            "Полные параметры, числители проверок и снимки исходников: `internal/docx-audit.json`.",
            "",
            "Научная проверка агрегатов и ограничений: `THESIS_FACT_AUDIT.md`; "
            "приложение Е независимо сверено по 179 числовым ячейкам "
            "в `internal/appendix-e-review.json`.",
            "",
        ]
    )
    (THESIS / "THESIS_INTEGRITY_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {"result": status, "checks": dict(totals), "report": public_name(output)},
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", type=Path, default=THESIS / "ArchGuard_AI_VKR_MASTER.docx")
    parser.add_argument("--output", type=Path, default=THESIS / "internal/docx-audit.json")
    args = parser.parse_args()
    audit = Audit()
    audit.check("artifact_exists", args.docx.is_file(), public_name(args.docx))
    if args.docx.is_file():
        trees = inspect_package(args.docx, audit)
        inspect_structure(trees, audit)
        inspect_sources(trees, audit)
        counts = load_json(THESIS / "internal/build-counts.json")
        audit.check(
            "build_manifest_artifact_hash",
            counts.get("docx_sha256") == sha(args.docx),
            "Exact built artifact, independently hashed",
        )
    write_report(audit, args.docx, args.output)
    if audit.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

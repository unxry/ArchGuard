"""Audit every rendered thesis page; keep visual review separate from measured checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
THESIS = ROOT / "docs/thesis"
H = {"h": "http://www.w3.org/1999/xhtml"}
W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("\u00ad", "")


def audit_pages(bbox: Path) -> list[dict[str, Any]]:
    result = []
    for number, page in enumerate(ET.parse(bbox).findall(".//h:page", H), 1):
        width, height = float(page.attrib["width"]), float(page.attrib["height"])
        words = sorted(
            page.findall(".//h:word", H),
            key=lambda word: (round(float(word.attrib["yMin"]), 1), float(word.attrib["xMin"])),
        )
        footers = [
            w for w in words if w.text == str(number) and float(w.attrib["yMin"]) > height - 57
        ]
        body = [w for w in words if w not in footers]
        overflow = [
            w.text
            for w in body
            if float(w.attrib["xMin"]) < 85.05 - 2
            or float(w.attrib["xMax"]) > width - 42.5 + 2
            or float(w.attrib["yMin"]) < 56.7 - 3
            or float(w.attrib["yMax"]) > height - 56.7 + 3
        ]
        result.append(
            dict(
                page=number,
                dimensions_pt=[width, height],
                words=len(body),
                text_overflow=overflow,
                footer_correct=len(footers) == (0 if number == 1 else 1),
                low_density=len(body) < 70,
                content_bottom_pt=max((float(w.attrib["yMax"]) for w in body), default=0),
                text=" ".join(w.text or "" for w in body),
            )
        )
    return result


def audit_objects(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from build_vkr_docx import ThesisBuilder, read_json

    builder = ThesisBuilder(read_json(THESIS / "internal/build-manifest.json"))
    with ZipFile(THESIS / "ArchGuard_AI_VKR_MASTER.docx") as package:
        document = ET.fromstring(package.read("word/document.xml"))
    captions: dict[str, int] = {}
    references: dict[str, list[int]] = defaultdict(list)
    for index, paragraph in enumerate(document.findall(".//w:p", W)):
        for bookmark in paragraph.findall("w:bookmarkStart", W):
            name = bookmark.get("{" + W["w"] + "}name", "")
            if name.startswith(("fig_", "tbl_")):
                captions[name] = index
        for instruction in paragraph.findall(".//w:instrText", W):
            match = re.match(r"\s*REF\s+((?:fig|tbl)_\w+)", instruction.text or "")
            if match:
                references[match[1]].append(index)
    objects = []
    for kind, entries in (("Рисунок", builder.figures), ("Таблица", builder.tables)):
        for entry in entries.values():
            bookmark = entry["bookmark"][:40]
            token = normalized(f"{kind} {entry['number']} — {entry['caption']}")
            rendered = [p["page"] for p in pages if token in normalized(p["text"])]
            continuation_token = re.escape(normalized("Продолжение таблицы " + entry["number"]))
            continued = [
                p["page"]
                for p in pages
                if re.search(continuation_token + r"(?![\d.])", normalized(p["text"]))
            ]
            first_reference = min(references.get(bookmark, [10**9]))
            objects.append(
                dict(
                    kind=kind,
                    key=entry["key"],
                    number=entry["number"],
                    caption=entry["caption"],
                    pages=rendered,
                    continuation_pages=continued if kind == "Таблица" else [],
                    referenced_before_caption=first_reference < captions.get(bookmark, -1),
                )
            )
    return objects


def audit_fonts(pdf: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    uses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for number, page in enumerate(PdfReader(pdf).pages, 1):

        def visitor(
            text: str, cm: Any, tm: Any, font: Any, size: Any, number: int = number
        ) -> None:
            name = str((font or {}).get("/BaseFont", ""))
            if text.strip() and "TimesNewRoman" not in name and "CourierNew" not in name:
                uses[name].append(dict(page=number, text=text.strip()))

        page.extract_text(visitor_text=visitor)
    return dict(uses)


def audit_headings(bbox: Path) -> dict[str, Any]:
    pagination = json.loads((THESIS / "internal/pagination.json").read_text())
    pages = ET.parse(bbox).findall(".//h:page", H)
    missing, orphans = [], []
    for title, number in pagination["headings"].items():
        page = pages[number - 1]
        words = sorted(
            page.findall(".//h:word", H),
            key=lambda word: (round(float(word.attrib["yMin"]), 1), float(word.attrib["xMin"])),
        )
        text = "".join(normalized(w.text or "") for w in words)
        start = text.find(normalized(title))
        if start < 0:
            missing.append(title)
            continue
        offset, selected = 0, []
        for word in words:
            end = offset + len(normalized(word.text or ""))
            if end > start and offset < start + len(normalized(title)):
                selected.append(word)
            offset = end
        bottom = max(float(w.attrib["yMax"]) for w in selected)
        following = {
            round(float(w.attrib["yMin"]), 1)
            for w in words
            if bottom < float(w.attrib["yMin"]) < float(page.attrib["height"]) - 57
        }
        if len(following) < 2:
            orphans.append(dict(title=title, page=number, following_lines=len(following)))
    return dict(checked=len(pagination["headings"]), missing=missing, orphan_candidates=orphans)


def audit_table_rows() -> dict[str, Any]:
    counts = json.loads((THESIS / "internal/build-counts.json").read_text())

    def cell_text(value: str) -> str:
        value = re.sub(
            r"\[@([\w-]+(?:;\s*@[\w-]+)*)\]",
            lambda m: (
                "["
                + "; ".join(str(counts["citation_order"][k]) for k in re.findall(r"[\w-]+", m[1]))
                + "]"
            ),
            value,
        )
        return normalized(value.replace("**", "").replace("`", "").replace("<br>", "\n"))

    expected: dict[str, list[list[str]]] = {}
    key = ""
    for path in (THESIS / "source").rglob("*.md"):
        for line in path.read_text().splitlines():
            match = re.match(r"<!-- TABLE:([\w-]+) \|", line)
            if match:
                key = match[1]
                expected[key] = []
            elif line.startswith("|") and key:
                row = [cell_text(c.strip()) for c in line.strip("|").split("|")]
                if not all(re.fullmatch(r"[:\-]+", c) for c in row):
                    expected[key].append(row)
            elif line.strip():
                key = ""
    with ZipFile(THESIS / "ArchGuard_AI_VKR_MASTER.docx") as package:
        root = ET.fromstring(package.read("word/document.xml"))
    bookmarks = {("tbl_" + k.replace("-", "_"))[:40]: k for k in expected}
    actual: dict[str, list[list[str]]] = defaultdict(list)
    errors, parts = [], 0
    for element in root.find("w:body", W):  # type: ignore[union-attr]
        if element.tag.endswith("}p"):
            for mark in element.findall("w:bookmarkStart", W):
                name = mark.get("{" + W["w"] + "}name", "")
                if name in bookmarks:
                    key = bookmarks[name]
        elif element.tag.endswith("}tbl"):
            parts += 1
            rows = element.findall("w:tr", W)
            if rows[0].find("w:trPr/w:tblHeader", W) is None:
                errors.append(key + ": missing repeated header")
            for index, row in enumerate(rows):
                values = [
                    normalized("".join(t.text or "" for t in cell.findall(".//w:t", W)))
                    for cell in row.findall("w:tc", W)
                ]
                if not any(values) or row.find("w:trPr/w:cantSplit", W) is None:
                    errors.append(key + ": empty or splittable row")
                if index == 0:
                    if values != expected[key][0]:
                        errors.append(key + ": header mismatch")
                else:
                    actual[key].append(values)
    errors += [key + ": data mismatch" for key in expected if actual[key] != expected[key][1:]]
    return dict(logical_tables=len(expected), physical_parts=parts, errors=errors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdftotext", type=Path, required=True)
    args = parser.parse_args()
    pdf = THESIS / "render/ArchGuard_AI_VKR_MASTER.pdf"
    bbox = THESIS / "render/layout.html"
    subprocess.run([str(args.pdftotext), "-bbox-layout", str(pdf), str(bbox)], check=True)
    pages = audit_pages(bbox)
    objects = audit_objects(pages)
    headings = audit_headings(bbox)
    tables = audit_table_rows()
    problems = [p["page"] for p in pages if p["text_overflow"] or not p["footer_correct"]]
    missing = [o["key"] for o in objects if not o["pages"] or not o["referenced_before_caption"]]
    report = dict(
        schema="archguard-render-measurement-v1",
        docx_sha256=digest(THESIS / "ArchGuard_AI_VKR_MASTER.docx"),
        pdf_sha256=digest(pdf),
        pages_checked=len(pages),
        coordinate_tolerance_pt=dict(horizontal=2, vertical=3),
        method="Poppler word boxes; separate actual footer; all page and caption locations",
        visual_review_claimed=False,
        overflow_or_footer_pages=problems,
        blank_pages=[p["page"] for p in pages if not p["words"]],
        low_density_pages=[p["page"] for p in pages if p["low_density"]],
        object_errors=missing,
        objects=objects,
        heading_audit=headings,
        table_row_audit=tables,
        whitespace_candidates=[
            p["page"] for p in pages if p["content_bottom_pt"] < p["dimensions_pt"][1] * 0.65
        ],
        non_body_fonts=audit_fonts(pdf),
        pages=[{k: v for k, v in p.items() if k != "text"} for p in pages],
    )
    (THESIS / "internal/render-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "pages_checked",
                    "overflow_or_footer_pages",
                    "blank_pages",
                    "low_density_pages",
                    "object_errors",
                )
            }
        )
    )
    if problems or missing or report["blank_pages"] or tables["errors"] or headings["missing"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

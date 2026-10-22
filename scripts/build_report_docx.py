#!/usr/bin/env python3
"""Create a simple DOCX proofreading report from structured report JSON."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from validate_review import validate
from runtime_common import configure_stdio

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
W = "{" + W_NS + "}"
CT = "{" + CT_NS + "}"
REL = "{" + REL_NS + "}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("pr", REL_NS)
ET.register_namespace("ct", CT_NS)

ISSUE_FIELDS = (
    ("status", "问题性质"),
    ("basis", "核验依据/来源"),
)


def display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def add_run(paragraph: ET.Element, text: str, bold: bool = False) -> None:
    for character in text:
        code = ord(character)
        if not (code in (9, 10, 13) or 0x20 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF):
            raise ValueError(f"Report contains invalid XML character U+{code:04X}; verify the extracted glyph before exporting")
    for line_index, line in enumerate(text.splitlines() or [""]):
        if line_index:
            run = ET.SubElement(paragraph, W + "r")
            ET.SubElement(run, W + "br")
        run = ET.SubElement(paragraph, W + "r")
        if bold:
            props = ET.SubElement(run, W + "rPr")
            ET.SubElement(props, W + "b")
        node = ET.SubElement(run, W + "t")
        node.set(XML_SPACE, "preserve")
        node.text = line


def add_paragraph(body: ET.Element, text: str, style: str = "Normal", bold: bool = False) -> None:
    paragraph = ET.SubElement(body, W + "p")
    props = ET.SubElement(paragraph, W + "pPr")
    style_node = ET.SubElement(props, W + "pStyle")
    style_node.set(W + "val", style)
    add_run(paragraph, text, bold=bold)


def location_revision(location: dict[str, Any], issue: dict[str, Any] | None = None) -> tuple[str, str]:
    """Format authored advice only. A report renderer must never invent edits."""
    issue = issue or {}
    error_type = display(location.get("error_type", "")).strip()
    suggested = display(
        location.get("suggested")
        or location.get("correction")
        or location.get("suggestion")
        or issue.get("suggestion") or ""
    ).strip()
    return error_type or display(issue.get("category")) or "未细分（请编辑核对）", suggested or "请编辑根据原图核对"


def make_styles() -> ET.Element:
    root = ET.Element(W + "styles")
    for style_id, name, size, bold, based_on in (
        ("Normal", "Normal", "22", False, None),
        ("Title", "Title", "34", True, "Normal"),
        ("Heading1", "heading 1", "30", True, "Normal"),
        ("Heading2", "heading 2", "24", True, "Normal"),
    ):
        style = ET.SubElement(root, W + "style", {W + "type": "paragraph", W + "styleId": style_id})
        if style_id == "Normal":
            style.set(W + "default", "1")
        ET.SubElement(style, W + "name", {W + "val": name})
        if based_on:
            ET.SubElement(style, W + "basedOn", {W + "val": based_on})
        paragraph_props = ET.SubElement(style, W + "pPr")
        ET.SubElement(paragraph_props, W + "spacing", {W + "after": "120", W + "line": "300", W + "lineRule": "auto"})
        run_props = ET.SubElement(style, W + "rPr")
        ET.SubElement(run_props, W + "rFonts", {W + "ascii": "Arial", W + "hAnsi": "Arial", W + "eastAsia": "SimSun"})
        ET.SubElement(run_props, W + "sz", {W + "val": size})
        if bold:
            ET.SubElement(run_props, W + "b")
    return root


def make_document(report: dict[str, Any]) -> ET.Element:
    document = ET.Element(W + "document")
    body = ET.SubElement(document, W + "body")
    add_paragraph(body, display(report.get("title") or "英语教辅编校问题清单"), "Title")

    metadata = report.get("metadata", {})
    if isinstance(metadata, dict):
        for key, label in (("manuscript", "稿件"), ("scope", "核对范围"), ("report_date", "日期")):
            if metadata.get(key):
                add_paragraph(body, f"{label}：{display(metadata[key])}")

    add_paragraph(body, "校对结果", "Heading1")
    summary = report.get("summary", {})
    if isinstance(summary, dict):
        for key, value in summary.items():
            if key == "structural_findings":
                continue
            if key == "issue_counts" and isinstance(value, dict):
                add_paragraph(body, "；".join(f"{status} {count} 项" for status, count in value.items()))
            elif not isinstance(value, (dict, list)):
                add_paragraph(body, display(value))
        for finding in summary.get("structural_findings", []):
            if not isinstance(finding, dict):
                continue
            label = {"pass": "核对未发现不符", "mismatch": "发现不符", "incomplete": "尚未核完"}.get(finding.get("status"), "待核")
            add_paragraph(body, f"{display(finding.get('check'))}：{label}，已核 {display(finding.get('checked_count'))} 条，不符 {display(finding.get('mismatch_count'))} 条。范围：{display(finding.get('scope'))}。")

    add_paragraph(body, "问题条目", "Heading1")
    issues = report.get("issues", [])
    if not issues:
        add_paragraph(body, "本次所列范围及可读材料内未发现问题。")
    else:
        add_paragraph(body, "以下修改建议供编辑确认，未改动原稿。")
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        locations = issue.get("locations", [])
        locators = "；".join(display(location.get("locator", "")) for location in locations if isinstance(location, dict))
        add_paragraph(body, f"{display(issue.get('id'))}｜{locators}", "Heading2")
        if issue.get("severity") == "高":
            add_paragraph(body, "重点复核：本项可能影响题意、答案或核心信息。", bold=True)
        scope = issue.get("scope")
        if isinstance(scope, dict):
            add_paragraph(body, f"影响范围：{display(scope.get('description'))}")
        count = issue.get("occurrence_count")
        if count is not None:
            estimate = "约 " if issue.get("count_status") == "estimated" else ""
            add_paragraph(body, f"出现次数：{estimate}{display(count)}；以下列出 {len(locations)} 个定位样例。计数依据：{display(issue.get('count_basis'))}")
        elif len(locations) > 1:
            add_paragraph(body, f"影响位置数：{len(locations)}")
        for location in locations:
            if not isinstance(location, dict):
                continue
            add_paragraph(body, f"位置：{display(location.get('locator', ''))}", bold=True)
            if location.get("source_id"):
                add_paragraph(body, f"文件：{display(location['source_id'])}")
            page = location.get("file_page") or location.get("page") or "见位置"
            question = location.get("question") or location.get("question_id") or location.get("entry") or "非题目正文"
            printed = f"；印刷页 {location['printed_page']}" if location.get("printed_page") is not None else ""
            add_paragraph(body, f"页码：文件页 {display(page)}{printed}")
            add_paragraph(body, f"题号/词条：{display(question)}")
            quote = location.get("quote")
            if quote:
                add_paragraph(body, f"原文证据：{display(quote)}")
                error_type, suggested = location_revision(location, issue)
                add_paragraph(body, f"错误类型：{error_type}")
                add_paragraph(body, f"具体问题：{display(issue.get('explanation') or issue.get('basis') or '请结合原文证据核对')}")
                add_paragraph(body, f"修改建议：{suggested}")
            elif location.get("error_type") or location.get("suggested"):
                error_type, suggested = location_revision(location, issue)
                add_paragraph(body, f"错误类型：{error_type}")
                add_paragraph(body, f"具体问题：{display(issue.get('explanation') or issue.get('basis') or '请结合位置核对')}")
                add_paragraph(body, f"修改建议：{suggested}")
        for key, label in ISSUE_FIELDS:
            value = issue.get(key)
            if value not in (None, ""):
                add_paragraph(body, f"{label}：{display(value)}")

    add_paragraph(body, "简短说明", "Heading1")
    coverage = report.get("coverage", {})
    if isinstance(coverage, dict):
        limitations = [display(item) for item in coverage.get("limitations", []) if str(item).strip()]
        if coverage.get("mode") == "single_delivery":
            if coverage.get("completed") is True and not limitations:
                add_paragraph(body, "已完成本次单份稿件的检查与复核。")
            elif not limitations:
                add_paragraph(body, "本次按单份稿件交付，已核范围见上。")
            if limitations:
                add_paragraph(body, "待核：" + "；".join(limitations))
        elif coverage.get("three_passes_complete") and not limitations:
            add_paragraph(body, "已完成本次指定范围的三校。")
        elif limitations:
            status = "三校尚未全部完成。" if not coverage.get("three_passes_complete") else "已完成本次指定范围的三校。"
            add_paragraph(body, f"{status} 限制：{'；'.join(limitations)}")
        else:
            add_paragraph(body, "三校状态以内部校验记录为准。")

    section = ET.SubElement(body, W + "sectPr")
    ET.SubElement(section, W + "pgSz", {W + "w": "11906", W + "h": "16838"})
    ET.SubElement(section, W + "pgMar", {W + "top": "1440", W + "right": "1440", W + "bottom": "1440", W + "left": "1440", W + "header": "720", W + "footer": "720", W + "gutter": "0"})
    return document


def visible_character_count(report: dict[str, Any]) -> int:
    document = make_document(report)
    return sum(
        1
        for node in document.iter(W + "t")
        for character in (node.text or "")
        if not character.isspace()
    )


def confirmed_location_count(report: dict[str, Any]) -> int:
    return sum(issue.get("occurrence_count", len(issue.get("locations", [])))
               for issue in report.get("issues", []) if isinstance(issue, dict)
               and issue.get("status") in ("明确差错", "体例/一致性")
               and type(issue.get("occurrence_count", 0)) is int)


def build(report: dict[str, Any], output: Path) -> None:
    if output.suffix.casefold() != ".docx":
        raise ValueError("Word report output must use the .docx extension")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = make_document(report)
    content_types = ET.Element(CT + "Types")
    ET.SubElement(content_types, CT + "Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(content_types, CT + "Default", {"Extension": "xml", "ContentType": "application/xml"})
    ET.SubElement(content_types, CT + "Override", {"PartName": "/word/document.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"})
    ET.SubElement(content_types, CT + "Override", {"PartName": "/word/styles.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"})

    package_rels = ET.Element(REL + "Relationships")
    ET.SubElement(package_rels, REL + "Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
        "Target": "word/document.xml",
    })
    document_rels = ET.Element(REL + "Relationships")
    ET.SubElement(document_rels, REL + "Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
        "Target": "styles.xml",
    })

    parts = {
        "[Content_Types].xml": ET.tostring(content_types, encoding="utf-8", xml_declaration=True),
        "_rels/.rels": ET.tostring(package_rels, encoding="utf-8", xml_declaration=True),
        "word/document.xml": ET.tostring(document, encoding="utf-8", xml_declaration=True),
        "word/styles.xml": ET.tostring(make_styles(), encoding="utf-8", xml_declaration=True),
        "word/_rels/document.xml.rels": ET.tostring(document_rels, encoding="utf-8", xml_declaration=True),
    }
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    with zipfile.ZipFile(output) as archive:
        bad_file = archive.testzip()
        if bad_file:
            output.unlink(missing_ok=True)
            raise ValueError(f"DOCX package validation failed at {bad_file}")
        ET.fromstring(archive.read("word/document.xml"))


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="structured report JSON")
    parser.add_argument("output", type=Path, help="new .docx path; existing files are never overwritten")
    parser.add_argument("--threshold", type=int, default=3000, help="generate only when visible report characters exceed this number (default: 3000)")
    parser.add_argument("--always", action="store_true", help="generate even when the report is at or below the threshold")
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8-sig"))
        if not isinstance(report, dict):
            raise ValueError("report JSON top-level value must be an object")
        if args.threshold < 0:
            raise ValueError("--threshold must be zero or greater")
        validation = validate(report)
        if not validation["ok"]:
            raise ValueError("Report validation failed: " + "; ".join(validation["errors"]))
        character_count = visible_character_count(report)
        if not args.always and character_count <= args.threshold and confirmed_location_count(report) <= 10:
            print(f"DOCX not generated: report has {character_count} visible characters; threshold is {args.threshold}.")
            return 0
        build(report, args.output)
    except (OSError, json.JSONDecodeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Created and structurally validated: {args.output} ({character_count} visible characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

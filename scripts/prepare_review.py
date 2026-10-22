#!/usr/bin/env python3
"""Prepare read-only, page-aware assets for multimodal proofreading."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pdf_layout import analyze_layout
from runtime_common import configure_stdio

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{" + WORD_NS + "}"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def natural_key(value: str) -> list[tuple[int, object]]:
    return [(0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"(\d+)", value)]


def word_text(element: ET.Element) -> str:
    parts: list[str] = []
    for child in element.iter():
        if child.tag == W + "t":
            parts.append(child.text or "")
        elif child.tag == W + "tab":
            parts.append("\t")
        elif child.tag == W + "br":
            parts.append("\n")
    return "".join(parts).strip()


def extract_docx(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    warnings: list[str] = []
    blocks: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "word/document.xml" not in names:
            raise ValueError("DOCX package has no word/document.xml")
        root = ET.fromstring(archive.read("word/document.xml"))
        body = root.find(".//" + W + "body")
        if body is None:
            raise ValueError("DOCX has no document body")
        paragraph_no = 0
        table_no = 0
        for child in body:
            if child.tag == W + "p":
                paragraph_no += 1
                text = word_text(child)
                if text:
                    blocks.append({"block_id": f"DOCX-P{paragraph_no:05d}", "locator": f"正文段落 {paragraph_no}", "kind": "paragraph", "text": text})
            elif child.tag == W + "tbl":
                table_no += 1
                for row_no, row in enumerate(child.findall(W + "tr"), start=1):
                    cells = [word_text(cell) for cell in row.findall(W + "tc")]
                    blocks.append({"block_id": f"DOCX-T{table_no:03d}-R{row_no:04d}", "locator": f"表格 {table_no} 第 {row_no} 行", "kind": "table_row", "cells": cells, "text": "\t".join(cells)})
        if any(tag in archive.read("word/document.xml") for tag in (b"<w:ins", b"<w:del", b":ins", b":del")):
            warnings.append("DOCX contains tracked changes; review them in Word before relying on extracted text.")
        if any(name.startswith("word/header") or name.startswith("word/footer") or "footnotes" in name or "endnotes" in name for name in names):
            warnings.append("Headers, footers, footnotes, or endnotes may not be represented in the body text blocks; inspect the rendered pages.")
        if b"<w:drawing" in archive.read("word/document.xml") or "word/media/" in names:
            warnings.append("DOCX contains images or drawings; inspect the rendered page images for embedded text and figures.")
        if b"<w:numPr" in archive.read("word/document.xml"):
            warnings.append("Some Word automatic numbering may be absent from extracted text; verify question numbering on rendered pages.")
    return blocks, warnings


def load_fitz():
    try:
        import pymupdf
        return pymupdf
    except ModuleNotFoundError as exc:
        if exc.name != "pymupdf":
            raise RuntimeError(f"PyMuPDF dependency failed: {exc}") from exc
        try:
            import fitz  # compatibility with older PyMuPDF installations
            if not hasattr(fitz, "open") or not hasattr(fitz, "Matrix"):
                raise ImportError("fitz is not PyMuPDF")
            return fitz
        except ImportError as legacy_exc:
            raise RuntimeError("PDF extraction requires PyMuPDF: python -m pip install pymupdf") from legacy_exc


def parse_pages(value: str | None, count: int) -> list[int]:
    if value is None:
        return list(range(1, count + 1))
    selected = set()
    for part in value.split(","):
        if not re.fullmatch(r"\d+(?:-\d+)?", part.strip()):
            raise ValueError("--pages must use 1-based values such as 1,3-5")
        ends = [int(n) for n in part.strip().split("-")]
        start, stop = ends[0], ends[-1]
        if start < 1 or stop < start or stop > count:
            raise ValueError(f"Page range must be within 1..{count}")
        selected.update(range(start, stop + 1))
    return sorted(selected)


def render_pdf(path: Path, page_dir: Path, dpi: int, source_label: str,
               selected_pages: str | None = None, render: bool = True,
               columns: str = "auto", reading_order: str = "column", layout_config: dict | None = None) -> tuple[list[dict[str, object]], list[str]]:
    fitz = load_fitz()
    pages: list[dict[str, object]] = []
    warnings: list[str] = []
    with fitz.open(path) as document:
        for index in parse_pages(selected_pages, len(document)):
            page = document[index - 1]
            config = (layout_config or {}).get("pages", {}).get(str(index), {})
            layout = analyze_layout(page.get_text("rawdict"), list(page.rect), columns, reading_order, config)
            record = {"file_page": index, "locator": f"PDF 文件第 {index} 页", **layout}
            if render:
                image_name = f"page-{index:04d}.png"
                page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False).save(page_dir / image_name)
                record["image"] = f"pages/{image_name}"
            pages.append(record)
            if not record["text"].strip():
                warnings.append(f"PDF page {index} has no selectable text; inspect the page image directly.")
    warnings.append(f"Layout is unverified ({source_label}); confirm representative pages and all disputed glyphs against the original. Extraction is not OCR.")
    return pages, warnings


def convert_docx_to_pdf(path: Path, temp_dir: Path) -> Path | None:
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if office is None:
        return None
    result = subprocess.run(
        [office, "--headless", "--convert-to", "pdf", "--outdir", str(temp_dir), str(path)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    pdf_path = temp_dir / (path.stem + ".pdf")
    if result.returncode != 0 or not pdf_path.exists():
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"LibreOffice could not render the DOCX to PDF. {detail}")
    return pdf_path


def image_inputs(source: Path) -> list[Path]:
    if source.is_file():
        candidates = [source]
    else:
        candidates = [path for path in source.iterdir() if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS]
    return sorted(candidates, key=lambda path: natural_key(path.name))


def prepare(source: Path, output_dir: Path, dpi: int, *, selected_pages: str | None = None,
            render: bool = True, columns: str = "auto", reading_order: str = "column",
            layout_config: dict | None = None, source_id: str | None = None) -> dict[str, object]:
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    page_dir = output_dir / "pages"
    page_dir.mkdir()
    warnings: list[str] = []
    pages: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []
    source_type = source.suffix.casefold().lstrip(".") if source.is_file() else "image_directory"

    if source.is_dir() or source.suffix.casefold() in IMAGE_EXTENSIONS:
        files = image_inputs(source)
        if not files:
            raise ValueError("No supported image files found.")
        source_hashes = []
        for index, image in enumerate(files, start=1):
            target_name = f"page-{index:04d}{image.suffix.casefold()}"
            shutil.copy2(image, page_dir / target_name)
            file_page = index
            pages.append({"file_page": file_page, "locator": f"图片文件第 {file_page} 页 ({image.name})", "image": f"pages/{target_name}", "text": ""})
            source_hashes.append((image.name, sha256_file(image)))
        combined = "\n".join(f"{name}:{digest}" for name, digest in source_hashes).encode("utf-8")
        source_hash = hashlib.sha256(combined).hexdigest()
        warnings.append("Image inputs are indexed without OCR. The multimodal model must inspect each original-resolution page image.")
    elif source.suffix.casefold() == ".pdf":
        source_hash = sha256_file(source)
        pages, page_warnings = render_pdf(source, page_dir, dpi, "source PDF", selected_pages, render, columns, reading_order, layout_config)
        warnings.extend(page_warnings)
    elif source.suffix.casefold() == ".docx":
        source_hash = sha256_file(source)
        blocks, docx_warnings = extract_docx(source)
        warnings.extend(docx_warnings)
        with tempfile.TemporaryDirectory(prefix="proofreader-") as temp_name:
            pdf_path = convert_docx_to_pdf(source, Path(temp_name))
            if pdf_path is None:
                warnings.append("LibreOffice is unavailable; DOCX body text was extracted but page layout and page numbers were not rendered.")
            else:
                pages, page_warnings = render_pdf(pdf_path, page_dir, dpi, "temporary DOCX conversion", selected_pages, render, columns, reading_order, layout_config)
                warnings.extend(page_warnings)
    elif source.suffix.casefold() == ".txt":
        source_hash = sha256_file(source)
        text = source.read_text(encoding="utf-8-sig")
        for index, paragraph in enumerate((part.strip() for part in re.split(r"\n\s*\n", text)), start=1):
            if paragraph:
                blocks.append({"block_id": f"TXT-P{index:05d}", "locator": f"文本段落 {index}", "kind": "paragraph", "text": paragraph})
        warnings.append("Plain text has no stable page layout; use paragraph and question locators.")
    else:
        raise ValueError("Supported inputs are PDF, DOCX, TXT, image files, or a directory of images.")

    manifest: dict[str, object] = {
        "schema_version": 2,
        "source_id": source_id or source.name,
        "source_file": source.name,
        "source_type": source_type,
        "source_sha256": source_hash,
        "pages": pages,
        "blocks": blocks,
        "warnings": warnings,
        "selection": {"pages": selected_pages or "all", "rendered": render},
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="PDF, DOCX, TXT, one image, or a folder of images")
    parser.add_argument("--output-dir", type=Path, help="new output folder; existing folders are never overwritten")
    parser.add_argument("--dpi", type=int, default=200, help="PDF render resolution (default: 200)")
    parser.add_argument("--pages", help="PDF or converted DOCX pages, e.g. 1,3-5; original file_page is preserved")
    parser.add_argument("--no-render", action="store_true", help="extract geometry/text without rendering images")
    parser.add_argument("--columns", default="auto", help="auto or 1..8 equal-width columns; prefer layout-config for unequal columns")
    parser.add_argument("--reading-order", choices=("column", "row"), default="column")
    parser.add_argument("--layout-config", type=Path, help="JSON pages/regions/bbox/column_breaks overrides")
    parser.add_argument("--source-id", help="unique source identity for multi-file reports")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.exists():
        parser.error(f"Source does not exist: {source}")
    if not 100 <= args.dpi <= 400:
        parser.error("--dpi must be between 100 and 400")
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else source.parent / (source.stem + "_review_assets")
    try:
        if args.columns != "auto" and (not args.columns.isdigit() or not 1 <= int(args.columns) <= 8):
            raise ValueError("--columns must be auto or 1..8")
        if args.pages and source.suffix.casefold() not in (".pdf", ".docx"):
            raise ValueError("--pages applies only to PDF or converted DOCX")
        config = json.loads(args.layout_config.read_text(encoding="utf-8-sig")) if args.layout_config else None
        manifest = prepare(source, output_dir, args.dpi, selected_pages=args.pages, render=not args.no_render,
                           columns=args.columns, reading_order=args.reading_order, layout_config=config, source_id=args.source_id)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, zipfile.BadZipFile, ET.ParseError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"Prepared {len(manifest['pages'])} page record(s) and {len(manifest['blocks'])} text block(s).")
    print(f"Manifest: {output_dir / 'manifest.json'}")
    for warning in manifest["warnings"]:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PDF page rendering requires PyMuPDF. Install it with: python -m pip install pymupdf") from exc
    return fitz


def render_pdf(path: Path, page_dir: Path, dpi: int, source_label: str) -> tuple[list[dict[str, object]], list[str]]:
    fitz = load_fitz()
    pages: list[dict[str, object]] = []
    warnings: list[str] = []
    document = fitz.open(path)
    for index, page in enumerate(document, start=1):
        image_name = f"page-{index:04d}.png"
        image_path = page_dir / image_name
        pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        pixmap.save(image_path)
        text = page.get_text("text")
        pages.append({"file_page": index, "locator": f"PDF 文件第 {index} 页", "image": f"pages/{image_name}", "text": text})
        if not text.strip():
            warnings.append(f"PDF page {index} has no selectable text; inspect the page image directly.")
    warnings.append(f"PDF pages were rendered for visual review ({source_label}); extraction is not OCR and does not validate the content.")
    document.close()
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


def prepare(source: Path, output_dir: Path, dpi: int) -> dict[str, object]:
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
        pages, page_warnings = render_pdf(source, page_dir, dpi, "source PDF")
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
                pages, page_warnings = render_pdf(pdf_path, page_dir, dpi, "temporary DOCX conversion")
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
        "source_file": source.name,
        "source_type": source_type,
        "source_sha256": source_hash,
        "pages": pages,
        "blocks": blocks,
        "warnings": warnings,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="PDF, DOCX, TXT, one image, or a folder of images")
    parser.add_argument("--output-dir", type=Path, help="new output folder; existing folders are never overwritten")
    parser.add_argument("--dpi", type=int, default=200, help="PDF render resolution (default: 200)")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.exists():
        parser.error(f"Source does not exist: {source}")
    if not 100 <= args.dpi <= 400:
        parser.error("--dpi must be between 100 and 400")
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else source.parent / (source.stem + "_review_assets")
    try:
        manifest = prepare(source, output_dir, args.dpi)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, ET.ParseError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"Prepared {len(manifest['pages'])} page image(s) and {len(manifest['blocks'])} text block(s).")
    print(f"Manifest: {output_dir / 'manifest.json'}")
    for warning in manifest["warnings"]:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

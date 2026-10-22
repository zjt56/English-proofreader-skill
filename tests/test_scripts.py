from __future__ import annotations

import json
import importlib.util
import sys
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_report_docx
import check_answer_key
import prepare_review
import validate_review


def valid_report() -> dict:
    return {
        "title": "英语教辅编校问题清单",
        "metadata": {"source_sha256": "abc123"},
        "summary": {
            "issue_counts": {
                "明确差错": 1,
                "体例/一致性": 0,
                "编辑确认": 0,
                "材料不足": 0,
            }
        },
        "issues": [
            {
                "id": "E001",
                "status": "明确差错",
                "category": "语法/主谓一致",
                "severity": "中",
                "confidence": "高",
                "locations": [{"locator": "PDF 第 1 页，第 1 题", "file_page": 1, "question": "1", "quote": "She go to school."}],
                "explanation": "主谓不一致。",
                "basis": "一般现在时主谓一致。",
                "suggestion": "请编辑核对谓语形式。",
            }
        ],
        "coverage": {
            "three_passes_complete": True,
            "batches": [{
                "id": "B01",
                "scope": "PDF 第 1 页",
                "passes": {"first": "complete", "second": "complete", "third": "complete"},
                "proof_status": {
                    "first": {"inspection": "complete", "sent_to_typesetting": True, "red_check": "complete"},
                    "second": {"inspection": "complete", "sent_to_typesetting": True, "red_check": "complete"},
                    "third": {"inspection": "complete", "sent_to_typesetting": True, "red_check": "complete"},
                },
            }],
            "limitations": [],
        },
    }


class AnswerKeyTests(unittest.TestCase):
    def test_detects_duplicate_missing_orphan_and_invalid_option(self) -> None:
        result = check_answer_key.analyze({
            "questions": [
                {"id": "1", "options": ["A", "B"]},
                {"id": "1", "options": ["A", "B"]},
                {"id": "2"},
            ],
            "answers": [{"id": "1", "value": "C"}, {"id": "9", "value": "A"}],
        })
        codes = {item["code"] for item in result["errors"]}
        self.assertTrue({"duplicate_question_id", "missing_answer", "orphan_answer", "answer_not_in_options"}.issubset(codes))

    def test_accepts_aligned_keys(self) -> None:
        result = check_answer_key.analyze({
            "questions": [{"id": "1", "options": ["A", "B"]}, {"id": "2"}],
            "answers": [{"id": "1", "value": "B"}, {"id": "2", "value": "open response"}],
        })
        self.assertTrue(result["ok"])


class ReviewValidationTests(unittest.TestCase):
    def test_accepts_consistent_report_and_manifest(self) -> None:
        manifest = {
            "source_sha256": "abc123",
            "pages": [{"file_page": 1, "text": "She go to school."}],
            "blocks": [],
        }
        result = validate_review.validate(valid_report(), manifest)
        self.assertTrue(result["ok"], result["errors"])
        self.assertTrue(result["three_passes_supported_by_log"])
        self.assertEqual([], result["warnings"])

    def test_rejects_unsupported_three_pass_claim(self) -> None:
        report = valid_report()
        report["coverage"]["batches"][0]["passes"]["third"] = "not_done"
        result = validate_review.validate(report)
        self.assertFalse(result["ok"])
        self.assertTrue(any("three_passes_complete" in error for error in result["errors"]))

    def test_flags_quote_mismatch_as_warning(self) -> None:
        manifest = {"pages": [{"file_page": 1, "text": "She goes to school."}], "blocks": []}
        result = validate_review.validate(valid_report(), manifest)
        self.assertTrue(result["ok"])
        self.assertTrue(any("source quote" in warning for warning in result["warnings"]))


class FileToolTests(unittest.TestCase):
    def test_prepare_text_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            folder = Path(temp_name)
            source = folder / "sample.txt"
            source.write_text("Question one.\n\nQuestion two.", encoding="utf-8")
            output = folder / "assets"
            manifest = prepare_review.prepare(source, output, 200)
            self.assertEqual(2, len(manifest["blocks"]))
            self.assertEqual("Question one.", manifest["blocks"][0]["text"])
            self.assertTrue((output / "manifest.json").exists())

    def test_prepare_image_folder_with_natural_sort(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            folder = Path(temp_name)
            source = folder / "scans"
            source.mkdir()
            for name in ("10.png", "2.png", "cover.png"):
                (source / name).write_bytes(name.encode("ascii"))
            manifest = prepare_review.prepare(source, folder / "assets", 200)
            locators = [page["locator"] for page in manifest["pages"]]
            self.assertIn("2.png", locators[0])
            self.assertIn("10.png", locators[1])
            self.assertIn("cover.png", locators[2])

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF is optional")
    def test_prepare_pdf_renders_page_and_extracts_text(self) -> None:
        import fitz

        with tempfile.TemporaryDirectory() as temp_name:
            folder = Path(temp_name)
            source = folder / "sample.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Question one")
            document.save(source)
            document.close()
            manifest = prepare_review.prepare(source, folder / "assets", 120)
            self.assertEqual(1, len(manifest["pages"]))
            self.assertIn("Question one", manifest["pages"][0]["text"])
            self.assertTrue((folder / "assets" / manifest["pages"][0]["image"]).exists())

    def test_docx_extraction_keeps_stable_block_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            source = Path(temp_name) / "sample.docx"
            document_xml = b'''<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
            <w:p><w:r><w:t>Question one.</w:t></w:r></w:p>
            <w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
            </w:body></w:document>'''
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("word/document.xml", document_xml)
            blocks, warnings = prepare_review.extract_docx(source)
            self.assertEqual(["DOCX-P00001", "DOCX-T001-R0001"], [block["block_id"] for block in blocks])
            self.assertEqual("A\tB", blocks[1]["text"])
            self.assertEqual([], warnings)

    def test_builds_valid_docx_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "report.docx"
            report = valid_report()
            build_report_docx.build(report, output)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                document = ET.fromstring(archive.read("word/document.xml"))
                content_types = ET.fromstring(archive.read("[Content_Types].xml"))
                relationships = ET.fromstring(archive.read("_rels/.rels"))
            self.assertTrue(content_types.tag.endswith("Types"))
            self.assertTrue(relationships.tag.endswith("Relationships"))
            from docx import Document
            opened = Document(output)
            self.assertGreater(len(opened.paragraphs), 0)
            text = "".join(node.text or "" for node in document.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
            self.assertIn("英语教辅编校问题清单", text)
            self.assertIn("She go to school.", text)
            with self.assertRaises(FileExistsError):
                build_report_docx.build(report, output)

    def test_docx_cli_applies_threshold_and_always_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            folder = Path(temp_name)
            report_path = folder / "report.json"
            report_path.write_text(json.dumps(valid_report(), ensure_ascii=False), encoding="utf-8")
            output = folder / "report.docx"
            script = ROOT / "scripts" / "build_report_docx.py"
            skipped = subprocess.run([sys.executable, str(script), str(report_path), str(output)], capture_output=True, text=True)
            self.assertEqual(0, skipped.returncode, skipped.stderr)
            self.assertFalse(output.exists())
            generated = subprocess.run([sys.executable, str(script), str(report_path), str(output), "--always"], capture_output=True, text=True)
            self.assertEqual(0, generated.returncode, generated.stderr)
            self.assertTrue(output.exists())

    def test_docx_cli_generates_when_report_exceeds_default_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            folder = Path(temp_name)
            report = valid_report()
            report["summary"]["details"] = "长" * 3100
            report_path = folder / "long-report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            output = folder / "long-report.docx"
            script = ROOT / "scripts" / "build_report_docx.py"
            generated = subprocess.run([sys.executable, str(script), str(report_path), str(output)], capture_output=True, text=True)
            self.assertEqual(0, generated.returncode, generated.stderr)
            self.assertTrue(output.exists())
            character_count = int(generated.stdout.rsplit("(", 1)[1].split(" ", 1)[0])
            self.assertGreater(character_count, 3000)


if __name__ == "__main__":
    unittest.main()

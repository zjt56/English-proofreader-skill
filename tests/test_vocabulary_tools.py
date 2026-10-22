from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_report_docx
import check_sequence
import check_toc
import cross_check_index
import pdf_layout
import prepare_review
import validate_review


def sample():
    return json.loads((ROOT / "examples/structural-review-input.json").read_text(encoding="utf-8"))


def report():
    return json.loads((ROOT / "examples/single-delivery-report.json").read_text(encoding="utf-8"))


class StructureChecks(unittest.TestCase):
    def test_cli_json_is_utf8_even_if_windows_default_stream_is_gbk(self):
        env = dict(os.environ, PYTHONIOENCODING="gbk")
        for name in ("cross_check_index", "check_toc", "check_sequence", "validate_review"):
            sample_name = "single-delivery-report.json" if name == "validate_review" else "structural-review-input.json"
            process = subprocess.run([sys.executable, str(ROOT / "scripts" / (name + ".py")), str(ROOT / "examples" / sample_name)],
                                     capture_output=True, env=env)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertTrue(json.loads(process.stdout.decode("utf-8"))["ok"])

    def test_complete_small_manuscript_and_cross_day_reset(self):
        data = sample()
        for check in (check_sequence, check_toc, cross_check_index):
            with self.subTest(tool=check.__name__):
                self.assertTrue(check.analyze(data)["ok"])

    def test_exact_index_pages_and_reverse_coverage(self):
        data = sample()
        data["index_entries"][0]["target_page"] = 2
        data["index_entries"][1]["term"] = "leave ou"
        codes = {item["code"] for item in cross_check_index.analyze(data)["findings"]}
        self.assertEqual({"index_page_mismatch", "index_term_not_found", "body_term_missing_in_index"}, codes)

    def test_wrong_source_cannot_match_correct_page(self):
        data = sample()
        data["index_entries"][0]["target_source_id"] = "different-volume"
        codes = {item["code"] for item in cross_check_index.analyze(data)["findings"]}
        self.assertIn("index_term_not_found", codes)
        self.assertIn("body_term_missing_in_index", codes)

    def test_uncertain_extraction_is_not_a_pass(self):
        data = sample()
        data["extraction_verified"] = False
        result = cross_check_index.analyze(data)
        self.assertFalse(result["ok"])
        self.assertEqual("incomplete", result["status"])
        self.assertEqual([], result["findings"])

    def test_incomplete_count_is_not_a_pass(self):
        data = sample()
        data["expected_counts"]["body_entries"] = 1600
        result = cross_check_index.analyze(data)
        self.assertEqual("incomplete", result["status"])
        self.assertIn("extraction_count_mismatch", [f["code"] for f in result["findings"]])

    def test_empty_records_cannot_claim_whole_book_pass(self):
        data = sample()
        data["index_entries"] = []
        data["body_entries"] = []
        data["expected_counts"] = {}
        self.assertEqual("incomplete", cross_check_index.analyze(data)["status"])

    def test_pages_never_use_implicit_offset(self):
        data = sample()
        del data["page_basis"]
        with self.assertRaises(ValueError):
            cross_check_index.analyze(data)

    def test_case_and_hyphens_are_not_silently_changed(self):
        data = sample()
        data["index_entries"][0]["term"] = "Apple"
        self.assertFalse(cross_check_index.analyze(data)["ok"])
        data["ignore_case"] = True
        self.assertTrue(cross_check_index.analyze(data)["ok"])

    def test_same_group_duplicate_and_missing_are_detected(self):
        data = sample()
        data["sequence_entries"][1]["number"] = 1
        findings = check_sequence.analyze(data)["findings"]
        self.assertEqual({"duplicate_number", "missing_number"}, {f["code"] for f in findings})
        self.assertTrue(all(f["group"] == "Day01" for f in findings))

    def test_group_order_and_entire_missing_day(self):
        data = sample()
        data["sequence_entries"] = list(reversed(data["sequence_entries"][:2]))
        findings = check_sequence.analyze(data)["findings"]
        self.assertTrue(any(f["code"] == "number_order_mismatch" for f in findings))
        self.assertTrue(any(f["code"] == "missing_number" and f["group"] == "Day02" for f in findings))

    def test_toc_distinguishes_title_page_and_target_identity(self):
        data = sample()
        data["headings"][0]["printed_page"] = 9
        data["headings"][1]["title"] = "错标题"
        self.assertEqual({"toc_title_mismatch", "toc_page_mismatch"}, {f["code"] for f in check_toc.analyze(data)["findings"]})

    def test_two_wrong_fields_in_one_toc_entry_count_as_one_bad_entry(self):
        data = sample()
        data["headings"][0].update(title="错标题", printed_page=9)
        result = check_toc.analyze(data)
        self.assertEqual(2, len(result["findings"]))
        self.assertEqual(1, result["checks"][0]["mismatch_count"])

    def test_full_size_index_records(self):
        data = {"page_basis": "printed_page", "extraction_verified": True,
                "complete": {"index_entries": True, "body_entries": True},
                "expected_counts": {"index_entries": 1600, "body_entries": 1600},
                "index_entries": [], "body_entries": []}
        for i in range(1600):
            page = i // 40 + 1
            data["index_entries"].append({"term": f"word{i}", "target_source_id": "body", "target_page": page, "locator": f"I{i}"})
            data["body_entries"].append({"term": f"word{i}", "source_id": "body", "printed_page": page, "locator": f"B{i}"})
        self.assertTrue(cross_check_index.analyze(data)["ok"])


class DeliveryAndReportChecks(unittest.TestCase):
    def test_single_delivery_has_no_spurious_production_warnings(self):
        result = validate_review.validate(report())
        self.assertTrue(result["ok"], result)
        self.assertEqual([], result["warnings"])
        self.assertFalse(result["three_passes_supported_by_log"])

    def test_single_delivery_cannot_claim_three_production_proofs(self):
        data = report()
        data["coverage"]["three_passes_complete"] = True
        self.assertFalse(validate_review.validate(data)["ok"])

    def test_partial_semantic_review_cannot_claim_completed(self):
        data = report()
        data["coverage"]["batches"][0]["checks"]["semantic"] = "partial"
        self.assertFalse(validate_review.validate(data)["ok"])

    def test_three_internal_readings_are_required_unless_user_changes_requirement(self):
        data = report()
        data["coverage"]["batches"][0]["internal_readings"] = 2
        self.assertFalse(validate_review.validate(data)["ok"])
        data["coverage"]["required_internal_readings"] = 2
        self.assertFalse(validate_review.validate(data)["ok"])
        data["coverage"]["reading_requirement_basis"] = "本次委托明确只检查两遍（虚构测试）"
        self.assertTrue(validate_review.validate(data)["ok"])

    def test_malformed_optional_metadata_fails_cleanly(self):
        data = report()
        data["metadata"]["sources"] = "not an array"
        self.assertFalse(validate_review.validate(data)["ok"])
        data = report()
        data["coverage"]["batches"][0]["checks"]["semantic"] = "not_applicable"
        data["coverage"]["batches"][0]["not_applicable_reasons"] = None
        self.assertFalse(validate_review.validate(data)["ok"])

    def test_two_page_ones_do_not_cross_match(self):
        data = report()
        manifests = [{"source_id": "body", "pages": [{"file_page": 1, "text": "unrelated"}]},
                     {"source_id": "index", "pages": [{"file_page": 1, "text": "She like apples. He like bananas."}]}]
        data["metadata"]["sources"].append({"source_id": "index"})
        result = validate_review.validate(data, manifests)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(result["warnings"]))
        del data["issues"][0]["locations"][0]["source_id"]
        self.assertFalse(validate_review.validate(data, manifests)["ok"])

    def test_per_source_hash_mismatch_rejected(self):
        data = report()
        data["metadata"]["sources"][0]["source_sha256"] = "old"
        self.assertFalse(validate_review.validate(data, {"source_id": "body", "source_sha256": "new"})["ok"])

    def test_structural_zero_rows_cannot_be_called_pass(self):
        data = report()
        data["summary"]["structural_findings"][0]["checked_count"] = 0
        self.assertFalse(validate_review.validate(data)["ok"])

    def test_occurrence_counts_do_not_change_issue_counts(self):
        data = report()
        data["issues"][0]["occurrence_count"] = 3610
        result = validate_review.validate(data)
        self.assertTrue(result["ok"])
        self.assertEqual(1, result["computed_issue_counts"]["明确差错"])
        data["issues"][0]["occurrence_count"] = 1
        self.assertFalse(validate_review.validate(data)["ok"])

    def test_word_preserves_human_results_without_inventing_punctuation_edits(self):
        data = report()
        data["metadata"]["intake"] = {"internal_marker": "not-for-editor"}
        issue = data["issues"][0]
        issue["locations"][0]["quote"] = "A , B"
        del issue["locations"][0]["suggested"]
        issue["suggestion"] = "请确认这是选项分隔还是句内标点。"
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.docx"
            build_report_docx.build(data, output)
            with zipfile.ZipFile(output) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
            text = "\n".join(node.text or "" for node in root.iter(build_report_docx.W + "t"))
            for expected in ("影响范围", "出现次数：2", "已核 4 条", "apple", issue["suggestion"]):
                self.assertIn(expected, text)
            for absent in ("not-for-editor", "三校尚未", "标点前多余空格", "建议改为：A, B"):
                self.assertNotIn(absent, text)

    def test_location_threshold_triggers_word_even_for_short_report(self):
        data = report()
        data["issues"][0]["occurrence_count"] = 11
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "report.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            output = folder / "report.docx"
            process = subprocess.run([sys.executable, str(ROOT / "scripts/build_report_docx.py"), str(path), str(output)], capture_output=True)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertTrue(output.exists())

    def test_word_rejects_invalid_xml_and_legacy_doc_extension_before_writing(self):
        data = report()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.docx"
            data["title"] = "bad\x00title"
            with self.assertRaises(ValueError):
                build_report_docx.build(data, output)
            self.assertFalse(output.exists())
            with self.assertRaises(ValueError):
                build_report_docx.build(report(), Path(folder) / "report.doc")


@unittest.skipUnless(importlib.util.find_spec("pymupdf") or importlib.util.find_spec("fitz"), "PyMuPDF optional")
class PdfIntegrationChecks(unittest.TestCase):
    def test_pua_remains_a_font_diagnostic_and_is_not_replaced_globally(self):
        pua = "\U00100c79"
        raw = {"blocks": [{"type": 0, "lines": [{"dir": (1, 0), "spans": [{"font": "Subset-IPA", "size": 10,
               "chars": [{"c": ch, "bbox": [20+i*5, 20, 25+i*5, 35]} for i,ch in enumerate("/"+pua+"I/")]}]}]}]}
        layout = pdf_layout.analyze_layout(raw, [0,0,600,800])
        self.assertIn(pua+"I", layout["text"])
        self.assertEqual("font_mapping_required", layout["encoding_diagnostics"][0]["kind"])
        self.assertEqual("Subset-IPA", layout["encoding_diagnostics"][0]["font"])

    def test_five_columns_and_selected_original_page_number(self):
        mu = prepare_review.load_fitz()
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "five-columns.pdf"
            with mu.open() as doc:
                doc.new_page(width=620, height=800)
                page = doc.new_page(width=620, height=800)
                for col in range(5):
                    for row in range(20):
                        page.insert_text((20 + col * 120, 80 + row * 25), f"term{col}_{row} / {row+1}", fontsize=8)
                doc.save(path)
            assets = prepare_review.prepare(path, folder / "assets", 120, selected_pages="2", render=False)
            page = assets["pages"][0]
            self.assertEqual(2, page["file_page"])
            self.assertEqual(5, page["column_count"])
            self.assertNotIn("image", page)
            self.assertIn("bbox", page["lines"][0])
            self.assertTrue(all(line["column"] == 1 for line in page["lines"][:20]))
            self.assertEqual(100, len(page["lines"]))

    def test_two_vertical_regions_keep_section_reading_order(self):
        mu = prepare_review.load_fitz()
        with mu.open() as doc:
            page = doc.new_page(width=600, height=800)
            for x, y, text in [(30,80,"day1-left"),(330,80,"day1-right"),(30,480,"day2-left"),(330,480,"day2-right")]:
                page.insert_text((x,y),text)
            config = {"regions": [{"bbox": [0,0,600,400], "column_breaks": [300]}, {"bbox": [0,400,600,800], "column_breaks": [300]}]}
            layout = pdf_layout.analyze_layout(page.get_text("rawdict"),list(page.rect),config=config)
            self.assertEqual(["day1-left","day1-right","day2-left","day2-right"], [line["text"] for line in layout["lines"]])
            self.assertEqual([], layout["unassigned_lines"])


if __name__ == "__main__":
    unittest.main()

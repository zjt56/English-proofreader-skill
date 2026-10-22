from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_consistency


def sample():
    return json.loads((ROOT / "examples/consistency-input.json").read_text(encoding="utf-8"))


class ConsistencyChecks(unittest.TestCase):
    def test_explicit_target_preserves_locations_and_excludes_teaching_exceptions(self):
        result = check_consistency.analyze(sample())
        self.assertEqual("mismatch", result["status"])
        self.assertEqual(2, result["excluded_count"])
        self.assertEqual(4, result["checked_entries"])
        self.assertEqual(1, len(result["findings"]))
        finding = result["findings"][0]
        self.assertEqual("preferred_form_mismatch", finding["code"])
        self.assertEqual(2, finding["locations"][0]["file_page"])
        self.assertEqual("体例候选", finding["status"])

    def test_mixed_forms_without_target_do_not_pick_the_majority(self):
        data = sample()
        del data["rules"][0]["preferred"]
        data["consistency_entries"].append(deepcopy(data["consistency_entries"][1]))
        data["expected_counts"]["consistency_entries"] += 1
        finding = check_consistency.analyze(data)["findings"][0]
        self.assertEqual("mixed_forms", finding["code"])
        self.assertEqual("编辑确认", finding["status"])
        self.assertNotIn("preferred", finding)
        self.assertEqual({"colour": 1, "color": 2}, finding["forms"])

    def test_different_scopes_and_valid_consistent_forms_do_not_create_candidates(self):
        data = sample()
        data["consistency_entries"][1].update(form="colour", quote="The colour is red.")
        result = check_consistency.analyze(data)
        self.assertTrue(result["ok"])
        self.assertEqual([], result["findings"])
        self.assertEqual(3, result["checks"][0]["checked_count"])

    def test_unverified_incomplete_and_empty_inputs_cannot_pass(self):
        for field in ("unverified", "incomplete", "empty", "wrong_count", "only_excluded"):
            data = sample()
            if field == "unverified":
                data["extraction_verified"] = False
            elif field == "incomplete":
                data["complete"]["consistency_entries"] = False
            elif field == "empty":
                data["consistency_entries"] = []
            elif field == "wrong_count":
                data["expected_counts"]["consistency_entries"] = 100
            else:
                data["consistency_entries"] = data["consistency_entries"][2:4]
                data["expected_counts"]["consistency_entries"] = 2
            with self.subTest(field=field):
                result = check_consistency.analyze(data)
                self.assertFalse(result["ok"])
                self.assertEqual("incomplete", result["status"])

    def test_bad_rule_role_or_unsupported_source_quote_is_rejected(self):
        changes = (
            lambda d: d.update(complete=[]),
            lambda d: d.update(expected_counts=None),
            lambda d: d["rules"][0].pop("basis"),
            lambda d: d["rules"][0].update(preferred="COLORS"),
            lambda d: d["rules"][0].update(forms=[" ", "colour"]),
            lambda d: d["consistency_entries"][0].update(role="distractor_typo"),
            lambda d: d["consistency_entries"][0].update(quote="Unrelated sentence."),
            lambda d: d["consistency_entries"][0].update(rule_id="missing"),
        )
        for change in changes:
            data = sample()
            change(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                check_consistency.analyze(data)

    def test_punctuation_differences_are_not_normalized_away(self):
        data = sample()
        data["consistency_entries"][5]["scope"] = "Unit 1 单选"
        result = check_consistency.analyze(data)
        self.assertEqual(2, len(result["findings"]))
        self.assertEqual({"1.": 1, "1、": 1}, result["findings"][1]["forms"])

    def test_cli_writes_utf8_candidates_without_overwriting_existing_results(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "findings.json"
            command = [sys.executable, str(ROOT / "scripts/check_consistency.py"),
                       str(ROOT / "examples/consistency-input.json"), "--output", str(output)]
            env = dict(os.environ, PYTHONIOENCODING="gbk")
            run = subprocess.run(command, capture_output=True, env=env)
            self.assertEqual(1, run.returncode)
            self.assertEqual("mismatch", json.loads(run.stdout.decode("utf-8"))["status"])
            self.assertEqual("体例候选", json.loads(output.read_text(encoding="utf-8"))["findings"][0]["status"])
            previous = output.read_bytes()
            retry = subprocess.run(command, capture_output=True, env=env)
            self.assertEqual(2, retry.returncode)
            self.assertEqual(previous, output.read_bytes())


if __name__ == "__main__":
    unittest.main()

"""Shared JSON I/O and conservative normalization for structural checks."""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path
from runtime_common import configure_stdio


def key(value, ignore_case=False):
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value))).strip()
    return text.casefold() if ignore_case else text


def require_rows(data, name, fields):
    rows = data.get(name)
    if not isinstance(rows, list):
        raise ValueError(f"{name} must be an array")
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or any(field not in row or row[field] in (None, "") for field in fields):
            raise ValueError(f"{name}[{i}] needs {', '.join(fields)}")
    return rows


def finish(data, required_sets, findings, checks):
    verified = data.get("extraction_verified") is True
    complete = verified and all(data.get("complete", {}).get(name) is True for name in required_sets)
    for name in required_sets:
        if not data[name]:
            complete = False
            findings.append({"code": "empty_dataset", "set": name, "status": "材料不足"})
        expected = data.get("expected_counts", {}).get(name)
        if expected is not None and (type(expected) is not int or expected < 0):
            raise ValueError(f"expected_counts.{name} must be a nonnegative integer")
        if expected is not None and expected != len(data[name]):
            complete = False
            findings.append({"code": "extraction_count_mismatch", "set": name,
                             "expected": expected, "actual": len(data[name]), "status": "材料不足"})
    for finding in findings:
        finding.setdefault("status", "结构候选" if complete else "材料不足/抽取待核")
    for check in checks:
        check["status"] = "incomplete" if not complete else ("mismatch" if check.get("mismatch_count", 0) else "pass")
    return {"ok": complete and not findings,
            "status": "incomplete" if not complete else ("mismatch" if findings else "pass"),
            "findings": findings, "checks": checks,
            "note": "程序核对结构，不判断语言正确；候选须回原稿确认。"}


def run_cli(analyze, description):
    configure_stdio()
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", type=Path, help="verified structural records JSON")
    parser.add_argument("--output", type=Path, help="new output JSON, never overwrite")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Input must be an object")
        result = analyze(data)
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
        print(text, end="")
        return 0 if result["ok"] else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Error: {exc}\n")

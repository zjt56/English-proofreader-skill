#!/usr/bin/env python3
"""Check structural alignment between question IDs, options, and answer-key IDs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def normalized_id(value: Any) -> str:
    return str(value).strip()


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    questions = data.get("questions")
    answers = data.get("answers")
    if not isinstance(questions, list) or not isinstance(answers, list):
        return {"ok": False, "errors": [{"code": "invalid_schema", "message": "questions and answers must be arrays"}]}

    question_ids: list[str] = []
    answer_ids: list[str] = []
    question_by_id: dict[str, dict[str, Any]] = {}
    answer_by_id: dict[str, dict[str, Any]] = {}

    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict) or not normalized_id(item.get("id", "")):
            errors.append({"code": "missing_question_id", "message": f"questions[{index - 1}] has no usable id"})
            continue
        item_id = normalized_id(item["id"])
        question_ids.append(item_id)
        question_by_id.setdefault(item_id, item)

    for index, item in enumerate(answers, start=1):
        if not isinstance(item, dict) or not normalized_id(item.get("id", "")):
            errors.append({"code": "missing_answer_id", "message": f"answers[{index - 1}] has no usable id"})
            continue
        item_id = normalized_id(item["id"])
        answer_ids.append(item_id)
        answer_by_id.setdefault(item_id, item)

    question_counts = Counter(question_ids)
    answer_counts = Counter(answer_ids)
    for item_id, count in sorted(question_counts.items()):
        if count > 1:
            errors.append({"code": "duplicate_question_id", "message": f"Question id {item_id!r} occurs {count} times"})
    for item_id, count in sorted(answer_counts.items()):
        if count > 1:
            errors.append({"code": "duplicate_answer_id", "message": f"Answer id {item_id!r} occurs {count} times"})
    for item_id in sorted(question_counts.keys() - answer_counts.keys()):
        errors.append({"code": "missing_answer", "message": f"Question {item_id!r} has no answer-key entry"})
    for item_id in sorted(answer_counts.keys() - question_counts.keys()):
        errors.append({"code": "orphan_answer", "message": f"Answer id {item_id!r} has no matching question"})

    for item_id in sorted(question_counts.keys() & answer_counts.keys()):
        options = question_by_id[item_id].get("options")
        if not isinstance(options, list) or not options:
            continue
        allowed = {str(option).strip().casefold() for option in options}
        value = answer_by_id[item_id].get("value")
        values = value if isinstance(value, list) else [value]
        for answer_value in values:
            normalized = str(answer_value).strip().casefold()
            if normalized not in allowed:
                errors.append({"code": "answer_not_in_options", "message": f"Answer {answer_value!r} for question {item_id!r} is not one of its listed option labels"})

    return {"ok": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("answer_map", type=Path, help="JSON with questions[] and answers[]")
    args = parser.parse_args()
    try:
        data = json.loads(args.answer_map.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("top-level JSON value must be an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "errors": [{"code": "input_error", "message": str(exc)}]}, ensure_ascii=False, indent=2))
        return 2
    result = analyze(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

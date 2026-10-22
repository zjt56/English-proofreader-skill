#!/usr/bin/env python3
"""Validate report structure, issue counts, coverage claims, and source quotes."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

STATUSES = ("明确差错", "体例/一致性", "编辑确认", "材料不足")
PASS_NAMES = ("first", "second", "third")
PASS_STATES = ("complete", "partial", "not_done")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def validate(data: dict[str, Any], manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    issues = data.get("issues")
    summary = data.get("summary")
    coverage = data.get("coverage")
    if not isinstance(issues, list):
        issues = []
        errors.append("issues must be an array")
    if not isinstance(summary, dict):
        summary = {}
        errors.append("summary must be an object")
    if not isinstance(coverage, dict):
        coverage = {}
        errors.append("coverage must be an object")

    counts: Counter[str] = Counter()
    seen_ids: set[str] = set()
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            errors.append(f"issues[{index - 1}] must be an object")
            continue
        issue_id = str(issue.get("id", "")).strip()
        if not issue_id:
            errors.append(f"issues[{index - 1}] has no id")
        elif issue_id in seen_ids:
            errors.append(f"duplicate issue id: {issue_id}")
        else:
            seen_ids.add(issue_id)
        status = issue.get("status")
        if status not in STATUSES:
            errors.append(f"{issue_id or 'issue'} has invalid status: {status!r}")
        else:
            counts[status] += 1
        for field in ("category", "severity", "confidence", "explanation", "basis", "suggestion"):
            if not str(issue.get(field, "")).strip():
                errors.append(f"{issue_id or 'issue'} is missing {field}")
        locations = issue.get("locations")
        if not isinstance(locations, list) or not locations:
            errors.append(f"{issue_id or 'issue'} must have at least one location")
            continue
        for location in locations:
            if not isinstance(location, dict) or not str(location.get("locator", "")).strip():
                errors.append(f"{issue_id or 'issue'} has a location without locator")
                continue
            quote = str(location.get("quote", "")).strip()
            if status != "材料不足" and not quote:
                errors.append(f"{issue_id or 'issue'} needs a source quote")
            if manifest is not None and quote:
                page = location.get("file_page")
                block_id = location.get("block_id")
                source_blocks = list(manifest.get("pages", [])) + list(manifest.get("blocks", []))
                candidates = [
                    block for block in source_blocks
                    if (page is not None and block.get("file_page") == page)
                    or (block_id and block.get("block_id") == block_id)
                ]
                if not candidates:
                    warnings.append(f"{issue_id}: locator {location.get('locator')!r} was not matched to a manifest page/block")
                elif not any(normalize_text(quote) in normalize_text(str(block.get("text", ""))) for block in candidates):
                    warnings.append(f"{issue_id}: source quote was not found verbatim after whitespace/Unicode normalization; visually verify it")

    expected_counts = {status: counts[status] for status in STATUSES}
    stated_counts = summary.get("issue_counts")
    if not isinstance(stated_counts, dict):
        errors.append("summary.issue_counts must list all four status counts")
    else:
        for status in STATUSES:
            if stated_counts.get(status) != expected_counts[status]:
                errors.append(f"summary count for {status!r} is {stated_counts.get(status)!r}; expected {expected_counts[status]}")

    batches = coverage.get("batches")
    if not isinstance(batches, list) or not batches:
        errors.append("coverage.batches must list each reviewed batch")
        batches = []
    all_complete = True
    for index, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict) or not str(batch.get("id", "")).strip() or not str(batch.get("scope", "")).strip():
            errors.append(f"coverage.batches[{index - 1}] needs id and scope")
            all_complete = False
            continue
        passes = batch.get("passes")
        if not isinstance(passes, dict):
            errors.append(f"batch {batch['id']} needs first/second/third pass states")
            all_complete = False
            continue
        for pass_name in PASS_NAMES:
            state = passes.get(pass_name)
            if state not in PASS_STATES:
                errors.append(f"batch {batch['id']} has invalid {pass_name} state: {state!r}")
                all_complete = False
            elif state != "complete":
                all_complete = False

        proof_status = batch.get("proof_status")
        if any(passes.get(name) == "complete" for name in PASS_NAMES):
            if not isinstance(proof_status, dict):
                message = f"batch {batch['id']} needs proof_status for inspection, typesetting, and red check"
                if coverage.get("three_passes_complete") is True:
                    errors.append(message)
                else:
                    warnings.append(message)
            else:
                for pass_name in PASS_NAMES:
                    if passes.get(pass_name) != "complete":
                        continue
                    proof = proof_status.get(pass_name)
                    if not isinstance(proof, dict):
                        message = f"batch {batch['id']} needs proof_status.{pass_name}"
                        if coverage.get("three_passes_complete") is True:
                            errors.append(message)
                        else:
                            warnings.append(message)
                        continue
                    if proof.get("inspection") != "complete":
                        message = f"batch {batch['id']} {pass_name} inspection is not complete"
                        (errors if coverage.get("three_passes_complete") is True else warnings).append(message)
                    if proof.get("sent_to_typesetting") is not True:
                        message = f"batch {batch['id']} {pass_name} was not sent to typesetting"
                        (errors if coverage.get("three_passes_complete") is True else warnings).append(message)
                    if proof.get("red_check") != "complete":
                        message = f"batch {batch['id']} {pass_name} red check is not complete"
                        (errors if coverage.get("three_passes_complete") is True else warnings).append(message)

    limitations = coverage.get("limitations", [])
    if not isinstance(limitations, list):
        errors.append("coverage.limitations must be an array")
        limitations = ["invalid limitations field"]
    if coverage.get("three_passes_complete") is True and (not all_complete or limitations):
        errors.append("three_passes_complete is true, but a pass is incomplete or a limitation is listed")

    if manifest is not None:
        source_hash = data.get("metadata", {}).get("source_sha256") if isinstance(data.get("metadata"), dict) else None
        manifest_hash = manifest.get("source_sha256")
        if source_hash and manifest_hash and source_hash != manifest_hash:
            errors.append("report source_sha256 does not match manifest source_sha256")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "computed_issue_counts": expected_counts,
        "three_passes_supported_by_log": all_complete and not limitations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="structured report JSON")
    parser.add_argument("--manifest", type=Path, help="optional source manifest JSON from prepare_review.py")
    args = parser.parse_args()
    try:
        report_data = json.loads(args.report.read_text(encoding="utf-8-sig"))
        if not isinstance(report_data, dict):
            raise ValueError("report JSON top-level value must be an object")
        manifest_data = None
        if args.manifest:
            manifest_data = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
            if not isinstance(manifest_data, dict):
                raise ValueError("manifest JSON top-level value must be an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    result = validate(report_data, manifest_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

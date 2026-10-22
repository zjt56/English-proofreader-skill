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
from runtime_common import configure_stdio

STATUSES = ("明确差错", "体例/一致性", "编辑确认", "材料不足")
PASS_NAMES = ("first", "second", "third")
PASS_STATES = ("complete", "partial", "not_done")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def validate(data: dict[str, Any], manifest: dict[str, Any] | list[dict[str, Any]] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifests = [] if manifest is None else (manifest if isinstance(manifest, list) else [manifest])
    sources = {}
    for item in manifests:
        identity = item.get("source_id") or item.get("source_file")
        if len(manifests) > 1 and not identity:
            errors.append("each manifest needs source_id for multi-file validation")
        identity = identity or "__single__"
        if identity in sources:
            errors.append(f"duplicate manifest source_id: {identity}")
        sources[identity] = item
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
            if not isinstance(issue.get(field), str) or not issue[field].strip():
                errors.append(f"{issue_id or 'issue'} is missing {field}")
        if "scope" in issue and (not isinstance(issue["scope"], dict) or not str(issue["scope"].get("description", "")).strip()):
            errors.append(f"{issue_id}: scope needs a description")
        occurrence_count = issue.get("occurrence_count")
        if occurrence_count is not None:
            if type(occurrence_count) is not int or occurrence_count < 1:
                errors.append(f"{issue_id}: occurrence_count must be a positive integer")
            if issue.get("count_status") not in ("exact", "estimated") or not issue.get("count_basis"):
                errors.append(f"{issue_id}: occurrence_count needs count_status exact/estimated and count_basis")
        locations = issue.get("locations")
        if not isinstance(locations, list) or not locations:
            errors.append(f"{issue_id or 'issue'} must have at least one location")
            continue
        if type(occurrence_count) is int and occurrence_count < len(locations):
            errors.append(f"{issue_id}: occurrence_count is smaller than the number of sample locations")
        for location in locations:
            if not isinstance(location, dict) or not str(location.get("locator", "")).strip():
                errors.append(f"{issue_id or 'issue'} has a location without locator")
                continue
            quote = str(location.get("quote", "")).strip()
            if status != "材料不足" and not quote:
                errors.append(f"{issue_id or 'issue'} needs a source quote")
            if manifests and quote:
                source_id = location.get("source_id")
                if len(manifests) > 1 and not source_id:
                    errors.append(f"{issue_id}: location needs source_id when using multiple manifests")
                    continue
                if source_id and source_id not in sources:
                    errors.append(f"{issue_id}: unknown location source_id: {source_id}")
                    continue
                source_manifest = sources[source_id] if source_id else manifests[0]
                page = location.get("file_page")
                block_id = location.get("block_id")
                source_blocks = list(source_manifest.get("pages", [])) + list(source_manifest.get("blocks", []))
                candidates = [
                    block for block in source_blocks
                    if (page is not None or block_id)
                    and (page is None or block.get("file_page") == page)
                    and (not block_id or block.get("block_id") == block_id)
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

    structural = summary.get("structural_findings", [])
    if not isinstance(structural, list):
        errors.append("summary.structural_findings must be an array")
    else:
        for finding in structural:
            if not isinstance(finding, dict) or not all(finding.get(key) for key in ("check", "status", "scope", "evidence")):
                errors.append("structural finding needs check, status, scope and evidence")
                continue
            checked, mismatch = finding.get("checked_count"), finding.get("mismatch_count")
            if type(checked) is not int or type(mismatch) is not int or not 0 <= mismatch <= checked:
                errors.append("structural finding needs nonnegative checked_count and mismatch_count <= checked_count")
            if finding["status"] not in ("pass", "mismatch", "incomplete"):
                errors.append("structural finding status must be pass/mismatch/incomplete")
            if finding["status"] == "pass" and (mismatch != 0 or checked == 0):
                errors.append("structural finding pass requires a nonzero checked_count and zero mismatches")

    batches = coverage.get("batches")
    if not isinstance(batches, list) or not batches:
        errors.append("coverage.batches must list each reviewed batch")
        batches = []
    mode = coverage.get("mode", "mudu")  # legacy reports retain their original contract
    if mode not in ("single_delivery", "mudu"):
        errors.append("coverage.mode must be single_delivery or mudu")
    required_readings = coverage.get("required_internal_readings", 3)
    if mode == "single_delivery":
        if type(required_readings) is not int or required_readings < 1:
            errors.append("required_internal_readings must be a positive integer")
            required_readings = 3
        if required_readings != 3 and not coverage.get("reading_requirement_basis"):
            errors.append("adjusting internal reading count needs reading_requirement_basis recording the user's request")
    all_complete = bool(batches)
    proof_complete = bool(batches)
    for index, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict) or not str(batch.get("id", "")).strip() or not str(batch.get("scope", "")).strip():
            errors.append(f"coverage.batches[{index - 1}] needs id and scope")
            all_complete = False
            continue
        if mode == "single_delivery":
            readings = batch.get("internal_readings", 0)
            if type(readings) is not int or readings < 0:
                errors.append(f"batch {batch['id']} internal_readings must be a nonnegative integer")
                readings = 0
            if readings < required_readings:
                all_complete = False
            checks = batch.get("checks", {})
            if not isinstance(checks, dict):
                checks = {}
            for name in ("structural", "semantic", "verification"):
                state = checks.get(name)
                if state not in (*PASS_STATES, "not_applicable"):
                    errors.append(f"batch {batch['id']} needs valid checks.{name}")
                if state not in ("complete", "not_applicable"):
                    all_complete = False
                if state == "not_applicable":
                    reasons = batch.get("not_applicable_reasons")
                    if not isinstance(reasons, dict) or not reasons.get(name):
                        errors.append(f"batch {batch['id']} needs a reason for not_applicable {name}")
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
                proof_complete = False
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
                        proof_complete = False
                        message = f"batch {batch['id']} needs proof_status.{pass_name}"
                        if coverage.get("three_passes_complete") is True:
                            errors.append(message)
                        else:
                            warnings.append(message)
                        continue
                    if proof.get("inspection") != "complete":
                        proof_complete = False
                        message = f"batch {batch['id']} {pass_name} inspection is not complete"
                        (errors if coverage.get("three_passes_complete") is True else warnings).append(message)
                    if proof.get("sent_to_typesetting") is not True:
                        proof_complete = False
                        message = f"batch {batch['id']} {pass_name} was not sent to typesetting"
                        (errors if coverage.get("three_passes_complete") is True else warnings).append(message)
                    if proof.get("red_check") != "complete":
                        proof_complete = False
                        message = f"batch {batch['id']} {pass_name} red check is not complete"
                        (errors if coverage.get("three_passes_complete") is True else warnings).append(message)

    limitations = coverage.get("limitations", [])
    if not isinstance(limitations, list):
        errors.append("coverage.limitations must be an array")
        limitations = ["invalid limitations field"]
    if coverage.get("three_passes_complete") is True and (not all_complete or limitations):
        errors.append("three_passes_complete is true, but a pass is incomplete or a limitation is listed")
    if mode == "single_delivery" and coverage.get("three_passes_complete") is True:
        errors.append("single_delivery cannot claim three_passes_complete")
    if coverage.get("completed") is True and (not all_complete or limitations):
        errors.append("coverage.completed requires all applicable checks complete with no material limitation")

    metadata = data.get("metadata", {})
    if isinstance(metadata, dict):
        if len(manifests) == 1:
            source_hash = metadata.get("source_sha256")
            manifest_hash = manifests[0].get("source_sha256")
            if source_hash and manifest_hash and source_hash != manifest_hash:
                errors.append("report source_sha256 does not match manifest source_sha256")
        metadata_sources = metadata.get("sources", [])
        if not isinstance(metadata_sources, list):
            errors.append("metadata.sources must be an array")
            metadata_sources = []
        for source in metadata_sources:
            if not isinstance(source, dict) or not isinstance(source.get("source_id"), str):
                errors.append("each metadata.sources entry needs a string source_id")
                continue
            identity = source.get("source_id")
            if manifests and identity not in sources:
                errors.append(f"metadata.sources references unknown source_id: {identity}")
            elif identity in sources and source.get("source_sha256") and source["source_sha256"] != sources[identity].get("source_sha256"):
                errors.append(f"source_sha256 mismatch for {identity}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "computed_issue_counts": expected_counts,
        "three_passes_supported_by_log": mode == "mudu" and all_complete and proof_complete and not limitations and not errors,
    }


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="structured report JSON")
    parser.add_argument("--manifest", type=Path, action="append", help="repeat for each source manifest")
    args = parser.parse_args()
    try:
        report_data = json.loads(args.report.read_text(encoding="utf-8-sig"))
        if not isinstance(report_data, dict):
            raise ValueError("report JSON top-level value must be an object")
        manifest_data = []
        for path in args.manifest or []:
            item = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(item, dict):
                raise ValueError("manifest JSON top-level value must be an object")
            manifest_data.append(item)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    result = validate(report_data, manifest_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

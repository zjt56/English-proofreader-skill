#!/usr/bin/env python3
"""Find terminology/style candidates in verified, explicitly grouped records."""
from collections import Counter, defaultdict
import unicodedata

from structure_common import finish, require_rows, run_cli

ACTIVE_ROLES = {"prose", "title", "label", "definition", "explanation", "term"}
EXCLUDED_ROLES = {"quotation", "proper_name", "distractor", "error_example", "answer_blank", "code"}


def form_key(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Forms must be nonempty strings, not answer spaces")
    return unicodedata.normalize("NFC", value)


def analyze(data):
    if not isinstance(data.get("complete", {}), dict) or not isinstance(data.get("expected_counts", {}), dict):
        raise ValueError("complete and expected_counts must be objects")
    rules = require_rows(data, "rules", ("id", "label", "forms"))
    rows = require_rows(data, "consistency_entries",
                        ("rule_id", "scope", "form", "role", "source_id", "locator", "quote"))
    by_id, groups, findings = {}, defaultdict(list), []
    for rule in rules:
        if not isinstance(rule["id"], str) or not rule["id"].strip():
            raise ValueError("Rule id must be a nonempty string")
        if not isinstance(rule["label"], str) or not rule["label"].strip():
            raise ValueError("Rule label must be a nonempty string")
        if rule["id"] in by_id:
            raise ValueError("Duplicate rule id")
        forms = rule["forms"]
        if not isinstance(forms, list) or len(forms) < 2:
            raise ValueError("Each rule needs at least two explicit forms")
        normalized = [form_key(value) for value in forms]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Rule forms must be distinct after NFC normalization")
        preferred = rule.get("preferred")
        if preferred is not None:
            if form_key(preferred) not in normalized:
                raise ValueError("Preferred form must belong to rule forms")
            if not isinstance(rule.get("basis"), str) or not rule["basis"].strip():
                raise ValueError("Preferred form needs an explicit editorial basis")
        by_id[rule["id"]] = (rule, set(normalized))

    excluded = 0
    for row in rows:
        if not all(isinstance(row[name], str) and row[name].strip()
                   for name in ("rule_id", "scope", "role", "source_id", "locator", "quote")):
            raise ValueError("Record IDs, scope, role, location and quote must be nonempty strings")
        if row["rule_id"] not in by_id:
            raise ValueError("Unknown consistency rule")
        _, forms = by_id[row["rule_id"]]
        current = form_key(row["form"])
        if current not in forms:
            raise ValueError("Record form does not belong to its rule")
        if current not in unicodedata.normalize("NFC", row["quote"]):
            raise ValueError("Record form must occur in its quoted source text")
        if row["role"] in EXCLUDED_ROLES:
            excluded += 1
            continue
        if row["role"] not in ACTIVE_ROLES:
            raise ValueError("Unknown text role; resolve its manuscript function first")
        groups[(row["rule_id"], row["scope"])].append(row)

    inventory, mismatches = [], 0
    for (rule_id, scope), members in groups.items():
        rule, _ = by_id[rule_id]
        counts = Counter(form_key(row["form"]) for row in members)
        inventory.append({"rule_id": rule_id, "scope": scope, "forms": dict(counts)})
        preferred = rule.get("preferred")
        if preferred is not None:
            affected = [row for row in members if form_key(row["form"]) != form_key(preferred)]
            if not affected:
                continue
            finding = {"code": "preferred_form_mismatch", "status": "体例候选",
                       "preferred": preferred, "basis": rule["basis"], "locations": affected,
                       "suggestion": f"建议按已确认体例统一为 {preferred}；回原稿核实功能和例外后由编辑决定。"}
        elif len(counts) > 1:
            finding = {"code": "mixed_forms", "status": "编辑确认", "locations": members,
                       "suggestion": "请编辑确认本范围的统一写法；不按出现频次自动选定。"}
        else:
            continue
        mismatches += 1
        findings.append({**finding, "rule_id": rule_id, "label": rule["label"],
                         "scope": scope, "forms": dict(counts)})

    if rows and not groups:
        findings.append({"code": "no_applicable_records", "status": "材料不足"})
    result = finish(data, ("rules", "consistency_entries"), findings,
                    [{"check": "显式范围内术语与体例一致性", "checked_count": len(groups),
                      "mismatch_count": mismatches}])
    if rows and not groups:
        result["ok"], result["status"] = False, "incomplete"
        result["checks"][0]["status"] = "incomplete"
    if result["status"] == "incomplete":
        for finding in result["findings"]:
            finding["status"] = "材料不足/抽取待核"
    result.update(inventory=inventory, checked_entries=sum(len(members) for members in groups.values()),
                  excluded_count=excluded,
                  note="只比较已整理写法，不发现全部拼写/语法错误；候选须回原稿复核，不自动修改或认定出版差错。")
    return result


if __name__ == "__main__":
    raise SystemExit(run_cli(analyze, __doc__))

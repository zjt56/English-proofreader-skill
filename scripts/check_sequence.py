#!/usr/bin/env python3
"""Check numbering within explicit day/section groups, never within file pages."""
from collections import Counter, defaultdict
from structure_common import finish, require_rows, run_cli


def analyze(data):
    rows = require_rows(data, "sequence_entries", ("group", "number", "source_id", "locator"))
    specs = require_rows(data, "groups", ("id", "source_id", "start", "end"))
    grouped, expected, findings = defaultdict(list), {}, []
    for spec in specs:
        identity = (spec["source_id"], spec["id"])
        if identity in expected:
            raise ValueError(f"Duplicate group specification: {identity}")
        if type(spec["start"]) is not int or type(spec["end"]) is not int or spec["end"] < spec["start"]:
            raise ValueError("Group start/end must be increasing integers")
        expected[identity] = list(range(spec["start"], spec["end"] + 1))
    for row in rows:
        if type(row["number"]) is not int:
            raise ValueError("Sequence number must be an integer; resolve OCR first")
        identity = (row["source_id"], row["group"])
        if identity not in expected:
            findings.append({"code": "unknown_group", "location": row})
        grouped[identity].append(row)
    for identity, wanted in expected.items():
        members = grouped[identity]
        values = [row["number"] for row in members]  # supplied verified reading order
        counts = Counter(values)
        duplicate = sorted(n for n, count in counts.items() if count > 1)
        missing = sorted(set(wanted) - set(values))
        unexpected = sorted(set(values) - set(wanted))
        detail = {"source_id": identity[0], "group": identity[1]}
        if duplicate:
            findings.append({"code": "duplicate_number", **detail, "numbers": duplicate,
                             "locations": [r for r in members if r["number"] in duplicate]})
        if missing:
            findings.append({"code": "missing_number", **detail, "numbers": missing})
        if unexpected:
            findings.append({"code": "unexpected_number", **detail, "numbers": unexpected})
        if not duplicate and not missing and not unexpected and values != wanted:
            findings.append({"code": "number_order_mismatch", **detail, "locations": members})
    mismatched_groups = {(f.get("source_id"), f.get("group")) for f in findings if f["code"] != "unknown_group"}
    return finish(data, ("sequence_entries", "groups"), findings,
                  [{"check": "按天/节核对组内序号连续性", "checked_count": len(specs), "mismatch_count": len(mismatched_groups)},
                   {"check": "条目分组归属", "checked_count": len(rows), "mismatch_count": sum(f["code"] == "unknown_group" for f in findings)}])


if __name__ == "__main__":
    raise SystemExit(run_cli(analyze, __doc__))

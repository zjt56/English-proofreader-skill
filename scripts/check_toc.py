#!/usr/bin/env python3
"""Compare TOC targets with section starts; retain same-title section identities."""
from collections import defaultdict
from structure_common import finish, key, require_rows, run_cli


def analyze(data):
    basis = data.get("page_basis")
    if basis not in ("printed_page", "file_page"):
        raise ValueError("page_basis must explicitly be printed_page or file_page")
    toc = require_rows(data, "toc_entries", ("section_id", "title", "target_page", "target_source_id", "locator"))
    body = require_rows(data, "headings", ("section_id", "title", basis, "source_id", "locator"))
    grouped = defaultdict(list)
    for heading in body:
        grouped[(heading["source_id"], heading["section_id"])].append(heading)
    findings, seen, forward_mismatches = [], set(), 0
    for row in toc:
        before = len(findings)
        identity = (row["target_source_id"], row["section_id"])
        if identity in seen:
            findings.append({"code": "duplicate_toc_target", "location": row})
        seen.add(identity)
        matches = grouped.get(identity, [])
        if not matches:
            findings.append({"code": "toc_target_missing", "location": row})
        elif len(matches) > 1:
            findings.append({"code": "ambiguous_section_start", "location": row, "body_locations": matches})
        else:
            actual = matches[0]
            if key(row["title"]) != key(actual["title"]):
                findings.append({"code": "toc_title_mismatch", "location": row, "body_location": actual})
            if key(row["target_page"]) != key(actual[basis]):
                findings.append({"code": "toc_page_mismatch", "location": row, "body_location": actual})
        forward_mismatches += len(findings) > before
    reverse_mismatches = 0
    for row in body:
        if row.get("include_in_toc", True) and (row["source_id"], row["section_id"]) not in seen:
            findings.append({"code": "section_missing_in_toc", "location": row})
            reverse_mismatches += 1
    return finish(data, ("toc_entries", "headings"), findings,
                  [{"check": "目录标题及起始页回查", "checked_count": len(toc), "mismatch_count": forward_mismatches, "page_basis": basis},
                   {"check": "正文节标题反查目录收录", "checked_count": sum(r.get("include_in_toc", True) for r in body), "mismatch_count": reverse_mismatches}])


if __name__ == "__main__":
    raise SystemExit(run_cli(analyze, __doc__))

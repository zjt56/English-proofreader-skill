#!/usr/bin/env python3
"""Cross-check index terms and target pages against body headwords, both ways."""
from collections import defaultdict
from structure_common import finish, key, require_rows, run_cli


def analyze(data):
    basis = data.get("page_basis")
    if basis not in ("printed_page", "file_page"):
        raise ValueError("page_basis must explicitly be printed_page or file_page")
    index = require_rows(data, "index_entries", ("term", "target_page", "target_source_id", "locator"))
    body = require_rows(data, "body_entries", ("term", basis, "source_id", "locator"))
    ignore = data.get("ignore_case", False)
    by_term = defaultdict(list)
    for row in body:
        by_term[key(row["term"], ignore)].append(row)
    findings = []
    for row in index:
        term = key(row["term"], ignore)
        matches = by_term.get(term, [])
        target_matches = [item for item in matches if item["source_id"] == row["target_source_id"]]
        if not target_matches:
            findings.append({"code": "index_term_not_found", "term": row["term"], "location": row})
        elif not any(key(item[basis]) == key(row["target_page"]) for item in target_matches):
            findings.append({"code": "index_page_mismatch", "term": row["term"], "location": row,
                             "body_locations": target_matches})
    # Reverse check uses the source+term pair. An index of a different volume
    # cannot cover an identically spelled headword in this volume.
    forward_mismatches = len(findings)
    indexed = {(row["target_source_id"], key(row["term"], ignore)) for row in index}
    for row in body:
        if row.get("include_in_index", True) and (row["source_id"], key(row["term"], ignore)) not in indexed:
            findings.append({"code": "body_term_missing_in_index", "term": row["term"], "location": row})
    checks = [{"check": "索引逐条回查正文页码", "checked_count": len(index), "mismatch_count": forward_mismatches, "page_basis": basis},
              {"check": "正文词头反查索引收录", "checked_count": sum(r.get("include_in_index", True) for r in body),
               "mismatch_count": len(findings) - forward_mismatches}]
    return finish(data, ("index_entries", "body_entries"), findings, checks)


if __name__ == "__main__":
    raise SystemExit(run_cli(analyze, __doc__))

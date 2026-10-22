"""Conservative PDF geometry extraction. Coordinates are PDF points, not pixels.

Column proposals are NOT a verified reading order. Keep each line and font span
so that a reviewer can fix regions/columns without extracting the PDF again.
"""
from __future__ import annotations

from collections import Counter
import unicodedata


def is_private(character: str) -> bool:
    return unicodedata.category(character) == "Co"


def extract_lines(raw: dict) -> list[dict]:
    result = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            fragments, current, previous = [], [], None
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    box = list(char["bbox"])
                    # A large horizontal jump can cross cells or columns even
                    # when the PDF producer put them in the same text line.
                    if previous is not None and box[0] - previous[2] > max(10, float(span.get("size", 10)) * 1.8):
                        if current:
                            fragments.append(current)
                        current = []
                    current.append((char.get("c", ""), box, span.get("font", ""), span.get("size", 0)))
                    previous = box
            if current:
                fragments.append(current)
            for fragment in fragments:
                text = "".join(item[0] for item in fragment)
                if not text.strip():
                    continue
                box = [min(c[1][0] for c in fragment), min(c[1][1] for c in fragment),
                       max(c[1][2] for c in fragment), max(c[1][3] for c in fragment)]
                spans = []
                for char, char_box, font, size in fragment:
                    if spans and spans[-1]["font"] == font and spans[-1]["size"] == size:
                        spans[-1]["text"] += char
                        spans[-1]["bbox"][2] = max(spans[-1]["bbox"][2], char_box[2])
                        spans[-1]["bbox"][3] = max(spans[-1]["bbox"][3], char_box[3])
                    else:
                        spans.append({"font": font, "size": size, "text": char, "bbox": char_box[:]})
                result.append({"line_id": f"L{len(result) + 1:05d}", "bbox": box,
                               "text": text, "spans": spans,
                               "baseline": line.get("spans", [{}])[0].get("origin", (0, box[3]))[1],
                               "direction": list(line.get("dir", (1, 0)))})
    return result


def propose_breaks(lines: list[dict], box: list[float]) -> list[float]:
    """Find persistent empty x strips. Do not cluster only word start positions:
    indentation, phonetics and narrow table cells can otherwise look like columns.
    Full-width headings are excluded only from the proposal, never from output.
    """
    width = box[2] - box[0]
    eligible = [line for line in lines if line["bbox"][2] - line["bbox"][0] < width * .65
                and line["bbox"][3] - line["bbox"][1] < 50
                and not all(is_private(ch) or ch.isspace() for ch in line["text"])
                and abs(line["direction"][0]) > .9]
    if len(eligible) < 12 or width <= 0:
        return []
    step = 2
    bins = [0] * (int(width / step) + 1)
    for line in eligible:
        left, _, right, _ = line["bbox"]
        for index in range(max(0, int((left - box[0]) / step)), min(len(bins), int((right - box[0]) / step) + 1)):
            bins[index] += 1
    runs, start = [], None
    # A sparse heading may cross a gutter. It must not erase hundreds of rows'
    # geometric evidence, but the resulting columns still need visual approval.
    sparse = max(1, int(len(eligible) * .003))
    for i, occupied in enumerate(bins + [sparse + 1]):
        if occupied <= sparse and start is None:
            start = i
        elif occupied > sparse and start is not None:
            if (i - start) * step >= max(4, width * .008):
                runs.append(box[0] + (start + i) * step / 2)
            start = None
    breaks = []
    for cut in runs:
        left_count = sum(line["bbox"][2] < cut for line in eligible)
        right_count = sum(line["bbox"][0] > cut for line in eligible)
        if left_count >= 12 and right_count >= 12:
            breaks.append(cut)
    return breaks[:7]


def arrange_region(lines: list[dict], box: list[float], breaks: list[float], order: str) -> tuple[list[dict], list[str]]:
    crossing = []
    for line in lines:
        left, _, right, _ = line["bbox"]
        line["column"] = sum(left >= cut for cut in breaks) + 1
        if any(left < cut < right for cut in breaks):
            line["column"] = None
            crossing.append(line["line_id"])
    if order == "row":
        # Row grouping by vertical centre, not rounding y (which splits near rows).
        ordered = sorted(lines, key=lambda item: ((item["bbox"][1] + item["bbox"][3]) / 2, item["bbox"][0]))
        rows = []
        for line in ordered:
            cy = (line["bbox"][1] + line["bbox"][3]) / 2
            tolerance = min(3, (line["bbox"][3] - line["bbox"][1]) * .3)
            if rows and abs(rows[-1][0] - cy) <= tolerance:
                rows[-1][1].append(line)
            else:
                rows.append((cy, [line]))
        return [line for _, row in rows for line in sorted(row, key=lambda item: item["bbox"][0])], crossing
    # Spanning headings separate bands, preventing a lower section heading from
    # being moved ahead of all the preceding column text.
    headings = sorted((line for line in lines if line["column"] is None), key=lambda item: item["bbox"][1])
    ordered, remaining = [], [line for line in lines if line["column"] is not None]
    for heading in headings:
        band = [line for line in remaining if line["bbox"][1] < heading["bbox"][1]]
        ordered.extend(sorted(band, key=lambda item: (item["column"], item["bbox"][1], item["bbox"][0])))
        remaining = [line for line in remaining if line not in band]
        ordered.append(heading)
    ordered.extend(sorted(remaining, key=lambda item: (item["column"], item["bbox"][1], item["bbox"][0])))
    return ordered, crossing


def analyze_layout(raw: dict, page_box: list[float], columns: str = "auto", order: str = "column", config: dict | None = None) -> dict:
    lines = extract_lines(raw)
    auxiliary = [line for line in lines if all(is_private(ch) or ch.isspace() for ch in line["text"])
                 or abs(line["direction"][0]) < .9]
    content_lines = [line for line in lines if line not in auxiliary]
    specs = (config or {}).get("regions") or [{"bbox": page_box}]
    regions, ordered, assigned = [], [], set()
    for i, spec in enumerate(specs, 1):
        box = spec["bbox"]
        if len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError("Each region needs a nonempty bbox [x0,y0,x1,y1]")
        members = [line for line in content_lines if box[0] <= (line["bbox"][0] + line["bbox"][2]) / 2 < box[2]
                   and box[1] <= (line["bbox"][1] + line["bbox"][3]) / 2 < box[3]]
        if any(line["line_id"] in assigned for line in members):
            raise ValueError("Layout regions overlap text; use disjoint regions")
        assigned.update(line["line_id"] for line in members)
        explicit = "column_breaks" in spec or columns != "auto"
        if "column_breaks" in spec:
            breaks = spec["column_breaks"]
            if breaks != sorted(set(breaks)) or any(not box[0] < x < box[2] for x in breaks):
                raise ValueError("column_breaks must be unique increasing x coordinates inside bbox")
        elif columns != "auto":
            count = int(columns)
            if not 1 <= count <= 8:
                raise ValueError("columns must be auto or 1..8")
            breaks = [box[0] + (box[2] - box[0]) * n / count for n in range(1, count)]
        else:
            breaks = propose_breaks(members, box)
        region_order = spec.get("reading_order", order)
        if region_order not in ("column", "row"):
            raise ValueError("reading_order must be column or row")
        arranged, crossing = arrange_region(members, box, breaks, region_order)
        for line in arranged:
            line["region"] = i
        ordered.extend(arranged)
        regions.append({"region": i, "bbox": box, "column_breaks": breaks, "column_count": len(breaks) + 1,
                        "reading_order": region_order, "crossing_lines": crossing,
                        "status": "configured" if explicit else "proposed"})
    unassigned = [line for line in content_lines if line["line_id"] not in assigned]
    ordered.extend(unassigned)  # never silently discard text outside configured regions
    private = Counter((span["font"], f"U+{ord(ch):04X}") for line in lines for span in line["spans"]
                      for ch in span["text"] if is_private(ch))
    rows = []
    for line in ordered:
        if rows and rows[-1]["region"] == line.get("region") and rows[-1]["column"] == line.get("column") and abs(rows[-1]["baseline"] - line["baseline"]) <= 2:
            rows[-1]["line_ids"].append(line["line_id"])
            rows[-1]["text"] += " " + line["text"]
            rows[-1]["bbox"] = [min(rows[-1]["bbox"][0], line["bbox"][0]), min(rows[-1]["bbox"][1], line["bbox"][1]),
                                max(rows[-1]["bbox"][2], line["bbox"][2]), max(rows[-1]["bbox"][3], line["bbox"][3])]
        else:
            rows.append({"region": line.get("region"), "column": line.get("column"), "baseline": line["baseline"],
                         "bbox": line["bbox"][:], "text": line["text"], "line_ids": [line["line_id"]]})
    line_by_id = {line["line_id"]: line for line in ordered}
    for row in rows:
        members = sorted((line_by_id[identity] for identity in row["line_ids"]), key=lambda item: item["bbox"][0])
        row["line_ids"] = [line["line_id"] for line in members]
        row["text"] = " ".join(line["text"] for line in members)
    return {"column_count": max((r["column_count"] for r in regions), default=0),
            "layout_status": "unverified", "regions": regions, "lines": ordered, "rows": rows,
            "auxiliary_lines": auxiliary,
            "unassigned_lines": [line["line_id"] for line in unassigned],
            "text": "\n".join(line["text"] for line in ordered),
            "encoding_diagnostics": [{"font": font, "codepoint": code, "count": count,
                                      "kind": "font_mapping_required"} for (font, code), count in sorted(private.items())]}

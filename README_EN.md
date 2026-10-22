<p align="right"><a href="README.md">简体中文</a> &nbsp;|&nbsp; <strong>English</strong></p>

# English Teaching-Aid Proofreading Skill

For Grades 7–9 exercises, reading, grammar, writing, exam preparation and vocabulary books. British English is the default. Supports Word, PDF, scans, images and text. **Reports issues and corrections for an editor to approve; never edits the source.**

## Capabilities

- Checks spelling, grammar, meaning, collocations, punctuation, numbering, Chinese instructions/translations/explanations, and Chinese-English alignment. It explicitly cross-checks contents-to-body sections, question/sequence numbers-to-body, questions-to-answers/explanations, and indexes-to-entries.
- Solves exercises before consulting keys and explanations. Vocabulary checks cover phonetics, parts of speech, senses, word forms, appendices, contents/index pages and grouped numbering.
- Reads the same version three times: initial inspection, independent rereading, then a fresh reading followed by verification. Formal Mudu proofs follow actual revised versions and red-checks.
- Distinguishes intentional blanks, brackets and distractors from errors; filters extraction noise, column-order failures and legitimate variants.
- Reports pages, questions/entries, source quotes, error types, concrete problems and corrections. Generates real Word reports when requested or when results exceed the thresholds below.

## Installation

Codex on Windows PowerShell:

```powershell
$skills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
New-Item -ItemType Directory -Force -Path $skills | Out-Null
git clone https://github.com/zjt56/English-proofreader-skill.git (Join-Path $skills 'english-teaching-aid-proofreader')
```

macOS/Linux:

```bash
skills_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skills_dir"
git clone https://github.com/zjt56/English-proofreader-skill.git "$skills_dir/english-teaching-aid-proofreader"
```

If the directory already exists, back it up or choose another location. Reload skills, then invoke `$english-teaching-aid-proofreader`. On other Agent Skills platforms, import the whole package and preserve relative paths. File reading, Python and Word generation depend on host capabilities.

## Usage

Supply the manuscript, version and scope, along with related answer keys, explanations, figures and publisher rules. With no scope specified, all readable submitted content is checked. Missing dependencies are reported rather than invented.

```text
Use $english-teaching-aid-proofreader on PDF pages 1–12.
Use British English and three complete readings of this version.
Check questions, answers and explanations. Report page, question, source quote,
error type, problem and correction. Do not edit the manuscript.
Flag uncertainties for the editor and deliver a Word report.
```

The workflow is: assess reading method → identify structure and priorities → review using applicable rules → report. Structural alignment comes first: contents, body sections, question/sequence numbers, answers/explanations, and index entries are checked item by item. Sampling only selects the reading method. A model with image access checks scans and verifies disputed characters against the original page. See [SKILL.md](SKILL.md) and [workflow details](references/proofreading-workflow.md).

**A concise entry point, with details loaded as needed.** Vocabulary books use entry rules; exercises use relevant grammar and answer checks. Tool arguments and JSON fields are read only when needed. Detailed language rules and positive/negative examples remain available.

## Reports

Use “Results → Issues → Brief note.” Count confirmed errors, style inconsistencies, editorial questions and insufficient material separately. Grouped issues retain their scope, sample locations, verified counts and corrections. Internal process logs stay out of the editor-facing report.

Generate a real `.docx` when requested, when the report exceeds 3,000 visible non-whitespace characters, or when confirmed locations exceed 10. Provide a file link; do not claim an unavailable file was generated. See [output rules](references/output-format.md) and the [fictional report](examples/editor-report-example.md).

## Auxiliary Tools

Available Word/WPS, Grammarly, Xiezuocat and LanguageTool features can provide candidates. No external checker is required. The model reviews context before accepting candidates; unpublished manuscripts are not uploaded without authorization.

Bundled scripts prepare material, compare structures/styles, validate reports and build Word files. Python 3.10+ is required; structural checks and DOCX generation use the standard library. PDF requires PyMuPDF; DOCX pagination needs LibreOffice or a host preview. python-docx is only an optional independent test dependency.

```text
python scripts/check_dependencies.py
python scripts/prepare_review.py manuscript.pdf --pages 1,3-5 --no-render --output-dir probe_assets
python scripts/cross_check_index.py examples/structural-review-input.json
python scripts/check_consistency.py examples/consistency-input.json --output consistency-findings.json
python scripts/validate_review.py examples/single-delivery-report.json
python scripts/build_report_docx.py examples/single-delivery-report.json example-report.docx --always
```

Examples are fictional. The consistency example intentionally returns one candidate and exits 1; 0 means no mismatch in supplied records, and 2 means invalid data or an execution error. Structural scripts consume verified records, not arbitrary PDF layouts. Incomplete extraction cannot support a whole-book pass. See [tools](references/mechanical-checks.md), [structure contracts](references/structured-checks.md) and [report fields](references/report-schema.md). When maintaining scripts, run `python -m unittest discover -s tests -v`.

## Reference Materials

The [publication guide](references/publication-reference-guide.md) and [public-service guide](references/public-service-reference-guide.md) indicate what sources to consult. No OCR-derived standards text or local-file indexes are bundled. Supply applicable publisher rules when needed; guides are not mandatory standard clauses. Ordinary prose is not forced into signage style.

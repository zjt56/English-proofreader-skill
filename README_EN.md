<p align="right"><a href="README.md">简体中文</a> &nbsp;|&nbsp; <strong>English</strong></p>

# English Teaching-Aid Proofreading Skill

An AI proofreading skill for English learning materials for Grades 7–9, including synchronized exercises, reading, grammar, writing, and exam preparation. British English is the default. The skill can process Word files, PDFs, scans, and copyable text, subject to the capabilities of the host platform.

## What It Does

- Checks spelling, word forms, grammar, usage, collocations, punctuation, capitalization, numbers, symbols, formatting, and Chinese-English alignment.
- Solves exercises independently before checking the answer key and explanations. It looks for mismatched numbering, missing answers, missing conditions, invalid reasoning, and questions with no or multiple valid answers.
- Performs three complete proofreading passes. Long files are split into consecutive page ranges or complete question sets, and each batch receives all three passes.
- Produces an issue list with page and question locations, source text, evidence, and suggested editorial action. It reports the scope checked and any limitations.
- Reports suggestions only. It does not edit, overwrite, or reformat the source manuscript; the editor makes the final decisions.

## Installation

### Codex

**Windows PowerShell:**

```powershell
$skills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
New-Item -ItemType Directory -Force -Path $skills | Out-Null
git clone https://github.com/zjt56/English-proofreader-skill.git (Join-Path $skills 'english-teaching-aid-proofreader')
```

**macOS/Linux:**

```bash
skills_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skills_dir"
git clone https://github.com/zjt56/English-proofreader-skill.git "$skills_dir/english-teaching-aid-proofreader"
```

These commands preserve the relative structure of `SKILL.md` and `references/`. If the skill directory already exists, back it up or remove it before cloning.

After reloading the skill, invoke it explicitly with `$english-teaching-aid-proofreader` or ask for an English teaching-aid proofreading task directly.

### Other Agent Skills platforms

Import this repository according to the platform's skill installation procedure, preserving both `SKILL.md` and `references/`. Skill paths and file-access capabilities vary by platform. Generating and checking a Word report also depends on DOCX support in the host environment.

## How to Use

When submitting a manuscript, include as much of the following as possible:

1. The manuscript and its version.
2. The requested scope, such as PDF pages, printed page numbers, sections, or question numbers. If no scope is specified, all readable submitted content is checked.
3. The related reading passages, figures, answer key, and explanations. Missing materials will be reported as limitations; the skill will not invent them.
4. The required English variant or publisher style. British English is the default. Where both British and American spellings are valid, inconsistent usage is normally reported as a consistency issue rather than a spelling error.

Example prompt:

```text
Use $english-teaching-aid-proofreader to proofread pages 1–12 of the attached PDF.
Use British English by default. Check the reading passage, questions, answer key,
and explanations together. Complete all three proofreading passes and report each
issue by PDF page and question number. Do not edit the source. Mark uncertain items
as “For editorial confirmation” or “Insufficient material.”
```

For scans, OCR is only an aid to locating text. Character-level issues should be checked against the page image whenever possible. Unclear or unreadable text is marked for image verification rather than guessed from OCR.

## Report Format

Reports use three sections in this order: “Summary → Issues → Coverage and limitations.” Each issue has a unique ID, location, category and status, impact, confidence, source text, rationale, and suggested editorial action. Confirmed errors are distinguished from style inconsistencies, items for editorial confirmation, and cases with insufficient material.

When the final report exceeds approximately 3,000 Chinese characters, the skill attempts to generate a complete Word report and returns a short summary with a file link in chat. The report never replaces or overwrites the source manuscript.

## Reference Materials

This repository currently does not include the publisher's internal handbook or other local rules that are still being organized. Provide applicable house-style documents with the task. Rules without an explicit basis will not be presented as mandatory publisher requirements.

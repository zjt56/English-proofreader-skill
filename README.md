<p align="right">
  <a href="#zh-cn">简体中文</a> &nbsp;|&nbsp; <a href="#english">English</a>
</p>

<a id="zh-cn"></a>

# 初中英语教辅编校 Skill

面向七至九年级英语教辅的 AI 编校技能，适用于同步练习、阅读、语法、写作和中考备考材料。默认以英式英语为目标，支持 Word、PDF、扫描件及可复制文本。

## 功能

- 检查拼写、词形、语法、用词、搭配、标点、大小写、数字符号、格式及中英文表达对应等问题。
- 独立核对题目、选项、答案和解析，关注错号、漏答、条件缺失、无解、多解和推理不成立。
- 按完整的一校、二校、三校流程重复检查；长稿按连续页或完整题组分批，每批都完成三校。
- 输出带页码、题号、原文证据、问题依据及建议处理的问题清单，并标明覆盖范围和未能核查的内容。
- 只提出修改建议，不会直接修改、覆盖或重排原稿。最终判断和修改由编辑完成。

## 安装

### Codex

**Windows PowerShell：**

```powershell
$skills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
New-Item -ItemType Directory -Force -Path $skills | Out-Null
git clone https://github.com/zjt56/English-proofreader-skill.git (Join-Path $skills 'english-teaching-aid-proofreader')
```

**macOS/Linux：**

```bash
skills_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skills_dir"
git clone https://github.com/zjt56/English-proofreader-skill.git "$skills_dir/english-teaching-aid-proofreader"
```

以上命令会保留 `SKILL.md` 和 `references/` 的相对结构。若技能目录已经存在，请先备份或移除旧版本，避免克隆失败。

重新加载技能后，可显式调用 `$english-teaching-aid-proofreader`，也可直接提出英语教辅编校任务。

### 其他支持 Agent Skills 的平台

按照平台的技能安装方式导入本仓库，并确保 `SKILL.md` 与 `references/` 一同保留。不同平台的技能目录和文件访问能力可能不同；长报告 Word 输出也取决于运行环境是否支持生成和检查 DOCX。

## 使用方法

提交稿件时，尽量一并提供：

1. 要校对的稿件，以及明确的文件版本。
2. 核查范围，例如文件页码、印刷页码、章节或题号；未指定时默认检查所提交的全部可读内容。
3. 与题目相关的阅读材料、图表、答案和解析。缺少材料时，技能会说明因此无法核验的部分，不会自行补全。
4. 英语变体或出版社体例要求。未另行指定时默认英式英语；英、美拼写均可接受时，混用通常作为一致性问题报告，而不是直接判作拼写错误。

示例指令：

```text
请使用 $english-teaching-aid-proofreader，校对附件 PDF 第 1–12 页。
默认按英式英语检查。请把阅读材料、题目、答案和解析一并核对，
完成一校、二校、三校后，按 PDF 文件页码和题号输出问题清单。
不要修改原稿；不确定的地方请列为“编辑确认”或“材料不足”。
```

对于扫描件，OCR 仅用于辅助检索；字符类问题须尽可能回看原图。图像不清或无法读取时，会标明“原图待核”，不会依据 OCR 猜定原文。

## 输出方式

报告固定分为“报告摘要 → 问题条目 → 覆盖与限制”。问题条目提供唯一编号、位置、问题类别与性质、影响等级、置信度、原文证据、问题依据和建议处理。已确认错误、体例/一致性问题、编辑确认项和材料不足项会区分标注。

若最终报告正文超过约 3,000 个中文字符，技能会尝试生成完整 Word 报告，并在对话中提供简短摘要和文件链接。原稿不会被报告文件替代或覆盖。

## 规范资料

本仓库目前不包含公司的内部编辑手册或其他未整理的本地规范。任务涉及出版社专属体例时，请同时提供适用规范；没有明确依据的事项不会被表述为公司强制规则。

---

<a id="english"></a>

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

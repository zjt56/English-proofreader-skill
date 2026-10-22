<p align="right"><strong>简体中文</strong> &nbsp;|&nbsp; <a href="README_EN.md">English</a></p>

# 初中英语教辅编校 Skill

协助编辑校对七至九年级同步练习、阅读、语法、写作、中考备考和词汇背记材料。默认英式英语，支持Word、PDF、扫描页、图片及文本。**只出问题和修改建议，不改原稿。**

## 能做什么

- 查拼写、语法、词义搭配、标点、编号、中文题干/译文/解析及中英对应。
- 独立解题后核答案和解析；词表专查音标、词性义项、词形及附表，批量核目录/索引页码和组内序号。
- 同一版本完整检查三遍：初检、独立复读、冷读后复核；正式木牍三校另按实际改排与核红推进。
- 理解挖空、括号、选项和干扰项的题型功能，过滤抽取乱码、错栏及合法变体造成的误报。
- 输出页码、题号/词条、原文、错误类型、具体问题和改法；长报告或用户要求时生成真实Word文档。

## 安装

Codex的Windows PowerShell：

```powershell
$skills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
New-Item -ItemType Directory -Force -Path $skills | Out-Null
git clone https://github.com/zjt56/English-proofreader-skill.git (Join-Path $skills 'english-teaching-aid-proofreader')
```

macOS/Linux：

```bash
skills_dir="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$skills_dir"
git clone https://github.com/zjt56/English-proofreader-skill.git "$skills_dir/english-teaching-aid-proofreader"
```

目录已存在时先备份或选择其他位置，避免覆盖。重新加载技能后，可用 `$english-teaching-aid-proofreader` 调用。其他支持Agent Skills的平台按其方式导入，保留整个技能包的相对目录；文件阅读、Python和Word生成能力以宿主环境为准。

## 怎么用

提供稿件、版本及核查范围；相关答案、解析、图表和出版社体例一并提供。未指定范围时检查提交的全部可读内容，缺必要材料时说明待核，不猜补。

```text
请用 $english-teaching-aid-proofreader 校对附件PDF第1–12页。
按英式英语，同一版本完整检查三遍；核题干、答案及解析。
列出页码、题号、原文、错误类型、具体问题和修改建议，不改原稿。
不确定项交编辑确认；请输出Word报告。
```

技能执行“判断读取方法 → 识别结构与重点 → 按适用规则检查 → 报告”。试读只选方法，不替代全文检查。扫描页由能看图的模型核读，字符争议回原图。入口见 [SKILL.md](SKILL.md)，读取、分批及正式校次区别见 [流程细节](references/proofreading-workflow.md)。

**入口精简，细节按需读。** 无需先加载全部参考：词表读词条规则，练习读相关语法/题答章节；工具参数和JSON字段只在使用工具时查。详细知识点、正反例和差错示例保留。

## 报告

采用“校对结果 → 问题条目 → 简短说明”，明确差错、体例/一致性、编辑确认和材料不足分开统计。全稿同类问题可合并，但保留范围、定位样例、实际次数和具体改法。内部流程台账不堆给编辑。

用户要求Word、报告超过3000个可见非空白字符，或确认位置超过10处时生成真实`.docx`并给链接。没有实际生成能力时说明，不伪装文件。见 [输出规范](references/output-format.md)及 [虚构报告示例](examples/editor-report-example.md)。

## 辅助工具

Word/WPS、Grammarly、秘塔写作猫和LanguageTool可按现有能力提供候选；没有外部检查器也能工作。AI结合原稿判断，不自动采纳或上传未公开稿件。

本包脚本负责读取、结构/体例比较、报告校验和Word生成。Python 3.10+；结构检查和Word生成只需标准库，PDF需PyMuPDF，DOCX分页需LibreOffice或宿主预览，python-docx仅供可选独立测试。先运行：

```text
python scripts/check_dependencies.py
python scripts/prepare_review.py manuscript.pdf --pages 1,3-5 --no-render --output-dir probe_assets
python scripts/cross_check_index.py examples/structural-review-input.json
python scripts/check_consistency.py examples/consistency-input.json --output consistency-findings.json
python scripts/validate_review.py examples/single-delivery-report.json
python scripts/build_report_docx.py examples/single-delivery-report.json example-report.docx --always
```

样例为虚构。一致性样例故意含一项候选，退出1属于预期结果；0表示输入记录内未见不符，2表示数据/运行错误。结构脚本接收已核实的记录，不能自动将任意PDF变成可信词表；未整理全不得宣称全书通过。完整用法见 [工具说明](references/mechanical-checks.md)、[结构契约](references/structured-checks.md)和 [报告字段](references/report-schema.md)。维护脚本可运行 `python -m unittest discover -s tests -v`。

## 规范资料

仅保留 [出版参考方向](references/publication-reference-guide.md)和 [公共服务方向](references/public-service-reference-guide.md)，提示AI遇到疑点应查哪类正式资料，不收录OCR规范原文或本地文件索引。需出版社专属规则时提供适用规定；方向指引不当作强制条文。普通叙述不机械套用公共标识语体。

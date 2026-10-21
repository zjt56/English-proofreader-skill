# 多模态审校与机械校验工具

这些工具负责整理来源、页码和审校状态，不判断英文是否正确，也不替大语言模型解题。拼写、语法、语义、图表关系和答案解析仍须由模型结合原稿上下文判断；脚本输出只能作为结构提示。

## 资料准备

Python 可用时运行：

```text
python scripts/prepare_review.py manuscript.pdf --output-dir review_assets
python scripts/prepare_review.py manuscript.docx --output-dir review_assets
python scripts/prepare_review.py page_images --output-dir review_assets
```

每次使用新的输出目录，避免覆盖上次清单或图像。脚本只读原稿，在输出目录生成 `manifest.json`；PDF 按文件页提取文字并渲染单页 PNG，图片按文件名排序并登记，DOCX 提取正文段落/表格并尝试用本机 LibreOffice 渲染页面。PDF 需要 PyMuPDF；DOCX 的页面图需要 LibreOffice。缺少依赖时会保留可完成的文字清单并在警告中说明，不会声称完成版面核验。

把 `manifest.json` 与对应页面图像一起提供给多模态模型。小字号或复杂表格应逐页查看清晰原图，不用缩略接触表代替；OCR/文本层只用于检索，原图才用于确认字符和版面。扫描页无文本层不代表空白，须由模型直接看图；图像无法读取时标“原图待核”。

DOCX 中段落/表格清单使用稳定块编号，不凭抽取文本推断页码。只有页面渲染结果可用时，才报告本次导出页码；页码随字体或软件变化时同时保留题号和块定位。

## 答案表结构检查

`check_answer_key.py`读取下列 JSON。题号应拆到实际可核对的最小单元，例如 `4(a)`；选择题可填写选项标签，主观题可不提供 `options`。

```json
{
  "questions": [
    {"id": "1", "options": ["A", "B", "C", "D"]},
    {"id": "2"}
  ],
  "answers": [
    {"id": "1", "value": "C"},
    {"id": "2", "value": "because ..."}
  ]
}
```

运行 `python scripts/check_answer_key.py answer_map.json`。脚本只报告重复题号、缺失/多余答案和选项标签不匹配，不能判断答案语义正确，也不能代替先独立解题再对答案。

## 报告校验与 DOCX

需要脚本核验或生成 DOCX 时，将结果暂存为 JSON：

```json
{
  "title": "英语教辅编校问题清单",
  "metadata": {"manuscript": "稿件名及版本", "scope": "PDF第1-3页", "report_date": "YYYY-MM-DD"},
  "summary": {"issue_counts": {"明确差错": 0, "体例/一致性": 0, "编辑确认": 0, "材料不足": 0}},
  "issues": [],
  "coverage": {
    "three_passes_complete": false,
    "batches": [{"id": "B01", "scope": "PDF第1-3页", "passes": {"first": "complete", "second": "complete", "third": "not_done"}}],
    "limitations": []
  }
}
```

`issues`中的每项须有 `id`、`status`、`category`、`severity`、`confidence`、`locations`、`explanation`、`basis` 和 `suggestion`。每个 `locations` 元素至少包含 `locator`；可用 `file_page`、`printed_page`、`question` 和 `quote` 提供更精确的定位。`status` 使用“明确差错”“体例/一致性”“编辑确认”“材料不足”之一。一个问题影响多个位置时，在同一项的 `locations` 中逐处列出。

运行：

```text
python scripts/validate_review.py report.json --manifest review_assets/manifest.json
python scripts/build_report_docx.py report.json report.docx
```

报告校验器会检查必需字段、问题编号、状态计数、定位引文与可用清单的一致性，以及是否有依据声称三校完成。它能检查记录和格式，不能证明模型确实完整阅读了所有页面。DOCX 生成器会按可见非空白字符数自动判断：默认超过 3,000 字符才生成；用户要求无论长度都生成时加 `--always`，指定阈值时加 `--threshold 5000` 等参数。生成器只从 JSON 创建新文件，不覆盖已有文件或原稿；生成后仍应使用可用的 Word/LibreOffice 渲染能力做视觉检查。

## 规则型检查器的边界

本技能面向可见原稿与多模态模型。若某环境额外运行拼写或语法检查器，其结果只能作为低优先级候选，必须回到原文、版面和上下文核实；不得用它代替图像识读、独立解题、答案解析核查或三轮复读。不要把稿件上传到未经用户批准的在线检查服务。

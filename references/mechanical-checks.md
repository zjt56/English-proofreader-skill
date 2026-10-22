# 辅助工具

只查本次要用的工具。工具产生候选或核对记录，AI须回原稿判断；无Python或外部检查器时，用宿主附件/图片能力继续，不虚构运行结果。结构准备方法见 [流程细节](proofreading-workflow.md)。

## 工具选择

| 任务 | 工具 | AI仍须核对 |
|---|---|---|
| 读取与定位 | 宿主预览、prepare_review.py | 文字可信度、栏序、跨页及原页码 |
| 索引/目录/序号 | cross_check_index.py、check_toc.py、check_sequence.py | 同版对应、收录口径、Day/节分组 |
| 题答编号/选项 | check_answer_key.py | 独立解题、答案及解析语义 |
| 术语/体例混用 | check_consistency.py | 同一含义/范围、专名引文等例外 |
| 改排核红 | 已有版本比较工具 | 逐项改对改全、误删错位及新增内容 |
| 报告与Word | validate_review.py、build_report_docx.py | 建议可执行、定位准确、可见版式 |

## 可选语言检查工具

使用已具备的工具，不要求先购买、安装或登录。只看建议，不接受全部修改；需要转换或设置时操作临时副本。第三方在线处理未公开稿件须用户授权。

| 工具 | 用途与设置 |
|---|---|
| Word/WPS | 补查拼写、字词和标点；功能以实际版本为准。Word英文部分设 English (United Kingdom)，中文分别处理 |
| Grammarly | 补查英文拼写/语法；设British English，过滤文风润色建议 |
| 秘塔写作猫 | 补查中文题干、译文、解析的字词/语句；不把改写或润色当差错 |
| LanguageTool | 已有可用服务时补查英文；明确英式变体，API用en-GB，单写en不能指定英式 |
| 词典/语法工具书 | 查具体义项、词性、搭配、音标；读适用条件和用例，不只看搜索摘要 |

处理顺序：保留实际工具/设置 → 找回原页与语境 → 排除题型设计和合法变体 → 核规则与最小改法 → 去重入报告。偏移量、复制段落或临时文档页码不能充当原稿页码。多个工具标红仍不等于差错，未标红也不等于已审完。

功能变动时查官方说明：[Word](https://support.microsoft.com/en-us/word/check-spelling-and-grammar-in-a-different-language)、[WPS](https://plus.wps.cn/blog/p121197.html)、[Grammarly](https://support.grammarly.com/hc/en-us/articles/115000089992-Select-between-British-English-American-English-Canadian-English-Australian-English-and-Indian-English)、[写作猫](https://apidocs.xiezuocat.com/guide/)、[LanguageTool](https://languagetool.org/http-api/swagger-ui/)。

## 运行条件

Python 3.10+。先运行 `python scripts/check_dependencies.py`，只检查、不安装或联网。

| 能力 | 依赖 |
|---|---|
| DOCX正文/表格、TXT/图片登记、结构核对、报告校验和DOCX生成 | Python标准库，无需python-docx |
| PDF文字、坐标、字体、页图 | PyMuPDF（import pymupdf；兼容旧fitz导入，不安装名为fitz的无关包） |
| DOCX实际分页 | LibreOffice或宿主Word预览；缺少时用块号，不猜页码 |
| 测试中独立读回Word | python-docx，可选；不影响必做的ZIP/XML检查 |

脚本不自动安装依赖。需要PDF能力时可在适用环境安装 `python -m pip install pymupdf`；无本地语言检查器也能使用本技能。

## 素材准备

```text
python scripts/prepare_review.py manuscript.pdf --pages 1,3-5 --no-render --source-id body --output-dir probe_assets
python scripts/prepare_review.py manuscript.pdf --pages 1,3-5 --output-dir visual_assets
python scripts/prepare_review.py manuscript.pdf --layout-config examples/layout-config.json --output-dir configured_assets
python scripts/prepare_review.py manuscript.docx --output-dir word_assets
python scripts/prepare_review.py page_images --output-dir image_assets
```

- 每次用新输出目录。`--pages`指原文件页，选第49页不会改成第1页；`--no-render`不生成页图，字符争议仍回原页。未选页则处理全部页。
- PDF清单保留源ID/哈希、文字/行框/字体、候选分栏和编码诊断。`layout_status=unverified`须人工/模型核图，不能自动改成已确认。`--columns N`仅适合已确认等宽栏；区域、非等宽及行/栏阅读序用配置，见 [版面规则](layout-aware-proofreading.md)。样例坐标不可照搬。
- 图片保留自然文件名顺序；DOCX保留段落/表格块。自动编号、浮动对象、页眉页脚另用宿主复核。旧DOC需只读预览或临时转换，不当ZIP读取。
- JSON及终端输出用UTF-8；结果优先用`--output`写新文件，避免Shell重定向编码。异常页局部看图，不反复全书抽取。

## 结构与一致性

目录、索引和分组序号的输入及命令见 [结构契约](structured-checks.md)，可运行数据见 [结构样例](../examples/structural-review-input.json)。脚本接收已整理并核实的记录，不是任意PDF自动解析器；覆盖不足不会给出全书通过。

题答脚本：`python scripts/check_answer_key.py answer_map.json`。输入如下；按实际小题拆ID，跨Day/大题重置时将组标识放入ID。它只核编号与选项，不判断答案语义。

```json
{"questions": [{"id": "D1-1", "options": ["A", "B", "C", "D"]}, {"id": "D1-2"}], "answers": [{"id": "D1-1", "value": "C"}, {"id": "D1-2", "value": "open response"}]}
```

一致性脚本：`python scripts/check_consistency.py examples/consistency-input.json --output consistency-findings.json`。输入见 [一致性样例](../examples/consistency-input.json)：

- `rules`有id/label/forms（至少两种）；可选preferred须属于forms，并附已确认体例basis。未定目标写法时仅列混用，不按多数定稿。
- `consistency_entries`有rule_id/scope/form/role/source_id/locator/quote；form须出现在引文中。scope按真实体例范围分组，不按页；保留大小写、标点和空格，仅规范Unicode NFC。
- role参与项：prose/title/label/definition/explanation/term；排除项：quotation/proper_name/distractor/error_example/answer_blank/code。按实际功能标注。
- `extraction_verified`、`complete.rules/consistency_entries`及可选expected_counts记录质量；空输入、全排除、未核实、未整理全或数量不符均不能通过。

一致性和三个结构脚本：退出码0=所提交完整记录未见不符，1=有候选或覆盖不足，2=输入/运行错误；不是全书语言正确证明。样例一致性数据故意含一项候选，预期退出1。`--output`拒绝覆盖；不匹配项须回原稿后才转为问题。

## 报告与Word

字段只在这一步查 [报告契约](report-schema.md)，不要先给编辑填写JSON。可运行 [单份稿件示例](../examples/single-delivery-report.json)：

```text
python scripts/validate_review.py report.json --manifest body_assets/manifest.json --manifest index_assets/manifest.json
python scripts/build_report_docx.py report.json report.docx --always
```

多文件以source_id分别核引文/哈希。单份稿件显式写mode=single_delivery，正式校次才写mudu。校验器只能检查记录自洽，不能证明真实阅读。

生成器用标准库写真实OOXML并读回ZIP/XML；`--always`用于用户要求Word。自动阈值、文件链接及可用时的可视检查见 [Word交付](long-report-docx.md)。不覆盖文件，不编造修改建议或视觉验收。

维护脚本时运行 `python -m unittest discover -s tests -v`；依赖缺失引起的跳过如实记录，不说全部功能已验证。PDF读取实现参考 [PyMuPDF文本结构](https://pymupdf.readthedocs.io/en/latest/app1.html)与 [文本示例](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)。

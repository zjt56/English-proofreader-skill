# 词表结构校验工具契约

这些脚本核对模型/宿主从可靠版面整理的结构记录，不是通用 PDF 自动词条解析器，不会仅凭一个乱码 PDF 生成可信的全书词表。先用 bbox 清单、原页和结构总数验证抽取质量，再运行。正文四个视觉区域也可能是两栏×上下两节，不能照抄其他 AI 的栏数。

## 记录准备与防伪通过

完整可运行的小型数据见 [结构样例](../examples/structural-review-input.json)。由模型/可用文档工具按 Day、索引字母段提取并缓存，编辑无需手填 1600 条。每条保留原始词头、`source_id`、定位；目录/词条页码须注明 `page_basis=printed_page` 或 `file_page`，禁止默认二者同值。多文件 ID 唯一，索引/目录的 `target_source_id` 指向正文。

`extraction_verified=true` 的前提：代表页的栏序/字段经原图确认，异常断词/拼接项全部反查，条数与独立结构预期核对，版本匹配。它是本次执行记录，不是脚本自动认证。`complete` 分别记录各集合是否全量整理；`expected_counts` 填已知独立预期，未知就不编造。字段缺失会返回输入错误；未验证、集合不全或条数不符则返回 `incomplete`，即便零不匹配也不能写“全书核对无误”。记录空集合时不得宣称完成非零检查。

所有结果仍是结构候选：`status=pass/mismatch/incomplete`、`findings`、`checks.checked_count`。差异回原图后才转正式问题。退出码 0=已声明完整且无不符；1=候选不符或输入覆盖不足；2=输入/运行错误。`--output` 新建结果 JSON，不覆盖旧文件。

## 题号、序号和目录—正文对应

这是每份教辅的必做结构检查，先于语言审校完成。按以下顺序建立同版对应关系：

1. **目录→正文章节**：逐项核对章节编号、标题、层级和起始页；正文出现但目录漏列、目录目标页错误、标题不一致或同一章节重复，分别记录。文件页与印刷页必须使用同一 `page_basis`，不能把两种页码直接比较。
2. **正文章节→题号/序号**：以可见 Day、单元、节或大题标题划组，核对组内题号/词条号是否连续、无重复、无漏号、无错号、无越界，且题号后的句号、括号等符号符合本组体例。跨页不断组，同页换组可合法重置；不清楚组界先看原页，不按页全局判重。
3. **题目→答案/解析**：核对题号、选项标签、答案和解析是否一一对应；重复题号、答案缺失、孤立答案、选项标签不在题目中都要列候选，再由 AI 独立作答判断语义。
4. **索引→词条/正文**：核对词头、收录范围、目标页和正文位置；“未找到”先排除错栏、断词、版本和收录口径，不直接定为漏收。

结构问题统一使用 `题号/序号结构`、`目录/正文对应`、`题目/答案/解析对应` 或 `索引/词条对应` 分类。报告中不要只写“序号有误”或“目录不一致”，要写出实际编号/标题、原文件页、印刷页（如有）、对应正文/目录位置、错误原因和修改建议。

## 三个核对器

```text
python scripts/cross_check_index.py examples/structural-review-input.json
python scripts/check_toc.py examples/structural-review-input.json
python scripts/check_sequence.py examples/structural-review-input.json
```

| 工具 | 输入集合及关键字段 | 可验证的事项/边界 |
|---|---|---|
| cross_check_index.py | index_entries: term,target_page,target_source_id,locator；body_entries: term,所选页码字段,source_id,locator | 词头在指定正文文件出现且页码命中；正文反查索引漏收。默认词头大小写敏感，只规范 NFC 与空白，不删连字符/词尾、不做模糊匹配。ignore_case 只能在既定收录体例允许时显式启用；正文 include_in_index=false 表示已确认不收录的附属条目 |
| check_toc.py | toc_entries: section_id,title,target_page,target_source_id,locator；headings: section_id,title,所选页码字段,source_id,locator | 目录→正文的章节标题、起始页、重复目标及正文漏入目录；同名章节用不同 section_id，不按标题一刀切。headings 只放章节开头，续页标题不是新开头；附表同样作为有ID的节 |
| check_sequence.py | groups: id,source_id,start,end；sequence_entries: group,number,source_id,locator | 正文组内题号/序号的重复、漏号、错号、超范围及次序。条目按确认的组内阅读序排列；跨页不断组，同页新天重置合法。不得用页码充当group；group不明先回看标题，不能靠序号重复自动划组 |

正文同词出现在多个合法位置，索引指向任一收录位置即可；多义重复/异体收录的其他政策由模型按本书体例核。`index_term_not_found` 只表示输入集合未找到，不自动等于原稿漏词。标题、符号差异也须按正式规范判断。

## 报告回填

把已完成的检查记入 `summary.structural_findings`，例如 `check/status/checked_count/mismatch_count/scope/evidence`；建议至少分别记录“目录—正文章节”“正文组内题号/序号”“题目—答案/解析”“索引—词条”。evidence 指向本次结果文件/记录与核对范围。只完成样例不能填成全书数据。pass 要有实际非零条数且 mismatch_count=0，覆盖不足用 incomplete。不匹配项经原图确认后另入 issues，不能把全部脚本 finding 直接当明确差错导出。

## 无代码环境

云端不支持 Python 时按相同字段建可续接的内部表，由模型双向核对并记录实际条数；超长时按组分批合并。未能全量核对的集合只报已完成范围，不虚构脚本名、运行输出或成功统计。三种核对不能代替词性、释义、音标和例句的逐条语义审查。

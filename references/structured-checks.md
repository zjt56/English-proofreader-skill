# 词表结构校验工具契约

这些脚本核对模型/宿主从可靠版面整理的结构记录，不是通用 PDF 自动词条解析器，不会仅凭一个乱码 PDF 生成可信的全书词表。先用 bbox 清单、原页和结构总数验证抽取质量，再运行。正文四个视觉区域也可能是两栏×上下两节，不能照抄其他 AI 的栏数。

## 记录准备与防伪通过

完整可运行的小型数据见 [结构样例](../examples/structural-review-input.json)。由模型/可用文档工具按 Day、索引字母段提取并缓存，编辑无需手填 1600 条。每条保留原始词头、`source_id`、定位；目录/词条页码须注明 `page_basis=printed_page` 或 `file_page`，禁止默认二者同值。多文件 ID 唯一，索引/目录的 `target_source_id` 指向正文。

`extraction_verified=true` 的前提：代表页的栏序/字段经原图确认，异常断词/拼接项全部反查，条数与独立结构预期核对，版本匹配。它是本次执行记录，不是脚本自动认证。`complete` 分别记录各集合是否全量整理；`expected_counts` 填已知独立预期，未知就不编造。字段缺失会返回输入错误；未验证、集合不全或条数不符则返回 `incomplete`，即便零不匹配也不能写“全书核对无误”。记录空集合时不得宣称完成非零检查。

所有结果仍是结构候选：`status=pass/mismatch/incomplete`、`findings`、`checks.checked_count`。差异回原图后才转正式问题。退出码 0=已声明完整且无不符；1=候选不符或输入覆盖不足；2=输入/运行错误。`--output` 新建结果 JSON，不覆盖旧文件。

## 三个核对器

```text
python scripts/cross_check_index.py examples/structural-review-input.json
python scripts/check_toc.py examples/structural-review-input.json
python scripts/check_sequence.py examples/structural-review-input.json
```

| 工具 | 输入集合及关键字段 | 可验证的事项/边界 |
|---|---|---|
| cross_check_index.py | index_entries: term,target_page,target_source_id,locator；body_entries: term,所选页码字段,source_id,locator | 词头在指定正文文件出现且页码命中；正文反查索引漏收。默认词头大小写敏感，只规范 NFC 与空白，不删连字符/词尾、不做模糊匹配。ignore_case 只能在既定收录体例允许时显式启用；正文 include_in_index=false 表示已确认不收录的附属条目 |
| check_toc.py | toc_entries: section_id,title,target_page,target_source_id,locator；headings: section_id,title,所选页码字段,source_id,locator | 目录标题、起始页、重复目标及正文漏入目录；同名章节用不同 section_id，不按标题一刀切。headings 只放章节开头，续页标题不是新开头；附表同样作为有ID的节 |
| check_sequence.py | groups: id,source_id,start,end；sequence_entries: group,number,source_id,locator | 按文件+Day/节分组查重号、漏号、超范围及次序。条目按确认的组内阅读序排列；跨页不断组，同页新天重置合法。不得用页码充当group；group不明先回看标题，不能靠序号重复自动划组 |

正文同词出现在多个合法位置，索引指向任一收录位置即可；多义重复/异体收录的其他政策由模型按本书体例核。`index_term_not_found` 只表示输入集合未找到，不自动等于原稿漏词。标题、符号差异也须按正式规范判断。

## 报告回填

把已完成的检查记入 `summary.structural_findings`，例如 `check/status/checked_count/mismatch_count/scope/evidence`；evidence 指向本次结果文件/记录与核对范围。只完成样例不能填成全书数据。pass 要有实际非零条数且 mismatch_count=0，覆盖不足用 incomplete。不匹配项经原图确认后另入 issues，不能把全部脚本 finding 直接当明确差错导出。

## 无代码环境

云端不支持 Python 时按相同字段建可续接的内部表，由模型双向核对并记录实际条数；超长时按组分批合并。未能全量核对的集合只报已完成范围，不虚构脚本名、运行输出或成功统计。三种核对不能代替词性、释义、音标和例句的逐条语义审查。

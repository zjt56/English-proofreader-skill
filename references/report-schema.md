# 报告JSON契约

仅供生成Word、脚本校验或续审时查阅。编辑可见格式由 [输出规范](output-format.md)决定。完整可运行数据见 [single-delivery-report.json](../examples/single-delivery-report.json)，数据为虚构。

## 通用字段

| 层级 | 字段与约定 |
|---|---|
| 顶层 | `title`，`metadata`，`summary`，`issues`数组，`coverage` |
| metadata | `manuscript/scope/report_date`；多文件用 `sources` 数组记录 `source_id` 及可用 `source_sha256`；读取和结构信息可放 `intake`，不显示给编辑 |
| summary | `result`简述；`issue_counts`必须包含四类且与issues计数一致；可选 `structural_findings` |
| issue必填 | 唯一 `id`；`status/category/severity/confidence/explanation/basis/suggestion`为非空字符串；非空 `locations`数组 |
| location | 非空 `locator`及原文 `quote`（材料不足可缺引文）；按实际给 `source_id/file_page/printed_page/question/entry/block_id`；具体改法用 `suggested`，可附 `error_type` |

status只用：`明确差错`、`体例/一致性`、`编辑确认`、`材料不足`。severity取高/中/低：高表示可能改变题意、答案或核心信息。confidence取高/中/低；低置信度不能作为明确差错。explanation写错点及理由，basis写规则或可核依据，suggestion给编辑可执行的最小建议；多种合理改法说明条件。

未知页码不造数，用locator给段落/条目；多文件所有位置用唯一source_id关联源文件。引文校验可重复传 `--manifest`，源哈希须匹配，不拿另一个文件相同页号替代。清单未匹配或抽取文字不同的警告须回原图，不自动变成稿件差错。

## 范围项与结构结果

范围问题可加 `scope`对象，至少有description；次数已知时加正整数 `occurrence_count`、`count_status=exact/estimated`、`count_basis`。locations保留真实定位样例，数量不得超过所报次数；未知总量不编数字。问题项数仅按归并后的id计。

`summary.structural_findings` 每条写 `check/status/checked_count/mismatch_count/scope/evidence`。status为pass/mismatch/incomplete；计数为非负整数，mismatch_count不大于checked_count。pass必须实查非零条且不符为0，evidence指向实际工作结果；未全量只写已完成范围。

## 单份稿件记录

必须显式写 `coverage.mode=single_delivery`，否则旧版校验器默认按正式校次处理。

```json
{
  "mode": "single_delivery", "completed": true, "three_passes_complete": false,
  "required_internal_readings": 3,
  "batches": [{"id": "B01", "scope": "实际文件页/题组范围",
    "checks": {"structural": "complete", "semantic": "complete", "verification": "complete"},
    "internal_readings": 3}],
  "limitations": []
}
```

checks状态可用complete/partial/not_done/not_applicable；不适用时在批次 `not_applicable_reasons` 按检查名说明。internal_readings登记实际完整阅读遍数；默认要求3遍。本次用户明确调整时，修改required_internal_readings并写 `reading_requirement_basis`。只有所有适用检查及所需阅读完成、没有实质未核范围，才写completed=true。正常缺旧稿/核红稿不记限制。

## 正式木牍校次记录

仅明确指定或具有相应版本时用 `coverage.mode=mudu`，流程见 [木牍校次](mudu-three-review-three-proof.md)。coverage记review_stage、limitations和各批次：

```json
{
  "id": "B01", "scope": "实际指定范围",
  "passes": {"first": "complete", "second": "partial", "third": "not_done"},
  "proof_status": {
    "first": {"inspection": "complete", "sent_to_typesetting": true, "red_check": "complete"},
    "second": {"inspection": "partial", "sent_to_typesetting": false, "red_check": "not_done"},
    "third": {"inspection": "not_done", "sent_to_typesetting": false, "red_check": "not_done"}
  }
}
```

passes状态为complete/partial/not_done。按真实检查、送排和核红更新，未完成就留对应状态。只有所有批次三校完整闭环、无未核范围，才能置three_passes_complete=true；单份稿件永远不能置true。状态记录只能检查自洽，不能证明模型实际阅读。

# 运行手册

## 重新构建验证书

```powershell
cd G:\05-Study\13.LLMwiki
python .\scripts\bookwiki.py build --source "G:\05-Study\07.BooksLearning\数据库\DBA实战手记.md" --out "G:\05-Study\13.LLMwiki" --book "DBA实战手记" --max-tokens 1600
```

## 打开 Obsidian

打开目录：

```text
G:\05-Study\13.LLMwiki\workspace\DBA实战手记\wiki
```

入口文件：

```text
00-Home.md
```

## 关键产物

```text
workspace\DBA实战手记\sources\source.md                  原文证据
workspace\DBA实战手记\chunks\chunks.jsonl                 证据块
workspace\DBA实战手记\chunks\work-orders\*.json           模型任务单
workspace\DBA实战手记\chunks\batches.md                   批次清单
workspace\DBA实战手记\wiki\token-budget.md                Token 预算报告
workspace\DBA实战手记\review\audit-report.md              审计报告
```

## 下一步：校验模型抽取结果

```powershell
python .\scripts\bookwiki.py validate-extraction --book-root "G:\05-Study\13.LLMwiki\workspace\DBA实战手记" --input "G:\05-Study\13.LLMwiki\workspace\DBA实战手记\extracted\knowledge.batch-001.jsonl"
```

## 下一步：生成候选概念页

```powershell
python .\scripts\bookwiki.py compile-concepts --book-root "G:\05-Study\13.LLMwiki\workspace\DBA实战手记" --min-confidence 0.75
```

候选概念页输出到：

```text
workspace\DBA实战手记\review\candidates\
```

## 批量生成 AI 导学层

```powershell
python .\scripts\bookwiki.py compile-learning-guides --book-root "G:\05-Study\13.LLMwiki\workspace\DBA实战手记" --skip-existing
```

说明：

- `--skip-existing` 会保留已经人工或模型优化过的导学区。
- 生成报告：`workspace\DBA实战手记\review\learning-guide-report.json`。
- 规则生成适合做第一版全覆盖；重点章节建议再用大模型按 `chunks\learning-orders\*.json` 精修。

## 当前验证结果

- 证据块：594 个。
- 全书估算输入：326857 tokens。
- 单次整书阅读估算：至少 329857 tokens，质量不可控。
- 已生成批次清单，每批约 18000 tokens 以内。
- 审计：通过。

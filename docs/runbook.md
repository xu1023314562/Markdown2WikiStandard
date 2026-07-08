# 运行手册

## 重新构建验证书

```powershell
cd G:\05-Study\13.LLMwiki
python .\scripts\bookwiki.py build --source "G:\05-Study\07.BooksLearning\数据库\DBA.md" --out "G:\05-Study\13.LLMwiki" --book "DBA" --max-tokens 1600
```

## 打开 Obsidian

打开目录：

```text
G:\05-Study\13.LLMwiki\workspace\DBA\wiki
```

入口文件：

```text
00-Home.md
```

## 关键产物

```text
workspace\DBA\sources\source.md                  原文证据
workspace\DBA\chunks\chunks.jsonl                 证据块
workspace\DBA\chunks\work-orders\*.json           模型任务单
workspace\DBA\chunks\batches.md                   批次清单
workspace\DBA\wiki\token-budget.md                Token 预算报告
workspace\DBA\review\audit-report.md              审计报告
```

## 下一步：校验模型抽取结果

```powershell
python .\scripts\bookwiki.py validate-extraction --book-root "G:\05-Study\13.LLMwiki\workspace\DBA" --input "G:\05-Study\13.LLMwiki\workspace\DBA\extracted\knowledge.batch-001.jsonl"
```

## 下一步：生成候选概念页

```powershell
python .\scripts\bookwiki.py compile-concepts --book-root "G:\05-Study\13.LLMwiki\workspace\DBA" --min-confidence 0.75
```

候选概念页输出到：

```text
workspace\DBA\review\candidates\
```

## 批量生成 AI 导学层

```powershell
python .\scripts\bookwiki.py compile-learning-guides --book-root "G:\05-Study\13.LLMwiki\workspace\DBA" --skip-existing
```

说明：

- `--skip-existing` 会保留已经人工或模型优化过的导学区。
- 生成报告：`workspace\DBA\review\learning-guide-report.json`。
- 规则生成适合做第一版全覆盖；重点章节建议再用大模型按 `chunks\learning-orders\*.json` 精修。

## 当前验证结果

- 证据块：594 个。
- 全书估算输入：326857 tokens。
- 单次整书阅读估算：至少 329857 tokens，质量不可控。
- 已生成批次清单，每批约 18000 tokens 以内。
- 审计：通过。

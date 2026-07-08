# 专业书籍 LLM Wiki 标准

标准版本：`bookwiki-standard-v1`

本标准用于约束任意 AI 大模型参与专业书籍转换时的行为，使不同模型、不同批次、不同会话的产出保持一致、可审计、可复现。

## 一句话原则

程序负责读全书、分块、建索引、做审计；大模型只负责在证据块内抽取结构化知识，不能直接改写原书或自由发挥。

## 固定阶段

| 阶段 | 名称 | 是否允许模型参与 | 产物 |
|---|---|---|---|
| P0 | ingest | 否 | `sources/source.md`, `state/source.json` |
| P1 | split | 否 | `sources/sections/*.md`, `state/sections.json` |
| P2 | chunk | 否 | `chunks/chunks.jsonl` |
| P3 | work-order | 否 | `chunks/work-orders/*.json`, `chunks/batches.md` |
| P4 | extract | 是 | `extracted/knowledge.batch-*.jsonl` |
| P5 | learning-guide | 是，但只能补导学层 | `chunks/learning-orders/*.json` |
| P6 | compile | 是，但只能使用已审计证据 | `review/candidates/*.md` |
| P7 | audit | 是/否均可，但必须结构化 | `review/*.json`, `review/audit-report.md` |
| P8 | publish | 否或人工确认 | `wiki/**/*.md` |

## 固定质量门禁

1. 无 `source_chunk` 的知识项不得进入 Wiki。
2. 无 `confidence` 的知识项不得进入 Wiki。
3. Markdown 表格型总结不得作为知识抽取结果。
4. AI 注释必须标记 `ai_note=true`，并放在“AI 注释”区。
5. 原书要点必须引用 chunk ID。
6. 概念页必须列出 `source_chunks`。
7. 审计报告出现 `ERROR` 时不得发布。
8. 模型不得读取整本书，只能读取 work-order 或已审计证据集合。
9. 阅读层必须拆成短文章，不能把 2 万到 12 万字符塞进单个主要阅读页。
10. AI 导学可以帮助零基础理解，但必须和原文分区，不能替代原文。

## 固定交接入口

任何模型接手项目时，必须按以下顺序读取标准文件：

```text
1. STANDARD.md
2. config/pipeline-standard.json
3. docs/model-execution-protocol.md
4. docs/quality-standard.md
5. workspace/<book>/pipeline-manifest.json
6. workspace/<book>/compliance-report.md
```

如果任务是抽取概念，还必须读取：

```text
workspace/<book>/chunks/batches.md
workspace/<book>/chunks/work-orders/<chunk_id>.json
```

如果任务是精修 AI 导学，还必须读取：

```text
workspace/<book>/chunks/learning-orders/<task>.json
```

模型完成固定交接读取前，不允许修改任何文件。

## 导学精修标准

导学精修必须遵守：

```text
docs/model-execution-protocol.md
docs/quality-standard.md
```

精修后必须运行：

```powershell
python .\scripts\bookwiki.py audit-learning-guides --book-root "workspace/<book>"
```

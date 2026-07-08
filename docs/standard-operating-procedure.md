# 标准作业流程 SOP

## 目标

把任意专业书籍转换为 Obsidian LLM Wiki，同时保证：

- 原文可追溯；
- 模型行为可约束；
- 输出格式可审计；
- 不同模型接手结果稳定一致。

## P0：输入登记

输入一本书的 Markdown、PDF 转 Markdown 或 EPUB 转 Markdown。

要求：

- 输入文件必须有固定路径。
- 生成 `state/source.json`，记录 hash、行数、估算 tokens、图片处理结果。
- `sources/source.md` 作为不可变证据基准。

## P1：结构切分

由程序按 Markdown 标题切分。

禁止：让模型生成目录或猜测章节。

产物：

```text
sources/sections/*.md
state/sections.json
```

## P2：证据分块

由程序按章节和 token 预算切分。

每个 chunk 必须包含：

```json
chunk_id, section_id, title, title_path, start_line, end_line, text, estimated_tokens, source_hash
```

## P3：模型任务单

由程序生成 `work-orders/*.json`。

模型只能读取任务单，不允许读取全书。

## P4：结构化抽取

模型角色：`extractor`。

输入：一个 work-order。

输出：JSON 数组或 JSONL。

禁止：

- Markdown；
- 表格；
- 总结全文；
- 外部知识；
- 无引用观点。

标准输出文件：

```text
extracted/knowledge.batch-001.jsonl
```

每行格式：

```json
{"chunk_id":"sec-0058-c01","items":[{"type":"definition","name":"数据库","text":"...","source_chunk":"sec-0058-c01","source_title":"...","source_lines":"631-642","confidence":0.95,"verbatim":true,"ai_note":false}]}
```

抽取完成后必须运行：

```powershell
python .\scripts\bookwiki.py validate-extraction --book-root "G:\05-Study\13.LLMwiki\workspace\DBA" --input "G:\05-Study\13.LLMwiki\workspace\DBA\extracted\knowledge.batch-001.jsonl"
```

只有校验 `PASS` 的 JSONL 才能进入下一步。

## P5：概念页编译

在概念页编译之前，阅读层还可以生成 AI 导学。

## P5A：AI 导学层

模型角色：`learning-guide`。

输入：`chunks/learning-orders/*.json`。

输出：只允许填充对应短文章的 `AI 导学` 区。

导学区必须包含：

- 本文适合解决的问题；
- 零基础解释；
- 关键概念；
- 学习顺序；
- 容易误解的点。

要求：

- 由浅入深；
- 每个关键结论引用 chunk ID；
- 不得改写原文；
- 不得把 AI 解释写成原书观点；
- 不得用表格替代主体解释。

## P6：概念页编译

模型角色：`compiler`。

输入：已通过格式校验的 evidence JSON。

输出：`review/candidates/*.md`。

要求：

- 原书定义必须引用 chunk。
- AI 注释必须隔离。
- `status` 默认为 `draft` 或 `needs_review`。

标准命令：

```powershell
python .\scripts\bookwiki.py compile-concepts --book-root "G:\05-Study\13.LLMwiki\workspace\DBA" --min-confidence 0.75
```

注意：概念页只生成到 `review/candidates/`，不得直接进入 `wiki/concepts/`。

## P7：Claim 审计

模型角色：`auditor`。

输入：候选页 + 被引用 chunk。

输出：结构化审计 JSON。

判定：

```text
supported
partially_supported
unsupported
contradicted
```

## P8：发布

发布只能移动已审核页面，不能重写内容。

允许进入 `wiki/` 的条件：

- 所有原书 claim 有 `source_chunk`；
- 审计无 `unsupported` 和 `contradicted`；
- 页面 frontmatter `status: reviewed`。

## 失败处理

如果模型输出不合规：

1. 保存到 `review/rejected/`。
2. 记录失败原因。
3. 使用同一 work-order 重新抽取。
4. 不得手工猜补来源。

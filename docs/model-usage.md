# 任意大模型使用说明

## 绝对禁止

不要把整本书发给模型，不要让模型“读完整本书后写一篇 LLM Wiki”。

禁止提示词：

```text
请阅读这本书并整理成 LLM Wiki。
```

这种方式会消耗数十万 token，并产生短表格、弱摘要、无证据内容。

## 正确提示词

每次只给模型一个任务单：

```text
你只能处理下面这个 work-order。
严格执行其中 prompt。
只输出 JSON 数组。
禁止输出 Markdown。
禁止输出表格。
禁止总结整本书。
如果没有可抽取内容，输出 []。
```

然后附上：

```text
workspace/<book>/chunks/work-orders/<chunk_id>.json
```

## 批处理提示词

如果模型支持读取本地文件，可以这样安排一个批次：

```text
读取 chunks/batches.md 中的 batch-001。
按其中列出的 work-order 逐个处理。
每个 work-order 输出一行 JSON：
{"chunk_id":"...","items":[...]}
禁止额外解释，禁止 Markdown 表格。
```

## 输出落盘位置

建议把模型输出保存为：

```text
workspace/<book>/extracted/knowledge.batch-001.jsonl
```

每一行格式：

```json
{"chunk_id":"sec-0058-c01","items":[{"type":"definition","name":"数据库","text":"...","source_chunk":"sec-0058-c01","source_title":"实战手记 > 1.1 什么是数据库","source_lines":"631-642","confidence":0.95,"verbatim":true,"ai_note":false}]}
```

## 质量拒绝规则

以下输出直接拒绝，不进入 `wiki/`：

- 没有 `source_chunk`。
- 输出为 Markdown 表格。
- 大量“本节主要介绍”空话。
- 引入原文没有的新概念或外部知识。
- 把 AI 理解写成原书观点。
- 缺少 `confidence`。

## 推荐节奏

一本 30 万 tokens 级别的书，不要一天内在同一会话里处理完。

建议：

1. 每次处理 1 个 batch。
2. 每个 batch 结束后立即保存 JSONL。
3. 清空上下文后再处理下一个 batch。
4. 概念页编译阶段只读取相关证据，不读取原书全文。

## AI 导学层

如果任务是让文章“更像教程、零基础能看懂”，不要让模型重写全文。应该读取：

```text
chunks/learning-orders/*.json
```

模型只填充文章中的 `AI 导学` 区，不能修改 `原文` 区。

导学输出必须包含：

- 本文适合解决的问题；
- 零基础解释；
- 关键概念；
- 学习顺序；
- 容易误解的点。

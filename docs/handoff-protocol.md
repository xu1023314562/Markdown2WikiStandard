# 跨模型交接协议

## 接手前必须读取

任意模型接手项目时，必须先读取以下文件：

```text
STANDARD.md
config/pipeline-standard.json
workspace/<book>/pipeline-manifest.json
workspace/<book>/compliance-report.md
workspace/<book>/chunks/batches.md
docs/model-usage.md
```

## 接手声明

模型开始工作前必须输出一句：

```text
我将只处理指定 work-order，不读取整本书，不输出 Markdown 表格，所有知识项必须包含 source_chunk。
```

## 任务边界

模型必须明确自己当前角色：

```text
extractor | compiler | auditor | publisher
```

不同角色不能混用。

## extractor 输出格式

每个 work-order 输出一行：

```json
{"chunk_id":"sec-0000-c00","items":[]}
```

## compiler 输出格式

只能写入：

```text
review/candidates/<concept>.md
```

不得直接写入：

```text
wiki/concepts/
```

## auditor 输出格式

只能输出 JSON：

```json
{"page":"...","verdict":"pass|fail","issues":[]}
```

## 交接完成条件

必须更新或说明：

- 已处理 batch ID；
- 输出文件路径；
- 失败 work-order；
- 是否触发质量门禁。

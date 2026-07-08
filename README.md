# 专业书籍 LLM Wiki 转换流水线

Markdown2WikiStandard：一套把专业书籍 Markdown 转换为证据型 Obsidian LLM Wiki 的标准化流水线。

目标：把专业书籍转换成 Obsidian 可浏览的 LLM Wiki，并保证所有知识页以原书为证据，不把 AI 总结当作原书事实。

## README 与 STANDARD 的分工

- `README.md`：给人看的项目入口，说明这个项目是什么、怎么快速运行、主要目录和命令是什么。
- `STANDARD.md`：给模型和流程看的强约束标准，定义固定阶段、交接顺序、质量门禁、禁止行为和审计要求。

简单说：人先看 `README.md`，模型先按 `STANDARD.md` 执行。README 可以解释和导航，STANDARD 负责约束和验收。

## 核心原则

1. 原文不可变：`workspace/<book>/sources/source.md` 是证据基准，AI 不得改写。
2. 证据先行：所有 Wiki 页面必须引用 `chunk_id`、章节、行号范围或页码。
3. AI 隔离：AI 解释只能写入“AI 注释”区，不能混入“原书要点”。
4. 低置信度进 review：缺引用、弱证据、疑似改写过度的内容不得进入正式页面。
5. 可重复构建：脚本根据原文 hash 生成状态文件，输出可被审计和重建。

## 目录结构

```text
workspace/<book>/
├── raw/                 # 原始输入副本
├── sources/             # 规范化原文，禁止 AI 改写
├── chunks/              # 章节/语义分块 JSONL
├── extracted/           # AI 或规则抽取的结构化知识
├── wiki/                # Obsidian 输出
│   ├── 00-Home.md
│   ├── chapters/
│   ├── concepts/
│   ├── glossary.md
│   └── source-map.md
├── review/              # 待审核候选和审计报告
├── state/               # hash、依赖、统计
└── attachments/         # 图片附件
```

## 快速验证

```powershell
python .\scripts\bookwiki.py build --source "G:\05-Study\07.BooksLearning\数据库\DBA.md" --out "G:\05-Study\13.LLMwiki" --book "DBA"
```

默认每个证据块控制在约 1800 tokens 内，可用 `--max-tokens` 调整：

```powershell
python .\scripts\bookwiki.py build --source "G:\05-Study\07.BooksLearning\数据库\DBA.md" --out "G:\05-Study\13.LLMwiki" --book "DBA" --max-tokens 1400
```

构建完成后，用 Obsidian 打开：

```text
G:\05-Study\13.LLMwiki\workspace\DBA\wiki
```

## 流水线阶段

1. `ingest`：复制原书 Markdown，重写图片到 `attachments/`，记录 source hash。
2. `split`：按 Markdown 标题切分为章节片段，保留原始行号范围。
3. `chunk`：按章节和长度生成证据块，每个块有稳定 `chunk_id`。
4. `compile`：生成 Obsidian 首页、章节页、术语表、证据地图。
5. `audit`：检查源文件、chunk、章节页、引用覆盖率、图片引用和 Obsidian 链接。

## Token 控制

本流水线禁止“让模型读完整本书”。脚本会生成 `chunks/work-orders/*.json`，每个任务单只包含一个 chunk、一个提示词、一个输出上限。模型只允许读取任务单并输出 JSON 数组。

同时会生成 `chunks/batches.md`，把任务单按预算分批。建议一个会话只处理一个批次，处理完成立刻落盘，避免消耗长上下文。

详见：`docs/token-control.md`。

给任意大模型使用时，直接按 `docs/model-usage.md` 执行，不要让模型读取整本书。

## 固化流程文档

- `STANDARD.md`：总标准。
- `docs/operator-guide.md`：人工操作手册。
- `docs/model-execution-protocol.md`：大模型精修导学的执行协议。
- `docs/quality-standard.md`：质量验收标准。
- `docs/runbook.md`：命令手册。

## AI 接入方式

本项目不绑定任何模型。任意 AI 大模型只需要遵守 `prompts/` 下的输出协议：

- `extract_knowledge.md`：从 chunk 中抽取概念、定义、主张、步骤、案例。
- `compile_concept_page.md`：根据结构化证据生成概念页。
- `audit_claims.md`：检查页面中的 claim 是否被原文支持。

推荐流程是：先运行离线 `build` 生成证据骨架，再把 `chunks/chunks.jsonl` 分批交给任意模型抽取 JSONL，最后再编译概念页并审计。

## 质量门禁

正式进入 `wiki/` 的内容必须满足：

- 每个原书要点必须带 `chunk_id`。
- 每个概念页必须列出来源块。
- 不能出现“原书认为”但无引用的句子。
- AI 注释必须单独标识。
- 审计报告无 `ERROR`。

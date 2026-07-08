# 工作流说明

## 核查

确认输入 Markdown 存在、标题层级可识别、图片引用可定位。

## 修改

运行 `bookwiki.py build` 创建工作区、证据块和 Obsidian Wiki 骨架。

## 验证

查看 `review/audit-report.md`。只有审计无 `ERROR` 的结果才可作为正式输出。

## 后续 AI 增强

1. 将 `chunks/chunks.jsonl` 分批交给模型，使用 `prompts/extract_knowledge.md`。
2. 合并模型输出到 `extracted/knowledge.jsonl`。
3. 使用 `prompts/compile_concept_page.md` 生成候选概念页。
4. 使用 `prompts/audit_claims.md` 审计候选页。
5. 人工确认后从 `review/candidates/` 移入 `wiki/concepts/`。

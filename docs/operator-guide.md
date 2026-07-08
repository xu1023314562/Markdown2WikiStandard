# 操作手册：专业书籍 LLM Wiki 转换

## 1. 构建工作区

```powershell
cd G:\05-Study\13.LLMwiki
python .\scripts\bookwiki.py build --source "G:\05-Study\07.BooksLearning\数据库\DBA实战手记.md" --out "G:\05-Study\13.LLMwiki" --book "DBA实战手记" --max-tokens 1600
```

生成：

```text
workspace/<book>/wiki/00-Home.md
workspace/<book>/wiki/reading/
workspace/<book>/wiki/articles/
workspace/<book>/chunks/learning-orders/
```

## 2. 生成第一版 AI 导学

```powershell
python .\scripts\bookwiki.py compile-learning-guides --book-root "G:\05-Study\13.LLMwiki\workspace\DBA实战手记" --skip-existing
```

用途：全书先获得统一结构，不追求最终表达质量。

## 3. 选择重点文章精修

优先选择：

- 概念密集文章；
- 读者难懂文章；
- 图片/案例较多文章；
- 后续会作为知识页源头的文章。

给模型前必须附上：

```text
docs/model-execution-protocol.md
```

并要求模型只改 `AI 导学` 区。

## 4. 审计导学质量

```powershell
python .\scripts\bookwiki.py audit-learning-guides --book-root "G:\05-Study\13.LLMwiki\workspace\DBA实战手记"
```

输出：

```text
review/learning-guide-audit.md
review/learning-guide-audit.json
```

## 5. 人工抽查

抽查标准：

- 首页是否只展示阅读入口；
- 文章是否短到可以一次读完；
- 图片是否显示；
- AI 导学是否能帮助零基础理解；
- 原文区是否未被修改；
- 每个关键解释是否有 chunk 来源。

## 6. 发布

只有通过审计和人工抽查的文章，才作为正式 Obsidian 阅读资料。

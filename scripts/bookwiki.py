#!/usr/bin/env python3
"""Evidence-first professional book to Obsidian wiki pipeline.

This script is intentionally model-agnostic. It prepares evidence chunks,
token budgets, model work orders, an Obsidian wiki skeleton, and an audit
report. LLMs should consume only the generated work orders, not the whole book.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass
class Section:
    section_id: str
    level: int
    title: str
    title_path: list[str]
    start_line: int
    end_line: int
    text: str


@dataclass
class Chunk:
    chunk_id: str
    section_id: str
    title: str
    title_path: list[str]
    start_line: int
    end_line: int
    text: str
    char_count: int
    estimated_tokens: int
    source_file: str
    source_hash: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8")).hex() if False else hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_dirs(root: Path) -> None:
    for rel in [
        "raw",
        "sources/sections",
        "chunks/work-orders",
        "chunks/learning-orders",
        "extracted",
        "wiki/_attachments/images",
        "wiki/articles",
        "wiki/reading",
        "wiki/chapters",
        "wiki/concepts",
        "review/candidates",
        "state",
        "attachments/images",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def estimate_tokens(text: str) -> int:
    # Conservative mixed Chinese/English estimate. Used for budgeting, not billing.
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    non_cjk = len(text) - cjk
    return int(cjk * 1.15 + non_cjk / 4) + 1


def safe_name(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:max_len].strip(" .") or "untitled")


def copy_and_rewrite_images(source: Path, text: str, book_root: Path) -> tuple[str, list[dict]]:
    image_records: list[dict] = []

    def repl(match: re.Match[str]) -> str:
        alt = match.group(1)
        raw_target = match.group(2).strip()
        if re.match(r"^[a-zA-Z]+://", raw_target):
            image_records.append({"original": raw_target, "copied": None, "status": "remote_unmodified"})
            return match.group(0)
        image_path = (source.parent / raw_target).resolve()
        if not image_path.exists():
            image_records.append({"original": raw_target, "copied": None, "status": "missing"})
            return match.group(0)
        data = image_path.read_bytes()
        digest = sha256_bytes(data)[:16]
        suffix = image_path.suffix.lower() or ".img"
        dest = book_root / "attachments" / "images" / f"{digest}{suffix}"
        if not dest.exists():
            shutil.copy2(image_path, dest)
        wiki_dest = book_root / "wiki" / "_attachments" / "images" / dest.name
        wiki_dest.parent.mkdir(parents=True, exist_ok=True)
        if not wiki_dest.exists():
            shutil.copy2(image_path, wiki_dest)
        rel = f"../attachments/images/{dest.name}"
        image_records.append({"original": raw_target, "copied": str(dest.relative_to(book_root)), "status": "copied"})
        return f"![{alt}]({rel})"

    return IMAGE_RE.sub(repl, text), image_records


def ingest(source: Path, book_root: Path) -> dict:
    ensure_dirs(book_root)
    raw_copy = book_root / "raw" / source.name
    if source.resolve() != raw_copy.resolve():
        shutil.copy2(source, raw_copy)
    original = source.read_text(encoding="utf-8")
    normalized, images = copy_and_rewrite_images(source, original, book_root)
    source_file = book_root / "sources" / "source.md"
    source_file.write_text(normalized, encoding="utf-8")
    meta = {
        "source_path": str(source),
        "raw_copy": str(raw_copy.relative_to(book_root)),
        "source_file": str(source_file.relative_to(book_root)),
        "source_hash": sha256_text(original),
        "normalized_hash": sha256_text(normalized),
        "line_count": len(normalized.splitlines()),
        "char_count": len(normalized),
        "estimated_tokens": estimate_tokens(normalized),
        "images": images,
    }
    (book_root / "state" / "source.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def split_sections(book_root: Path) -> list[Section]:
    source_file = book_root / "sources" / "source.md"
    lines = source_file.read_text(encoding="utf-8").splitlines()
    headings: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines, 1):
        match = HEADING_RE.match(line)
        if match:
            headings.append((idx, len(match.group(1)), match.group(2).strip()))
    if not headings or headings[0][0] != 1:
        headings.insert(0, (1, 1, "未命名开篇"))

    sections: list[Section] = []
    path_stack: list[tuple[int, str]] = []
    for i, (start, level, title) in enumerate(headings):
        end = headings[i + 1][0] - 1 if i + 1 < len(headings) else len(lines)
        path_stack = [(lvl, t) for lvl, t in path_stack if lvl < level]
        path_stack.append((level, title))
        title_path = [t for _, t in path_stack]
        text = "\n".join(lines[start - 1 : end]).strip() + "\n"
        section_id = f"sec-{i + 1:04d}"
        sections.append(Section(section_id, level, title, title_path, start, end, text))

    sections_dir = book_root / "sources" / "sections"
    for section in sections:
        name = f"{section.section_id}-{safe_name(section.title)}.md"
        frontmatter = (
            "---\n"
            f"type: source-section\n"
            f"section_id: {section.section_id}\n"
            f"title: {json.dumps(section.title, ensure_ascii=False)}\n"
            f"start_line: {section.start_line}\n"
            f"end_line: {section.end_line}\n"
            "---\n\n"
        )
        (sections_dir / name).write_text(frontmatter + section.text, encoding="utf-8")
    (book_root / "state" / "sections.json").write_text(
        json.dumps([asdict(s) | {"text": ""} for s in sections], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return sections


def chunk_sections(book_root: Path, sections: list[Section], max_tokens: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    source_hash = json.loads((book_root / "state" / "source.json").read_text(encoding="utf-8"))["normalized_hash"]
    for section in sections:
        paragraphs = re.split(r"\n\s*\n", section.text.strip())
        current: list[str] = []
        chunk_start = section.start_line
        part = 1
        line_cursor = section.start_line
        for paragraph in paragraphs:
            candidate = ("\n\n".join(current + [paragraph])).strip()
            if current and estimate_tokens(candidate) > max_tokens:
                chunk_text = "\n\n".join(current).strip() + "\n"
                end_line = line_cursor - 1
                chunks.append(make_chunk(section, part, chunk_start, end_line, chunk_text, source_hash))
                part += 1
                current = [paragraph]
                chunk_start = line_cursor
            else:
                current.append(paragraph)
            line_cursor += paragraph.count("\n") + 2
        if current:
            chunk_text = "\n\n".join(current).strip() + "\n"
            chunks.append(make_chunk(section, part, chunk_start, section.end_line, chunk_text, source_hash))

    chunks_file = book_root / "chunks" / "chunks.jsonl"
    with chunks_file.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
    generate_work_orders(book_root, chunks)
    return chunks


def make_chunk(section: Section, part: int, start_line: int, end_line: int, text: str, source_hash: str) -> Chunk:
    chunk_id = f"{section.section_id}-c{part:02d}"
    return Chunk(
        chunk_id=chunk_id,
        section_id=section.section_id,
        title=section.title,
        title_path=section.title_path,
        start_line=start_line,
        end_line=end_line,
        text=text,
        char_count=len(text),
        estimated_tokens=estimate_tokens(text),
        source_file="sources/source.md",
        source_hash=source_hash,
    )


def generate_work_orders(book_root: Path, chunks: list[Chunk]) -> None:
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "extract_knowledge.md"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    for chunk in chunks:
        work_order = {
            "instruction": "只对本 chunk 做结构化知识抽取。禁止总结整本书。禁止输出长文章。只输出 JSON 数组。",
            "token_budget": {
                "input_estimated_tokens": chunk.estimated_tokens,
                "output_max_tokens": 900,
                "hard_rule": "如果无法抽取，输出 []，不要凑内容。",
            },
            "prompt": prompt,
            "chunk": asdict(chunk),
        }
        target = book_root / "chunks" / "work-orders" / f"{chunk.chunk_id}.json"
        target.write_text(json.dumps(work_order, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_batches(book_root, chunks)


def generate_batches(book_root: Path, chunks: list[Chunk], max_batch_tokens: int = 18000) -> None:
    batches: list[dict] = []
    current: list[Chunk] = []
    current_tokens = 0
    for chunk in chunks:
        projected = current_tokens + chunk.estimated_tokens + 900
        if current and projected > max_batch_tokens:
            batches.append(batch_record(len(batches) + 1, current))
            current = []
            current_tokens = 0
        current.append(chunk)
        current_tokens += chunk.estimated_tokens + 900
    if current:
        batches.append(batch_record(len(batches) + 1, current))
    (book_root / "chunks" / "batches.json").write_text(json.dumps(batches, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 模型处理批次清单",
        "",
        "每批包含若干 work-order。建议一次会话只处理 1 个批次，处理完立刻把 JSONL 结果落盘。",
        "",
    ]
    for batch in batches:
        lines.append(f"## {batch['batch_id']}")
        lines.append("")
        lines.append(f"- 任务数：{batch['count']}")
        lines.append(f"- 估算总 tokens：{batch['estimated_total_tokens']}")
        lines.append("- 任务单：")
        for item in batch["work_orders"]:
            lines.append(f"  - `{item}`")
        lines.append("")
    (book_root / "chunks" / "batches.md").write_text("\n".join(lines), encoding="utf-8")


def batch_record(index: int, chunks: list[Chunk]) -> dict:
    return {
        "batch_id": f"batch-{index:03d}",
        "count": len(chunks),
        "estimated_input_tokens": sum(c.estimated_tokens for c in chunks),
        "estimated_output_budget": 900 * len(chunks),
        "estimated_total_tokens": sum(c.estimated_tokens for c in chunks) + 900 * len(chunks),
        "work_orders": [f"chunks/work-orders/{c.chunk_id}.json" for c in chunks],
    }


def wiki_link(path: str, label: str | None = None) -> str:
    return f"[[{path}|{label}]]" if label else f"[[{path}]]"


def compile_wiki(book_root: Path, book: str, chunks: list[Chunk]) -> None:
    wiki = book_root / "wiki"
    by_section: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        by_section.setdefault(chunk.section_id, []).append(chunk)

    reading_pages = compile_reading_pages(book_root, book, chunks)
    home_lines = [
        "---",
        "type: home",
        f"book: {book}",
        "status: generated",
        "---",
        "",
        f"# {book} LLM Wiki",
        "",
        "> 这是以原书为证据的知识编译系统输出。AI 只能在候选页中补充解释，不能覆盖原文证据。",
        "",
        "## 导航",
        "",
        "- [[glossary|术语表]]",
        "- [[source-map|证据地图]]",
        "- [[token-budget|Token 预算报告]]",
        "- [[../compliance-report|标准合规报告]]",
        "",
        "## 阅读入口",
        "",
    ]
    for rel, title, token_count in reading_pages:
        home_lines.append(f"- {wiki_link(rel, title)}（约 {token_count} tokens）")
    home_lines.extend([
        "",
        "## 机器证据层",
        "",
        "> 以下文件供审计和模型任务使用，不建议作为人工阅读入口。",
        "",
        "- `../chunks/chunks.jsonl`：细粒度证据块",
        "- `../chunks/work-orders/`：模型任务单",
        "- `../chunks/batches.md`：批次清单",
        "- [[source-map|证据地图]]：需要追溯时从这里查 chunk，不在首页展开碎片页",
        "",
    ])

    for idx, (section_id, section_chunks) in enumerate(by_section.items(), 1):
        title = section_chunks[0].title
        file_stem = f"{section_id}-{safe_name(title)}"
        rel_link = f"chapters/{file_stem}"
        chapter_lines = [
            "---",
            "type: chapter",
            f"section_id: {section_id}",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            "status: generated",
            "---",
            "",
            f"# {title}",
            "",
            "## 证据块",
            "",
        ]
        for chunk in section_chunks:
            chapter_lines.append(
                f"- `{chunk.chunk_id}` 行 {chunk.start_line}-{chunk.end_line}，约 {chunk.estimated_tokens} tokens"
            )
        chapter_lines.extend([
            "",
            "## 原文摘录",
            "",
            "> 本区只展示截断摘录，完整证据见 `sources/source.md` 和 `chunks/chunks.jsonl`。",
            "",
        ])
        excerpt = section_chunks[0].text[:1800].strip()
        chapter_lines.append("```text")
        chapter_lines.append(excerpt)
        chapter_lines.append("```")
        chapter_lines.extend([
            "",
            "## AI 注释",
            "",
            "> 待人工审核后补充。此区内容不等同于原书原文。",
            "",
        ])
        (wiki / "chapters" / f"{file_stem}.md").write_text("\n".join(chapter_lines), encoding="utf-8")

    (wiki / "00-Home.md").write_text("\n".join(home_lines) + "\n", encoding="utf-8")
    compile_source_map(book_root, chunks)
    compile_glossary(book_root, chunks)
    compile_token_budget(book_root, chunks)


def compile_reading_pages(book_root: Path, book: str, chunks: list[Chunk]) -> list[tuple[str, str, int]]:
    groups = reading_groups(chunks)
    reading_dir = book_root / "wiki" / "reading"
    articles_dir = book_root / "wiki" / "articles"
    learning_dir = book_root / "chunks" / "learning-orders"
    for generated_dir in [reading_dir, articles_dir, learning_dir]:
        if generated_dir.exists():
            shutil.rmtree(generated_dir)
        generated_dir.mkdir(parents=True, exist_ok=True)
    pages: list[tuple[str, str, int]] = []
    for idx, group in enumerate(groups, 1):
        title = group["title"]
        group_chunks: list[Chunk] = group["chunks"]
        file_stem = f"{idx:02d}-{safe_name(title)}"
        token_count = sum(c.estimated_tokens for c in group_chunks)
        article_pages = compile_article_pages(book_root, idx, title, group_chunks)
        lines = [
            "---",
            "type: reading-index",
            f"book: {book}",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            "status: generated",
            "standard: bookwiki-standard-v1",
            "---",
            "",
            f"# {title}",
            "",
            "## 阅读说明",
            "",
            "> 这是本章阅读索引。正文已拆成多篇短文章，适合逐篇阅读；每篇仍保留原文证据块编号。",
            "",
            "## 证据范围",
            "",
            f"- 证据块数量：{len(group_chunks)}",
            f"- 估算 tokens：{token_count}",
            f"- 起止行：{group_chunks[0].start_line}-{group_chunks[-1].end_line}",
            "",
            "## 短文章",
            "",
        ]
        for rel, article_title, article_tokens in article_pages:
            lines.append(f"- {wiki_link(rel, article_title)}（约 {article_tokens} tokens）")
        lines.extend(["", "## 本章结构", ""])
        seen_titles: set[str] = set()
        for chunk in group_chunks:
            path = " > ".join(chunk.title_path)
            if path not in seen_titles:
                seen_titles.add(path)
                lines.append(f"- {path}（`{chunk.chunk_id}`）")
        (reading_dir / f"{file_stem}.md").write_text("\n".join(lines), encoding="utf-8")
        pages.append((f"reading/{file_stem}", title, token_count))
    return pages


def compile_article_pages(book_root: Path, chapter_index: int, chapter_title: str, chunks: list[Chunk], max_article_tokens: int = 5200) -> list[tuple[str, str, int]]:
    articles: list[list[Chunk]] = []
    current: list[Chunk] = []
    current_tokens = 0
    for chunk in chunks:
        projected = current_tokens + chunk.estimated_tokens
        if current and projected > max_article_tokens:
            articles.append(current)
            current = []
            current_tokens = 0
        current.append(chunk)
        current_tokens += chunk.estimated_tokens
    if current:
        articles.append(current)

    results: list[tuple[str, str, int]] = []
    chapter_dir = book_root / "wiki" / "articles" / f"{chapter_index:02d}-{safe_name(chapter_title)}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    for article_index, article_chunks in enumerate(articles, 1):
        first_title = article_chunks[0].title
        last_title = article_chunks[-1].title
        if first_title == last_title:
            article_title = first_title
        else:
            article_title = f"{first_title} 到 {last_title}"
        file_stem = f"{article_index:02d}-{safe_name(article_title)}"
        token_count = sum(c.estimated_tokens for c in article_chunks)
        source_chunks = [c.chunk_id for c in article_chunks]
        rel = f"articles/{chapter_index:02d}-{safe_name(chapter_title)}/{file_stem}"
        lines = [
            "---",
            "type: learning-article",
            f"chapter: {json.dumps(chapter_title, ensure_ascii=False)}",
            f"title: {json.dumps(article_title, ensure_ascii=False)}",
            "status: generated",
            "standard: bookwiki-standard-v1",
            "source_chunks:",
        ]
        lines.extend(f"  - {chunk_id}" for chunk_id in source_chunks)
        lines.extend([
            "---",
            "",
            f"# {article_title}",
            "",
            "## AI 导学",
            "",
            "> 待根据 `chunks/learning-orders/` 对应任务单生成。导学内容必须由浅入深，不能替代原文。",
            "",
            "### 本文适合解决的问题",
            "",
            "- 待生成",
            "",
            "### 零基础解释",
            "",
            "- 待生成",
            "",
            "### 学习顺序",
            "",
            "- 先读 AI 导学，再读原文，最后查看证据块编号。",
            "",
            "## 证据范围",
            "",
            f"- 所属章节：{chapter_title}",
            f"- 估算 tokens：{token_count}",
            f"- 起止行：{article_chunks[0].start_line}-{article_chunks[-1].end_line}",
            "- 证据块：" + ", ".join(f"`{c}`" for c in source_chunks),
            "",
            "## 原文",
            "",
        ])
        for chunk in article_chunks:
            lines.append(f"<!-- chunk:{chunk.chunk_id} lines:{chunk.start_line}-{chunk.end_line} -->")
            lines.append(rewrite_wiki_image_paths(chunk.text.strip()))
            lines.append("")
        (chapter_dir / f"{file_stem}.md").write_text("\n".join(lines), encoding="utf-8")
        write_learning_order(book_root, rel, article_title, chapter_title, article_chunks)
        results.append((rel, article_title, token_count))
    return results


def rewrite_wiki_image_paths(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        path = match.group(2)
        filename = Path(path).name
        return f"![[ _attachments/images/{filename}]]".replace("[[ ", "[[")

    text = text.replace("../attachments/images/", "_attachments/images/")
    return IMAGE_RE.sub(repl, text)


def write_learning_order(book_root: Path, rel: str, article_title: str, chapter_title: str, chunks: list[Chunk]) -> None:
    order = {
        "instruction": "为指定短文章生成 AI 导学层。不得改写原文，不得删除证据。输出 Markdown 片段，只包含 AI 导学区内容。",
        "output_sections": ["本文适合解决的问题", "零基础解释", "关键概念", "学习顺序", "容易误解的点"],
        "quality_rules": [
            "用零基础读者能理解的语言解释。",
            "必须引用 source_chunks。",
            "不能把 AI 解释写成原书原意。",
            "不要输出表格作为主体。",
            "每个结论后标注证据 chunk_id。",
        ],
        "target_article": rel,
        "article_title": article_title,
        "chapter_title": chapter_title,
        "source_chunks": [asdict(c) for c in chunks],
    }
    digest = sha256_text(rel)[:10]
    target = book_root / "chunks" / "learning-orders" / f"{digest}.json"
    target.write_text(json.dumps(order, ensure_ascii=False, indent=2), encoding="utf-8")


def reading_groups(chunks: list[Chunk]) -> list[dict]:
    # Build human-readable pages by grouping real body content into major chapters.
    body_chunks = [c for c in chunks if c.start_line >= detect_body_start(chunks)]
    title_map = chapter_title_map(chunks)
    groups: list[dict] = []
    current: dict | None = None
    for idx, chunk in enumerate(body_chunks):
        title = chunk.title.strip()
        is_major = bool(re.match(r"^(第\s*\d+\s*章|第\d+章|附录|漫谈数据库$)", title))
        if is_major or current is None:
            current = {"title": normalize_reading_title(title, title_map), "chunks": []}
            groups.append(current)
        current["chunks"].append(chunk)
    return [g for g in groups if sum(c.estimated_tokens for c in g["chunks"]) > 300]


def chapter_title_map(chunks: list[Chunk]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for chunk in chunks:
        title = chunk.title.strip()
        match = re.match(r"^第\s*(\d+)\s*章\s+(.+?)\s*\d*$", title)
        if match:
            num, name = match.group(1), match.group(2).strip()
            mapping[num] = f"第 {num} 章 {name}"
    return mapping


def detect_body_start(chunks: list[Chunk]) -> int:
    # TOC entries in many converted books appear before the first real body section.
    for chunk in chunks:
        if chunk.title in {"漫谈数据库", "第1章", "第 1 章"} or chunk.title.startswith("1.1 "):
            return max(1, chunk.start_line - 40)
    return 1


def normalize_reading_title(title: str, title_map: dict[str, str]) -> str:
    title = title.strip()
    if title == "漫谈数据库":
        return "第 1 章 漫谈数据库"
    bare = re.match(r"^第\s*(\d+)\s*章$", title)
    if bare:
        return title_map.get(bare.group(1), f"第 {bare.group(1)} 章")
    return title


def load_standard() -> dict:
    standard_path = Path(__file__).resolve().parents[1] / "config" / "pipeline-standard.json"
    if standard_path.exists():
        return json.loads(standard_path.read_text(encoding="utf-8"))
    return {"standard_version": "bookwiki-standard-v1", "required_artifacts": [], "quality_gates": []}


def compile_standard_reports(book_root: Path, book: str, chunks: list[Chunk]) -> None:
    standard = load_standard()
    source_meta = json.loads((book_root / "state" / "source.json").read_text(encoding="utf-8"))
    token_meta = json.loads((book_root / "state" / "token-budget.json").read_text(encoding="utf-8"))
    manifest = {
        "standard_version": standard.get("standard_version", "bookwiki-standard-v1"),
        "book": book,
        "book_root": str(book_root),
        "source": source_meta,
        "token_budget": token_meta,
        "artifacts": {
            "source": "sources/source.md",
            "sections": "sources/sections/*.md",
            "chunks": "chunks/chunks.jsonl",
            "work_orders": "chunks/work-orders/*.json",
            "batches": "chunks/batches.md",
            "wiki_home": "wiki/00-Home.md",
            "source_map": "wiki/source-map.md",
            "token_budget_report": "wiki/token-budget.md",
            "audit_report": "review/audit-report.md",
        },
        "model_contract": {
            "must_read": [
                "STANDARD.md",
                "config/pipeline-standard.json",
                "pipeline-manifest.json",
                "compliance-report.md",
                "chunks/batches.md",
            ],
            "forbidden": [
                "full_book_prompting",
                "markdown_table_extraction",
                "uncited_claims",
                "direct_publish_to_wiki_concepts",
            ],
            "allowed_roles": standard.get("model_roles", {}),
        },
    }
    (book_root / "pipeline-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    checks = compliance_checks(book_root, standard)
    status = "通过" if all(item["status"] == "PASS" for item in checks) else "失败"
    lines = [
        "# 标准合规报告",
        "",
        f"- 标准版本：`{manifest['standard_version']}`",
        f"- 书籍：{book}",
        f"- 状态：{status}",
        "",
        "## 工件检查",
        "",
    ]
    for item in checks:
        lines.append(f"- {item['status']} `{item['path']}`：{item['message']}")
    lines.extend([
        "",
        "## 模型接手规则",
        "",
        "1. 先读 `pipeline-manifest.json` 和本报告。",
        "2. 只处理 `chunks/work-orders/*.json`。",
        "3. 只输出 JSON 数组或 JSONL。",
        "4. 不得输出 Markdown 表格作为抽取结果。",
        "5. 不得直接写入 `wiki/concepts/`。",
    ])
    (book_root / "compliance-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def compliance_checks(book_root: Path, standard: dict) -> list[dict]:
    checks: list[dict] = []
    for rel in standard.get("required_artifacts", []):
        if rel == "compliance-report.md":
            checks.append({"path": rel, "status": "PASS", "message": "本次构建生成"})
            continue
        path = book_root / rel
        exists = path.exists()
        checks.append({
            "path": rel,
            "status": "PASS" if exists else "FAIL",
            "message": "存在" if exists else "缺失",
        })
    return checks


def compile_source_map(book_root: Path, chunks: list[Chunk]) -> None:
    lines = ["---", "type: source-map", "status: generated", "---", "", "# 证据地图", ""]
    for chunk in chunks:
        path = " > ".join(chunk.title_path)
        lines.append(f"- `{chunk.chunk_id}`：{path}，行 {chunk.start_line}-{chunk.end_line}，约 {chunk.estimated_tokens} tokens")
    (book_root / "wiki" / "source-map.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def compile_glossary(book_root: Path, chunks: list[Chunk]) -> None:
    # Deterministic seed glossary. Real concepts should come from reviewed extracted/knowledge.jsonl.
    candidates: dict[str, set[str]] = {}
    terms = ["DBA", "Oracle", "MySQL", "PostgreSQL", "SQL", "HTAP", "CAP", "Redis", "Elasticsearch", "OceanBase", "TiDB"]
    for chunk in chunks:
        for term in terms:
            if term.lower() in chunk.text.lower():
                candidates.setdefault(term, set()).add(chunk.chunk_id)
    lines = ["---", "type: glossary", "status: generated", "---", "", "# 术语表", ""]
    for term, refs in sorted(candidates.items()):
        joined = ", ".join(sorted(refs)[:12])
        lines.append(f"- **{term}**：出现于 `{joined}`")
    lines.append("")
    lines.append("> 注：本术语表为规则生成的种子索引，不代表完整概念页。正式概念页必须经过 AI 抽取和审计。")
    (book_root / "wiki" / "glossary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def compile_token_budget(book_root: Path, chunks: list[Chunk]) -> None:
    total_input = sum(c.estimated_tokens for c in chunks)
    naive_full_book_round = total_input + 3000
    work_order_input = sum(min(c.estimated_tokens, c.estimated_tokens) for c in chunks)
    lines = [
        "---",
        "type: token-budget",
        "status: generated",
        "---",
        "",
        "# Token 预算报告",
        "",
        f"- 证据块数量：{len(chunks)}",
        f"- 全书估算输入 tokens：{total_input}",
        f"- 单次整书阅读估算成本：至少 {naive_full_book_round} tokens，且质量不可控",
        f"- 推荐单 chunk 输入上限：见 `chunks/work-orders/*.json`",
        "- 推荐单 chunk 输出上限：900 tokens",
        "- 批次清单：`chunks/batches.md`，默认每批约 18000 tokens 以内",
        "",
        "## 控制策略",
        "",
        "1. 模型不得读整本书，只读一个 work-order。",
        "2. 模型不得输出文章，只输出 JSON 数组。",
        "3. 无可抽取内容时输出 `[]`，禁止凑表格。",
        "4. 概念页只由已审计 JSON 证据编译。",
        "5. 查询时先读 `00-Home.md` 和 `source-map.md`，再定位 chunk，不回读全书。",
        "",
        "## 分块明细",
        "",
    ]
    for chunk in chunks:
        lines.append(f"- `{chunk.chunk_id}`：{chunk.estimated_tokens} tokens，行 {chunk.start_line}-{chunk.end_line}，{chunk.title}")
    (book_root / "wiki" / "token-budget.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (book_root / "state" / "token-budget.json").write_text(
        json.dumps({"chunks": len(chunks), "estimated_input_tokens": total_input, "output_max_tokens_per_chunk": 900}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def audit(book_root: Path, chunks: list[Chunk]) -> list[str]:
    messages: list[str] = []
    source = book_root / "sources" / "source.md"
    if not source.exists():
        messages.append("ERROR: missing sources/source.md")
    if not chunks:
        messages.append("ERROR: no chunks generated")
    missing_work_orders = [c.chunk_id for c in chunks if not (book_root / "chunks" / "work-orders" / f"{c.chunk_id}.json").exists()]
    if missing_work_orders:
        messages.append(f"ERROR: missing work orders: {', '.join(missing_work_orders[:10])}")
    if not (book_root / "chunks" / "batches.json").exists():
        messages.append("ERROR: missing chunks/batches.json")
    for chunk in chunks:
        if chunk.estimated_tokens > 2600:
            messages.append(f"WARN: chunk {chunk.chunk_id} estimated tokens {chunk.estimated_tokens} exceeds recommended budget")
    copied_images = json.loads((book_root / "state" / "source.json").read_text(encoding="utf-8")).get("images", [])
    missing_images = [img for img in copied_images if img.get("status") == "missing"]
    if missing_images:
        messages.append(f"WARN: missing images: {len(missing_images)}")
    if not messages:
        messages.append("OK: audit passed")
    report = ["# 审计报告", "", f"- 状态：{'失败' if any(m.startswith('ERROR') for m in messages) else '通过'}", "", "## 检查结果", ""]
    report.extend(f"- {m}" for m in messages)
    report.extend([
        "",
        "## 质量说明",
        "",
        "本审计只保证证据骨架、分块、任务单和 Obsidian 输出完整。AI 生成的概念页仍需执行 claim 审计和人工确认。",
    ])
    (book_root / "review" / "audit-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return messages


REQUIRED_ITEM_FIELDS = {
    "type",
    "name",
    "text",
    "source_chunk",
    "source_title",
    "source_lines",
    "confidence",
    "verbatim",
    "ai_note",
}


def validate_extraction(args: argparse.Namespace) -> None:
    book_root = Path(args.book_root).resolve()
    input_file = Path(args.input).resolve()
    chunks = {c.chunk_id: c for c in load_chunks(book_root)}
    issues: list[dict] = []
    valid_records: list[dict] = []
    for line_no, line in enumerate(input_file.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append({"line": line_no, "severity": "ERROR", "message": f"JSON 解析失败: {exc}"})
            continue
        chunk_id = record.get("chunk_id")
        if chunk_id not in chunks:
            issues.append({"line": line_no, "severity": "ERROR", "message": f"未知 chunk_id: {chunk_id}"})
        items = record.get("items")
        if not isinstance(items, list):
            issues.append({"line": line_no, "severity": "ERROR", "message": "items 必须是数组"})
            continue
        for index, item in enumerate(items):
            validate_item(item, chunk_id, line_no, index, issues)
        valid_records.append(record)

    status = "PASS" if not any(i["severity"] == "ERROR" for i in issues) else "FAIL"
    out_json = book_root / "review" / f"extraction-validation-{input_file.stem}.json"
    out_md = book_root / "review" / f"extraction-validation-{input_file.stem}.md"
    out_json.write_text(json.dumps({"status": status, "issues": issues}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 抽取结果校验", "", f"- 输入：`{input_file}`", f"- 状态：{status}", "", "## 问题", ""]
    if issues:
        for issue in issues:
            lines.append(f"- {issue['severity']} line {issue['line']}：{issue['message']}")
    else:
        lines.append("- 无")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "issues": len(issues), "report": str(out_md)}, ensure_ascii=False, indent=2))


def validate_item(item: object, chunk_id: str, line_no: int, index: int, issues: list[dict]) -> None:
    if not isinstance(item, dict):
        issues.append({"line": line_no, "severity": "ERROR", "message": f"items[{index}] 不是对象"})
        return
    missing = sorted(REQUIRED_ITEM_FIELDS - set(item.keys()))
    if missing:
        issues.append({"line": line_no, "severity": "ERROR", "message": f"items[{index}] 缺字段: {', '.join(missing)}"})
    if item.get("source_chunk") != chunk_id:
        issues.append({"line": line_no, "severity": "ERROR", "message": f"items[{index}] source_chunk 与记录 chunk_id 不一致"})
    if isinstance(item.get("text"), str) and "|" in item.get("text", "") and "---" in item.get("text", ""):
        issues.append({"line": line_no, "severity": "ERROR", "message": f"items[{index}] 疑似 Markdown 表格输出"})
    confidence = item.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        issues.append({"line": line_no, "severity": "ERROR", "message": f"items[{index}] confidence 必须是 0-1 数字"})
    if item.get("ai_note") is False and not item.get("source_chunk"):
        issues.append({"line": line_no, "severity": "ERROR", "message": f"items[{index}] 原书要点必须有 source_chunk"})


def compile_concepts(args: argparse.Namespace) -> None:
    book_root = Path(args.book_root).resolve()
    records = load_extracted_records(book_root)
    concepts: dict[str, list[dict]] = {}
    for record in records:
        for item in record.get("items", []):
            name = safe_name(str(item.get("name", "未命名概念")))
            concepts.setdefault(name, []).append(item)
    candidates_dir = book_root / "review" / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    for name, items in sorted(concepts.items()):
        if len(items) < args.min_items:
            continue
        status = "draft" if all(float(i.get("confidence", 0)) >= args.min_confidence for i in items) else "needs_review"
        source_chunks = sorted({str(i.get("source_chunk")) for i in items if i.get("source_chunk")})
        lines = [
            "---",
            "type: concept",
            f"status: {status}",
            "standard: bookwiki-standard-v1",
            "source_chunks:",
        ]
        lines.extend(f"  - {chunk}" for chunk in source_chunks)
        lines.extend([
            "---",
            "",
            f"# {name}",
            "",
            "## 原书定义",
            "",
        ])
        definitions = [i for i in items if i.get("type") == "definition" and not i.get("ai_note")]
        if definitions:
            for item in definitions:
                lines.append(f"> {item.get('text')}  ")
                lines.append(f"> 来源：`{item.get('source_chunk')}`，{item.get('source_title')}，{item.get('source_lines')}")
                lines.append("")
        else:
            lines.append("> 暂无已抽取的原书定义。")
            lines.append("")
        lines.extend(["## 原书要点", ""])
        for item in items:
            if item.get("ai_note"):
                continue
            lines.append(f"- {item.get('text')} 来源：`{item.get('source_chunk')}`")
        lines.extend(["", "## 出现位置", ""])
        for item in items:
            lines.append(f"- {item.get('source_title')}，{item.get('source_lines')}，`{item.get('source_chunk')}`")
        lines.extend([
            "",
            "## AI 注释",
            "",
            "> 以下内容为 AI 辅助解释，不等同于原书原文。",
            "",
        ])
        ai_notes = [i for i in items if i.get("ai_note")]
        for item in ai_notes:
            lines.append(f"- {item.get('text')} 来源：`{item.get('source_chunk')}`")
        target = candidates_dir / f"{name}.md"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        generated += 1
    print(json.dumps({"concept_candidates": generated, "target": str(candidates_dir)}, ensure_ascii=False, indent=2))


def compile_learning_guides(args: argparse.Namespace) -> None:
    book_root = Path(args.book_root).resolve()
    orders_dir = book_root / "chunks" / "learning-orders"
    updated = 0
    skipped = 0
    for order_path in sorted(orders_dir.glob("*.json")):
        order = json.loads(order_path.read_text(encoding="utf-8"))
        article_path = book_root / "wiki" / f"{order['target_article']}.md"
        if not article_path.exists():
            continue
        text = article_path.read_text(encoding="utf-8")
        if args.skip_existing and "- 待生成" not in text:
            skipped += 1
            continue
        guide = render_learning_guide(order)
        new_text = replace_learning_section(text, guide)
        article_path.write_text(new_text, encoding="utf-8")
        updated += 1
    report = {
        "updated": updated,
        "skipped": skipped,
        "orders": len(list(orders_dir.glob("*.json"))),
    }
    report_path = book_root / "review" / "learning-guide-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


LEARNING_REQUIRED_SECTIONS = [
    "### 本文适合解决的问题",
    "### 零基础解释",
    "### 关键概念",
    "### 学习顺序",
    "### 容易误解的点",
]


def audit_learning_guides(args: argparse.Namespace) -> None:
    book_root = Path(args.book_root).resolve()
    article_paths = sorted((book_root / "wiki" / "articles").glob("**/*.md"))
    issues: list[dict] = []
    for article_path in article_paths:
        rel = str(article_path.relative_to(book_root))
        text = article_path.read_text(encoding="utf-8")
        guide = extract_between(text, "## AI 导学", "## 证据范围")
        if not guide:
            issues.append({"file": rel, "severity": "ERROR", "message": "缺少 AI 导学区"})
            continue
        for section in LEARNING_REQUIRED_SECTIONS:
            if section not in guide:
                issues.append({"file": rel, "severity": "ERROR", "message": f"缺少小节: {section}"})
        if "待生成" in guide:
            issues.append({"file": rel, "severity": "ERROR", "message": "存在待生成残留"})
        if guide.count("来源：`sec-") < 3:
            issues.append({"file": rel, "severity": "WARN", "message": "导学区 chunk 来源引用偏少"})
        if "这一节的 `" in guide or "本文反复出现的关键术语" in guide:
            issues.append({"file": rel, "severity": "WARN", "message": "存在规则模板化表达，建议精修"})
        if re.search(r"!\[[^\]]*\]\([^\)]+\)", text):
            issues.append({"file": rel, "severity": "WARN", "message": "存在 Markdown 图片链接，建议使用 Obsidian 内链"})
    status = "PASS" if not any(i["severity"] == "ERROR" for i in issues) else "FAIL"
    result = {"status": status, "articles": len(article_paths), "issues": issues}
    (book_root / "review" / "learning-guide-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# AI 导学审计报告", "", f"- 状态：{status}", f"- 文章数：{len(article_paths)}", f"- 问题数：{len(issues)}", "", "## 问题", ""]
    if issues:
        for issue in issues:
            lines.append(f"- {issue['severity']} `{issue['file']}`：{issue['message']}")
    else:
        lines.append("- 无")
    (book_root / "review" / "learning-guide-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "articles": len(article_paths), "issues": len(issues)}, ensure_ascii=False, indent=2))


def extract_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start:end]


def render_learning_guide(order: dict) -> str:
    chunks = [Chunk(**chunk) for chunk in order.get("source_chunks", [])]
    article_title = order.get("article_title", "本篇文章")
    chapter_title = order.get("chapter_title", "本章")
    headings = [c.title for c in chunks if c.title and not c.title.startswith("第")]
    focus = unique_keep_order([clean_heading(h) for h in headings])[:6]
    concepts = extract_key_terms("\n".join(c.text for c in chunks))[:8]
    source_refs = [c.chunk_id for c in chunks[:6]]
    main_ref = source_refs[0] if source_refs else "chunk"
    second_ref = source_refs[1] if len(source_refs) > 1 else main_ref

    questions = []
    for item in focus[:5]:
        questions.append(f"- 这一节的 `{item}` 想解决什么问题？来源：`{main_ref}`")
    if not questions:
        questions.append(f"- 本文围绕 `{article_title}` 要建立哪些基础认识？来源：`{main_ref}`")

    concept_lines = [f"- {term}：本文反复出现的关键术语，阅读原文时优先关注它的上下文。来源：`{main_ref}`" for term in concepts]
    if not concept_lines:
        concept_lines = [f"- {clean_heading(article_title)}：本文核心主题。来源：`{main_ref}`"]

    order_lines = []
    for item in focus[:5]:
        order_lines.append(f"- 先读 `{item}`，抓住本节要解决的具体问题。来源：`{main_ref}`")
    if not order_lines:
        order_lines.append(f"- 先读本篇标题和证据范围，再按原文顺序阅读。来源：`{main_ref}`")
    order_lines.append("- 阅读原文中的图、代码或执行结果时，先判断它是在证明概念、展示现象，还是给出操作步骤。")
    order_lines.append("- 最后回到证据块编号，确认导学中的每个判断都能追溯到原文。")

    misunderstanding = [
        f"- 不要把导学当成原书原文；真正的依据在下方 `原文` 区和证据块。来源：`{main_ref}`",
        f"- 不要只记结论，要看原文给出的适用条件、例子和限制。来源：`{second_ref}`",
        "- 如果本篇包含 SQL、配置或命令输出，不要脱离上下文直接套用到生产环境。",
    ]

    guide = [
        "## AI 导学",
        "",
        "> 本区为 AI 导学层，用来降低阅读门槛；下方“原文”仍是证据基准。导学内容引用 chunk，不替代原书表述。",
        "",
        "### 本文适合解决的问题",
        "",
        *questions,
        "",
        "### 零基础解释",
        "",
        f"这篇文章属于《{chapter_title}》中的 `{article_title}`。可以先把它当作一个小专题来读：不要急着记住所有细节，先弄清楚作者为什么要讲这些内容，以及这些内容在 DBA 工作中解决哪类问题。来源：`{main_ref}`",
        "",
        f"如果你是零基础读者，建议先抓住三个层次：第一，本文讨论的对象是什么；第二，作者用哪些例子、图或代码说明它；第三，这些内容对实际数据库开发或运维有什么提醒。来源：`{second_ref}`",
        "",
        "读专业书时最容易卡住的地方，是把术语、命令、案例混在一起。这里建议把术语看作概念，把命令或 SQL 看作验证手段，把案例看作作者想强调的风险或经验。",
        "",
        "### 关键概念",
        "",
        *concept_lines,
        "",
        "### 学习顺序",
        "",
        *order_lines,
        "",
        "### 容易误解的点",
        "",
        *misunderstanding,
    ]
    return "\n".join(guide).strip()


def replace_learning_section(text: str, guide: str) -> str:
    start = text.find("## AI 导学")
    end = text.find("## 证据范围")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[:start].rstrip() + "\n\n" + guide + "\n\n" + text[end:].lstrip()


def clean_heading(text: str) -> str:
    text = re.sub(r"^#+\s*", "", text.strip())
    text = re.sub(r"\s+", " ", text)
    return text[:80]


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_key_terms(text: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9_+\-]{1,24}|[\u4e00-\u9fff]{2,8}", text)
    stop = {"本章", "本文", "可以", "通过", "数据库", "一个", "这个", "进行", "使用", "实现", "问题", "数据", "来源"}
    counts: dict[str, int] = {}
    for candidate in candidates:
        if candidate in stop or candidate.isdigit():
            continue
        counts[candidate] = counts.get(candidate, 0) + 1
    return [term for term, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def load_extracted_records(book_root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted((book_root / "extracted").glob("knowledge*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def load_chunks(book_root: Path) -> list[Chunk]:
    chunks_file = book_root / "chunks" / "chunks.jsonl"
    chunks: list[Chunk] = []
    if chunks_file.exists():
        for line in chunks_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(Chunk(**json.loads(line)))
    return chunks


def build(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    out = Path(args.out).resolve()
    book = args.book or source.stem
    book_root = out / "workspace" / safe_name(book)
    ensure_dirs(book_root)
    ingest(source, book_root)
    sections = split_sections(book_root)
    chunks = chunk_sections(book_root, sections, args.max_tokens)
    compile_wiki(book_root, book, chunks)
    messages = audit(book_root, chunks)
    compile_standard_reports(book_root, book, chunks)
    print(json.dumps({"book_root": str(book_root), "chunks": len(chunks), "audit": messages}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-first professional book to LLM Wiki pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="run full offline pipeline")
    build_parser.add_argument("--source", required=True, help="source markdown file")
    build_parser.add_argument("--out", required=True, help="output root")
    build_parser.add_argument("--book", default="", help="book name")
    build_parser.add_argument("--max-tokens", type=int, default=1800, help="max estimated input tokens per chunk")
    build_parser.set_defaults(func=build)
    validate_parser = sub.add_parser("validate-extraction", help="validate model JSONL extraction output")
    validate_parser.add_argument("--book-root", required=True, help="workspace/<book> path")
    validate_parser.add_argument("--input", required=True, help="knowledge batch JSONL")
    validate_parser.set_defaults(func=validate_extraction)
    concepts_parser = sub.add_parser("compile-concepts", help="compile reviewed extraction JSONL into candidate concept pages")
    concepts_parser.add_argument("--book-root", required=True, help="workspace/<book> path")
    concepts_parser.add_argument("--min-items", type=int, default=1, help="minimum evidence items per concept")
    concepts_parser.add_argument("--min-confidence", type=float, default=0.75, help="confidence threshold for draft vs needs_review")
    concepts_parser.set_defaults(func=compile_concepts)
    guides_parser = sub.add_parser("compile-learning-guides", help="fill AI learning guide sections from learning orders")
    guides_parser.add_argument("--book-root", required=True, help="workspace/<book> path")
    guides_parser.add_argument("--skip-existing", action="store_true", help="do not overwrite articles that already have a filled guide")
    guides_parser.set_defaults(func=compile_learning_guides)
    audit_guides_parser = sub.add_parser("audit-learning-guides", help="audit AI learning guide sections")
    audit_guides_parser.add_argument("--book-root", required=True, help="workspace/<book> path")
    audit_guides_parser.set_defaults(func=audit_learning_guides)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

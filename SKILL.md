---
name: 408-teach
description: 408 考研自学总技能：管理教材、考纲、真题和学习进度，基于教材章节生成“完整原文 + 就地深度讲解 + 408 考法 + 易错点”的讲义，并支持继续下一节、诊断教材结构、登记科目资料、绑定计算机组成原理当前材料、真题对照和未来重型索引扩展。Use when the user wants to study 408 subjects such as 计算机组成原理、操作系统、计算机网络、数据结构 from local教材/OCR/PDF/考纲/真题, initialize or inspect a 408 study project, continue learning, explain a section, or build exam-oriented self-study notes.
---

# 408 Teach

Build an exam-oriented 408 self-study project from local materials. Keep the existing lecture engine reliable: extract one textbook section, preserve the source spine, explain each source heading in place, validate the lecture, archive images, and advance progress only after validation passes.

## Start Here

- Use the project directory supplied by the user. If none is supplied, use `.` only when it is clearly the active study project.
- If the project is the current computer-organization material folder and `.408-config.json` is missing or incomplete, run `python <skill>/main.py bootstrap-co <项目目录>`.
- Otherwise initialize with `python <skill>/main.py init <项目目录>`, then add textbooks and materials explicitly.
- Use `python <skill>/main.py materials <项目目录>` to inspect registered textbooks, syllabus files, past-paper PDFs, and future index slots.
- Never load the whole textbook. Extract only the requested section. A parent section automatically includes all descendant subsections until the next true sibling section.

## Source Authority

- Treat `source_authority: pdf` as a hard rule: the PDF is the authority for textbook wording, formulas, tables, figures, and page layout.
- Treat `derived_markdown` as a section index and cache when `markdown_role: section_index_and_cache`; use it to locate headings and draft source text, not as final proof.
- If Markdown conflicts with the PDF, follow the PDF.
- Before finalizing a lecture from an OCR-derived Markdown section, inspect the PDF when the section includes formulas, tables, figures, suspicious OCR, or user-reported errors.
- If exact PDF verification is not possible for a small passage, say so in the working notes and do not invent missing textbook text.

For the current bundled computer-organization project, see [references/materials.md](references/materials.md).

## Diagram Policy

- Do not reference or copy textbook image files for conceptual diagrams by default.
- Reconstruct conceptual figures yourself in the lecture using Mermaid, tables, ASCII diagrams, or concise text diagrams, and label them as self-drawn from the textbook's meaning.
- Preserve the textbook's figure number and caption text when useful, but replace the `![](...)` image link with the self-drawn diagram.
- Only keep an original image link when the user explicitly asks to preserve the original figure, or when the figure is not meaningfully reproducible as a diagram, such as a photograph, detailed circuit image, scanned handwritten mark, or visually dense table.
- If an original image is replaced, still use the PDF as the authority for the figure's meaning and surrounding text.

## Commands

| Intent | Command |
|---|---|
| Initialize | `python <skill>/main.py init [项目目录]` |
| Add textbook | `python <skill>/main.py add <教材名> <教材Markdown路径> [项目目录] [--source-pdf PDF] [--authority pdf\|markdown] [--md-role ROLE]` |
| Bind current 组成原理 project | `python <skill>/main.py bootstrap-co [项目目录]` |
| View registered materials | `python <skill>/main.py materials [项目目录] [科目]` |
| Switch textbook | `python <skill>/main.py switch <教材名> [项目目录]` |
| View progress | `python <skill>/main.py status [项目目录]` |
| Diagnose structure | `python <skill>/main.py doctor [项目目录]` |
| Extract section or keyword | `python <skill>/main.py extract <章节号\|关键词> [项目目录] [--max-chars N] [--chunk K]` |
| Continue | `python <skill>/main.py continue [项目目录] [--max-chars N] [--chunk K]` |
| Validate, archive, advance | `python <skill>/main.py finalize <章节号> <草稿路径> [项目目录]` |
| Manual recovery | `python <skill>/main.py complete <章节号> [项目目录]` |

Notes:

- `extract` returns JSON with `type: "section"` or `type: "multiple_matches"`.
- `extract` and `doctor` include `source_authority`, `source_pdf`, `derived_markdown`, and `markdown_role`.
- `continue` starts from saved progress or the first study section.
- `--chunk` is one-based and requires `--max-chars`; collect and merge every chunk before `finalize`.
- Treat command stdout as machine-readable JSON where applicable. Keep user commentary in the conversation.

## Study Workflow

Read [references/kaoyan-408-workflow.md](references/kaoyan-408-workflow.md) when the user asks for exam-oriented learning, syllabus alignment,真题对照,错题复盘, or multi-session study planning.

Default flow for one section:

1. Inspect project materials with `materials` when the project is new or ambiguous.
2. Use `doctor` after adding or bootstrapping a textbook. Stop on fatal or error diagnostics.
3. Use `extract` or `continue`. If a keyword has multiple matches, show choices and ask which section to use.
4. Read [references/lecture-quality.md](references/lecture-quality.md), [references/408os-importance.md](references/408os-importance.md), and [references/mixed-teaching-style.md](references/mixed-teaching-style.md).
5. Align the extracted section with the syllabus, `https://www.408os.cn/analysis` exam-frequency data, and relevant past-paper PDFs when available.
6. Use the PDF as authority when `source_authority` is `pdf`.
7. Write one UTF-8 Markdown draft in source order. Preserve complete extracted source unless explicitly correcting OCR from PDF evidence.
8. For every source heading, assign an S/A/B/C/D importance level and adjust explanation depth accordingly.
9. Run `finalize`. Fix every reported issue and rerun until it passes.

## Lecture Contract

Use two top-level titles for new lectures: first `# 408考试大纲`, then one section title containing the requested section number. The legacy one-title format is still accepted for old notes.

```markdown
# 408考试大纲

本讲义对应的 408 大纲条目。比如讲解 1.3 计算机系统层次结构时，先放“计算机组成原理 第一章 计算机系统概述”相关大纲。

## 408os 考频分析

- 数据范围：2009-2026，共 18 年真题统计。
- 本节相关知识点：列出知识点、等级 S/A/B/C/D、题量、分值、考察年份数。
- 本节讲解策略：说明哪些深讲，哪些速通，哪些只做保底识别。

# 1.3 章节标题

## 教材原文

按 408 大纲引用教材父节原文，完整保留被引用的教材段落，或按 PDF 证据修正 OCR。

### 重要性判断
- 等级：S/A/B/C/D
- 依据：408os 考频、408 大纲位置、真题/章节连接关系
- 学习策略：深讲 / 标准讲 / 速通 / 概念卡片 / 保底识别

### 核心概念与深度讲解
#### 你可能会卡在哪里
...
#### 从零推导
...
#### 机制拆解
...
#### 例子跑通
...
#### 408 怎么考
...
#### 易错点
...

## 1.3.1 教材子标题

按 408 大纲引用该子标题下的教材原文，完整保留被引用的教材段落，或按 PDF 证据修正 OCR。

### 重要性判断
- 等级：S/A/B/C/D
- 依据：408os 考频、408 大纲位置、真题/章节连接关系
- 学习策略：深讲 / 标准讲 / 速通 / 概念卡片 / 保底识别

### 核心概念与深度讲解
#### 最低掌握
...
#### 看到题怎么处理
...
#### 408 怎么考
...
#### 易错点
...
```

Apply this block to the target heading and every heading present in the extracted source, in the same order. Use two level-one headings only: `# 408考试大纲` and the target section title. Downgrade descendant source headings when necessary.

Every source heading must have:

- non-empty `核心概念与深度讲解` directly before the next source heading;
- a heading named `重要性判断` before the explanation block;
- a heading named `408 怎么考`;
- a heading beginning with `易错点`.

Depth is not uniform. Follow `references/mixed-teaching-style.md`: S/A knowledge points use teacher-style zero-to-mechanism explanation; B points use problem-solving speed-run explanation; C/D points use recognition-only treatment. Do not delete low-frequency syllabus items, but do not spend high-frequency time on them.

Do not restore old global sections such as `学习目标`, `典型例题`, `本节自测`, or `一分钟总结`. Put examples, summaries, and真题提示 next to the textbook passage they explain.

## Future Index Slot

If a project contains `.408-index/`, use it as an optional retrieval layer:

```text
.408-index/
  chunks.jsonl
  syllabus-map.json
  questions.jsonl
  mistakes.jsonl
```

When the index is absent, fall back to registered materials plus section extraction. Do not block ordinary learning because the heavy index has not been built.

## Components

- `main.py`: CLI workflow, material registration, finalization, and image archiving.
- `scripts/config.py`: configuration, material registry, progress, path safety, and atomic writes.
- `scripts/parser.py`: section parsing, parent extraction, diagnostics, chunking, search, and source hashing.
- `scripts/validate_lecture.py`: inline lecture contract validation.
- `scripts/visualization.py`: optional Mermaid HTML helper; it is not part of the normal `finalize` path.

Use `complete` only to recover progress when a valid canonical lecture already exists.

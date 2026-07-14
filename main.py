#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
408-teach Skill 主程序
处理用户命令，协调各模块工作
"""

import sys
import os
import json
import hashlib
import re
from pathlib import Path
from urllib.parse import unquote

# 添加scripts目录到路径
SCRIPT_DIR = Path(__file__).parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from parser import TextbookParser
from config import (
    ConfigManager,
    atomic_write_bytes,
    atomic_write_text,
    sanitize_path_component,
)
from validate_lecture import validate_lecture


_IMAGE_LINK = re.compile(r'(!\[[^\]]*\]\()([^)]*)(\))')
_REMOTE_IMAGE = re.compile(r'^(?:https?://|data:)', re.IGNORECASE)


def _usage_text():
    return """408-teach Skill

用法: python main.py <命令> [参数]

命令:
  init [目录]                     - 初始化项目
  add <教材名> <路径> [目录]      - 添加教材
  materials [目录] [科目]         - 查看已登记教材、考纲和真题
  bootstrap-co [目录]             - 绑定当前组成原理教材、考纲和真题
  switch <教材名> [目录]          - 切换教材
  status [目录]                   - 查看进度
  extract <章节号|关键词> [目录]  - 提取章节内容
  continue [目录]                 - 继续学习
  doctor [目录]                   - 诊断教材结构
  finalize <章节号> <草稿> [目录] - 校验、保存并推进
  complete <章节号> [目录]        - 低级手动推进

选项:
  -h, --help, help                - 显示帮助
"""


def _diagnostics_blocking(diagnostics):
    return any(item["severity"] in {"fatal", "error"} for item in diagnostics)


def _split_image_destination(inner):
    stripped = inner.strip()
    if not stripped:
        return "", ""
    if stripped.startswith("<"):
        end = stripped.find(">")
        if end != -1:
            return stripped[1:end], stripped[end + 1:]

    title_match = re.match(r'(.+?)(\s+["\'][^"\']*["\']\s*)$', stripped)
    if title_match:
        return title_match.group(1).strip(), title_match.group(2)
    return stripped, ""


def _format_image_destination(destination):
    if re.search(r'[\s()]', destination):
        return f"<{destination}>"
    return destination


def _prepare_local_images(content, textbook_path):
    """Resolve local image links and return portable links plus image bytes."""
    textbook_dir = Path(textbook_path).resolve().parent
    source_names = {}
    target_sources = {}
    assets = []

    def replace_link(match):
        inner = match.group(2)
        leading = re.match(r'\s*', inner).group(0)
        trailing = re.search(r'\s*$', inner).group(0)
        raw_link, title = _split_image_destination(inner)
        link = unquote(raw_link)
        if _REMOTE_IMAGE.match(link) or link.startswith("#"):
            return match.group(0)

        source = Path(link.replace("/", os.sep))
        if not source.is_absolute():
            source = textbook_dir / source
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"讲义引用的教材图片不存在: {source}")

        source_key = str(source).casefold()
        target_name = source_names.get(source_key)
        if target_name is None:
            data = source.read_bytes()
            target_name = source.name
            existing_source = target_sources.get(target_name.casefold())
            if existing_source is not None and existing_source != source_key:
                digest = hashlib.sha256(data).hexdigest()[:8]
                target_name = f"{source.stem}-{digest}{source.suffix}"
            source_names[source_key] = target_name
            target_sources[target_name.casefold()] = source_key
            assets.append((Path("images") / target_name, data))

        destination = _format_image_destination(f"images/{target_name}")
        return f"{match.group(1)}{leading}{destination}{title}{trailing}{match.group(3)}"

    return _IMAGE_LINK.sub(replace_link, content), assets


def _parse_chunk_options(args):
    """Parse an optional project directory plus extraction chunk options."""
    project_dir = "."
    max_chars = None
    chunk_index = None
    positional = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--max-chars", "--chunk"}:
            if index + 1 >= len(args):
                raise ValueError(f"{arg} 缺少参数")
            try:
                value = int(args[index + 1])
            except ValueError as exc:
                raise ValueError(f"{arg} 必须是整数") from exc
            if value < 1:
                raise ValueError(f"{arg} 必须大于 0")
            if arg == "--max-chars":
                max_chars = value
            else:
                chunk_index = value
            index += 2
            continue
        if arg.startswith("--"):
            raise ValueError(f"未知选项: {arg}")
        positional.append(arg)
        index += 1

    if len(positional) > 1:
        raise ValueError("只能指定一个项目目录")
    if positional:
        project_dir = positional[0]
    if chunk_index is not None and max_chars is None:
        raise ValueError("--chunk 必须与 --max-chars 一起使用")
    return project_dir, max_chars, chunk_index or 1


def _apply_chunking(result, max_chars, chunk_index):
    if result.get("type") != "section" or max_chars is None:
        return result
    content = result["section"]["content"]
    chunks = TextbookParser.chunk_content(content, max_chars)
    if chunk_index > len(chunks):
        raise ValueError(f"分块序号超出范围: {chunk_index}，共 {len(chunks)} 块")

    section = dict(result["section"])
    section["content"] = chunks[chunk_index - 1]
    section["paragraphs"] = []
    result = dict(result)
    result["section"] = section
    result.update({
        "chunk_index": chunk_index,
        "chunk_count": len(chunks),
        "is_last_chunk": chunk_index == len(chunks),
        "source_sha256": TextbookParser.source_sha256(content),
    })
    return result


def _textbook_source_payload(current):
    return {
        "source_authority": current.get("sourceAuthority", "markdown"),
        "source_pdf": current.get("sourcePdf"),
        "derived_markdown": current.get("derivedMarkdown", current.get("path")),
        "markdown_role": current.get("markdownRole", "primary_source"),
    }


def _parse_add_args(args):
    if len(args) < 2:
        raise ValueError(
            "用法: add <教材名称> <教材Markdown路径> [项目目录] "
            "[--source-pdf PDF] [--authority pdf|markdown] [--md-role ROLE]"
        )

    name = args[0]
    path = args[1]
    project_dir = "."
    source_pdf = None
    source_authority = None
    markdown_role = "primary_source"
    positional = []
    index = 2
    while index < len(args):
        arg = args[index]
        if arg in {"--source-pdf", "--authority", "--md-role"}:
            if index + 1 >= len(args):
                raise ValueError(f"{arg} 缺少参数")
            value = args[index + 1]
            if arg == "--source-pdf":
                source_pdf = value
            elif arg == "--authority":
                source_authority = value
            else:
                markdown_role = value
            index += 2
            continue
        if arg.startswith("--"):
            raise ValueError(f"未知选项: {arg}")
        positional.append(arg)
        index += 1

    if len(positional) > 1:
        raise ValueError("只能指定一个项目目录")
    if positional:
        project_dir = positional[0]
    if source_authority is None:
        source_authority = "pdf" if source_pdf else "markdown"
    return name, path, project_dir, source_pdf, source_authority, markdown_role


def handle_init(args):
    """处理初始化命令"""
    project_dir = args[0] if args else "."
    manager = ConfigManager(project_dir)
    manager.init_project()


def handle_add(args):
    """处理添加教材命令"""
    name, path, project_dir, source_pdf, source_authority, markdown_role = _parse_add_args(args)

    manager = ConfigManager(project_dir)
    manager.add_textbook(
        name,
        path,
        source_pdf=source_pdf,
        source_authority=source_authority,
        markdown_role=markdown_role,
    )


def _computer_organization_paths(project_dir):
    root = Path(project_dir).resolve()
    ocr_dir = root / "计算机组成与系统结构-第3版-袁春风" / "ocr"
    stem = "11计算机组成与系统结构-第3版-袁春风"
    return {
        "root": root,
        "markdown": ocr_dir / f"{stem}.md",
        "source_pdf": ocr_dir / f"{stem}_origin.pdf",
        "syllabus": root / "计算机组成原理大纲.md",
        "papers_dir": root / "计算机组成原理真题",
    }


def handle_bootstrap_co(args):
    """Bind the current computer-organization study materials."""
    if len(args) > 1:
        raise ValueError("用法: bootstrap-co [项目目录]")
    project_dir = args[0] if args else "."
    paths = _computer_organization_paths(project_dir)
    papers = sorted(str(path) for path in paths["papers_dir"].glob("*.pdf"))

    manager = ConfigManager(str(paths["root"]))
    manager.ensure_project()
    manager.add_textbook(
        "计算机组成原理",
        str(paths["markdown"]),
        source_pdf=str(paths["source_pdf"]),
        source_authority="pdf",
        markdown_role="section_index_and_cache",
        quiet=True,
    )
    subject = manager.register_subject_materials(
        "计算机组成原理",
        textbook_name="计算机组成原理",
        syllabus_path=str(paths["syllabus"]),
        paper_paths=papers,
        future_index_dir=".408-index/计算机组成原理",
    )
    return {
        "project_dir": str(paths["root"]),
        "subject": "计算机组成原理",
        "textbook": manager.get_current_textbook(),
        "materials": subject,
    }


def handle_materials(args):
    """Return registered subject-facing materials."""
    if len(args) > 2:
        raise ValueError("用法: materials [项目目录] [科目]")
    project_dir = args[0] if args else "."
    subject = args[1] if len(args) == 2 else None
    manager = ConfigManager(project_dir)
    return {
        "project_dir": str(Path(project_dir).resolve()),
        "textbooks": manager.get_all_textbooks(),
        "subjects": manager.get_subject_materials(subject),
    }


def handle_switch(args):
    """处理切换教材命令"""
    if len(args) < 1:
        raise ValueError("用法: switch <教材名称> [项目目录]")

    name = args[0]
    project_dir = args[1] if len(args) > 1 else "."

    manager = ConfigManager(project_dir)
    manager.switch_textbook(name)


def handle_status(args):
    """处理查看进度命令"""
    project_dir = args[0] if args else "."
    manager = ConfigManager(project_dir)

    current = manager.get_current_textbook()
    if not current:
        raise ValueError("未设置当前教材，请先添加教材")

    all_progress = manager.get_all_progress()
    all_textbooks = manager.get_all_textbooks()

    print(f"\n📚 当前教材：{current['name']}")
    if current.get("sourceAuthority") == "pdf" and current.get("sourcePdf"):
        print(f"📌 权威源：PDF（{current['sourcePdf']}）")
        print(f"🧭 章节索引：Markdown（{current['path']}）")
    current_progress = all_progress.get(current['name'], {})
    completed = current_progress.get('completed', [])
    current_section = current_progress.get('current')
    finished = current_progress.get('finished', False)

    print(f"✅ 已完成：{', '.join(completed) if completed else '无'} (共{len(completed)}节)")
    progress_label = "全书已完成" if finished else (current_section or "未开始")
    print(f"📍 当前进度：{progress_label}")

    print(f"\n📚 其他教材：")
    for name in all_textbooks:
        if name != current['name']:
            progress = all_progress.get(name, {})
            completed = progress.get('completed', [])
            current_section = progress.get('current')
            if completed:
                print(f"   {name} - 已完成 {', '.join(completed[:3])}{'...' if len(completed) > 3 else ''} (当前: {current_section})")
            else:
                print(f"   {name} - 未开始")


def handle_extract(args):
    """
    处理讲解命令，提取章节内容
    返回提取的章节数据供Claude生成讲义
    """
    if len(args) < 1:
        raise ValueError("用法: extract <章节号|关键词> [项目目录] [--max-chars N] [--chunk N]")

    query = args[0]
    project_dir, max_chars, chunk_index = _parse_chunk_options(args[1:])

    manager = ConfigManager(project_dir)
    current = manager.get_current_textbook()

    if not current:
        raise ValueError("未设置当前教材，请先添加教材")

    textbook_path = current['path']
    parser = TextbookParser(textbook_path)

    # 判断是章节号还是关键词
    normalized_query = TextbookParser.normalize_section_number(query)
    if normalized_query:
        # 按章节号提取
        section = parser.extract_section(normalized_query)
        if not section:
            # 列出可用章节
            chapters = parser.extract_chapter_list()
            available = "，".join(f"{ch['number']} {ch['title']}" for ch in chapters[:20])
            raise ValueError(f"未找到章节 {query}。可用章节: {available or '无'}")

        return _apply_chunking({
            "type": "section",
            "textbook_name": current['name'],
            "textbook_path": textbook_path,
            "output_dir": current['outputDir'],
            **_textbook_source_payload(current),
            "section": section,
            "project_dir": project_dir
        }, max_chars, chunk_index)

    else:
        # 按关键词搜索
        results = parser.search_keyword(query)
        if not results:
            raise ValueError(f"未找到包含 '{query}' 的章节")

        if len(results) == 1:
            # 唯一匹配，直接提取
            section = parser.extract_section(results[0]['number'])
            return _apply_chunking({
                "type": "section",
                "textbook_name": current['name'],
                "textbook_path": textbook_path,
                "output_dir": current['outputDir'],
                **_textbook_source_payload(current),
                "section": section,
                "project_dir": project_dir
            }, max_chars, chunk_index)

        else:
            return {
                "type": "multiple_matches",
                "results": results
            }


def handle_continue(args):
    """处理继续学习命令"""
    project_dir, max_chars, chunk_index = _parse_chunk_options(args)

    manager = ConfigManager(project_dir)
    current = manager.get_current_textbook()

    if not current:
        raise ValueError("未设置当前教材，请先添加教材")

    progress = manager.get_progress(current['name'])
    if progress.get('finished'):
        return {
            "type": "finished",
            "textbook_name": current["name"],
            "message": f"教材《{current['name']}》已完成",
        }

    current_section = progress.get('current')
    started_from_first = False

    # 如果没有当前进度，从第一章第一节开始
    if not current_section:
        parser = TextbookParser(current['path'])
        current_section = parser.get_first_study_section()
        if current_section:
            started_from_first = True
        else:
            raise ValueError("无法解析教材章节结构")

    # 提取该节内容
    extract_args = [current_section, project_dir]
    if max_chars is not None:
        extract_args.extend(["--max-chars", str(max_chars), "--chunk", str(chunk_index)])
    result = handle_extract(extract_args)
    if started_from_first and result:
        result = dict(result)
        result["started_from_first"] = True
    return result


def handle_complete(args):
    """完成一节并根据教材结构自动推进到下一节。"""
    if len(args) < 1:
        raise ValueError("用法: complete <章节号> [项目目录]")

    section_number = args[0]
    project_dir = args[1] if len(args) > 1 else "."
    manager = ConfigManager(project_dir)
    current = manager.get_current_textbook()
    if not current:
        raise ValueError("未设置当前教材，请先添加教材")

    parser = TextbookParser(current['path'])
    normalized = parser.normalize_section_number(section_number)
    if not normalized or not parser.extract_section(normalized):
        raise ValueError(f"未找到章节 {section_number}")

    next_section = parser.get_next_section(normalized)
    manager.update_progress(current['name'], normalized, next_section=next_section)
    return {
        "completed": normalized,
        "next": next_section,
        "finished": next_section is None,
    }


def handle_doctor(args):
    """Diagnose active textbook structure without changing project state."""
    if len(args) > 1:
        raise ValueError("用法: doctor [项目目录]")
    project_dir = args[0] if args else "."
    manager = ConfigManager(project_dir)
    current = manager.get_current_textbook()
    if not current:
        raise ValueError("未设置当前教材，请先添加教材")

    textbook_path = Path(current["path"])
    if not textbook_path.is_file():
        return {
            "textbook": current["name"],
            **_textbook_source_payload(current),
            "diagnostics": [{
                "severity": "fatal",
                "code": "missing_textbook",
                "message": f"教材文件不存在或不可读: {textbook_path}",
            }],
            "fatal": True,
        }

    diagnostics = TextbookParser(str(textbook_path)).diagnose()
    return {
        "textbook": current["name"],
        **_textbook_source_payload(current),
        "diagnostics": diagnostics,
        "fatal": _diagnostics_blocking(diagnostics),
    }


def handle_finalize(args):
    """Validate, atomically store, and only then advance one section."""
    if len(args) not in {2, 3}:
        raise ValueError("用法: finalize <章节号> <草稿路径> [项目目录]")

    section_number, draft_path = args[:2]
    project_dir = args[2] if len(args) == 3 else "."
    manager = ConfigManager(project_dir)
    current = manager.get_current_textbook()
    if not current:
        raise ValueError("未设置当前教材，请先添加教材")

    parser = TextbookParser(current["path"])
    normalized = parser.normalize_section_number(section_number)
    section = parser.extract_section(normalized) if normalized else None
    if not section:
        raise ValueError(f"未找到章节 {section_number}")

    draft = Path(draft_path)
    if not draft.is_file():
        raise FileNotFoundError(f"讲义草稿不存在: {draft}")
    content = draft.read_text(encoding="utf-8")
    errors = validate_lecture(
        content,
        expected_section=normalized,
        source_content=section["content"],
    )
    if errors:
        raise ValueError("讲义校验失败：\n- " + "\n- ".join(errors))

    content, image_assets = _prepare_local_images(content, current["path"])

    chapter_dir = f"chapter-{int(normalized.split('.')[0]):02d}"
    section_dir = sanitize_path_component(f"{normalized}-{section['title']}")
    destination = (
        manager.get_output_dir(current["name"])
        / "lectures"
        / chapter_dir
        / section_dir
        / "讲义.md"
    )
    for relative_path, image_content in image_assets:
        atomic_write_bytes(destination.parent / relative_path, image_content)
    atomic_write_text(destination, content)

    next_section = parser.get_next_section(normalized)
    manager.update_progress(current["name"], normalized, next_section=next_section)
    return {
        "finalized_path": str(destination.resolve()),
        "completed": normalized,
        "next": next_section,
        "finished": next_section is None,
    }


def main():
    """主函数"""
    import io

    # 保证机器调用方可以用同一编码读取成功与错误输出。
    if sys.platform == 'win32':
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    if len(sys.argv) < 2:
        print(_usage_text())
        return 2

    command = sys.argv[1]
    args = sys.argv[2:]
    if command in {"-h", "--help", "help"}:
        print(_usage_text())
        return 0

    try:
        if command == "init":
            handle_init(args)
        elif command == "add":
            handle_add(args)
        elif command == "materials":
            result = handle_materials(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif command == "bootstrap-co":
            result = handle_bootstrap_co(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif command == "switch":
            handle_switch(args)
        elif command == "status":
            handle_status(args)
        elif command == "extract":
            result = handle_extract(args)
            if result:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif command == "continue":
            result = handle_continue(args)
            if result:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif command == "doctor":
            result = handle_doctor(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["fatal"] else 0
        elif command == "finalize":
            result = handle_finalize(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif command == "complete":
            result = handle_complete(args)
            if result:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            raise ValueError(f"未知命令: {command}")
    except (ValueError, FileNotFoundError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

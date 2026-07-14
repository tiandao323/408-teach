#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the deterministic parts of an inline 408 lecture note."""

import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple


INLINE_EXPLANATION = "核心概念与深度讲解"
SYLLABUS_TITLE = "408考试大纲"
FREQUENCY_ANALYSIS = "408os考频分析"
IMPORTANCE_JUDGMENT = "重要性判断"
PLACEHOLDER_PATTERNS = [
    re.compile(r"\b(?:TODO|TBD)\b", re.IGNORECASE),
    re.compile(r"待补充|待完善"),
    re.compile(r"\{\{[^{}]+\}\}"),
    re.compile(r"(?m)^\s*深度讲解\s*\d"),
]
_SEPARATOR_TRANSLATION = str.maketrans({
    "．": ".", "。": ".", "·": ".", "-": ".", "—": ".", "–": ".",
})


def _heading_key(title: str) -> str:
    return re.sub(r"\s+", "", title.strip().translate(_SEPARATOR_TRANSLATION))


def _headings(lines: List[str]) -> List[Tuple[int, int, str]]:
    headings: List[Tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if re.match(r"^\s*(?:```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append((index, len(match.group(1)), _heading_key(match.group(2))))
    return headings


def _source_headings(lines: List[str]) -> List[Tuple[int, int, str]]:
    """Keep numbered textbook headings and ignore OCR lines beginning with '#'."""
    return [
        heading
        for heading in _headings(lines)
        if re.match(r"^(?:第\d+章|\d+(?:\.\d+)*(?=\D|$))", heading[2])
    ]


def _title_contains_section(title: str, expected_section: str) -> bool:
    normalized_title = title.translate(_SEPARATOR_TRANSLATION)
    pattern = rf"(?<![\d.]){re.escape(expected_section)}(?![\d.])"
    return re.search(pattern, normalized_title) is not None


def _body_key(text: str) -> str:
    """Normalize source body text while allowing Markdown heading downgrades."""
    lines = [
        re.sub(r"^\s*#{1,6}\s+", "", line)
        for line in text.splitlines()
    ]
    normalized = "\n".join(lines).strip().translate(_SEPARATOR_TRANSLATION)
    return re.sub(r"\s+", "", normalized)


def _drop_markdown_image_lines(text: str) -> str:
    return "\n".join(
        line
        for line in text.splitlines()
        if not re.match(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$", line)
    )


def _body_line_keys(text: str) -> List[str]:
    return [
        key
        for key in (_body_key(line) for line in text.splitlines())
        if key
    ]


def _body_lines_preserved_in_order(source_body: str, lecture_key: str) -> bool:
    cursor = 0
    for line_key in _body_line_keys(source_body):
        found = lecture_key.find(line_key, cursor)
        if found == -1:
            return False
        cursor = found + len(line_key)
    return True


def _body_preserved(source_body: str, lecture_body: str) -> bool:
    if "不引用原图文件" in lecture_body and "```mermaid" in lecture_body:
        source_body = _drop_markdown_image_lines(source_body)

    source_key = _body_key(source_body)
    if not source_key:
        return True

    lecture_key = _body_key(lecture_body)
    if source_key in lecture_key:
        return True
    if _body_lines_preserved_in_order(source_body, lecture_key):
        return True
    if len(source_key) >= 20 and len(lecture_key) >= 20:
        return SequenceMatcher(None, source_key, lecture_key).ratio() >= 0.9
    return False


def _match_source_headings(
    lecture_headings: List[Tuple[int, int, str]],
    source_headings: List[Tuple[int, int, str]],
) -> Tuple[List[Tuple[int, int, str]], List[str]]:
    matched: List[Tuple[int, int, str]] = []
    errors: List[str] = []
    cursor = 0
    lecture_titles = [title for _, _, title in lecture_headings]

    for _, _, source_title in source_headings:
        found = next(
            (
                index
                for index in range(cursor, len(lecture_headings))
                if lecture_headings[index][2] == source_title
            ),
            None,
        )
        if found is None:
            if source_title in lecture_titles:
                errors.append(f"教材标题顺序不一致：{source_title}")
            else:
                errors.append(f"缺少教材标题：{source_title}")
            continue
        matched.append(lecture_headings[found])
        cursor = found + 1

    return matched, errors


def _heading_body(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
    heading: Tuple[int, int, str],
) -> str:
    start = heading[0] + 1
    end = next((line_index for line_index, _, _ in headings if line_index > heading[0]), len(lines))
    return "\n".join(lines[start:end]).strip()


def validate_lecture(
    content: str,
    expected_section: Optional[str] = None,
    source_content: Optional[str] = None,
) -> List[str]:
    """Return human-readable errors; an empty list means validation passed."""
    errors: List[str] = []
    lines = content.splitlines()
    headings = _headings(lines)

    top_level = [(line_index, title) for line_index, level, title in headings if level == 1]
    section_title: Optional[str] = None
    requires_importance = False
    if len(top_level) == 1:
        section_title = top_level[0][1]
    elif len(top_level) == 2 and top_level[0][1] == _heading_key(SYLLABUS_TITLE):
        section_title = top_level[1][1]
        requires_importance = True
        preface_lines = lines[top_level[0][0] + 1:top_level[1][0]]
        preface_headings = _headings(preface_lines)
        if not any(heading[2] == _heading_key(FREQUENCY_ANALYSIS) for heading in preface_headings):
            errors.append("408考试大纲部分缺少 408os 考频分析")
    else:
        errors.append(
            "讲义必须有一个章节一级标题，或两个一级标题："
            "# 408考试大纲 和 # 目标章节标题；"
            f"当前为 {len(top_level)} 个"
        )

    if section_title and expected_section and not _title_contains_section(section_title, expected_section):
        errors.append(f"章节一级标题未包含目标章节号：{expected_section}")

    if source_content is not None:
        source_headings = _source_headings(source_content.splitlines())
        matched, match_errors = _match_source_headings(headings, source_headings)
        errors.extend(match_errors)

        if not source_headings:
            errors.append("教材源内容中未识别到标题")
        elif len(matched) == len(source_headings):
            source_lines = source_content.splitlines()
            for index, ((source_line_index, _, _), (line_index, _, title)) in enumerate(zip(source_headings, matched)):
                source_end = (
                    source_headings[index + 1][0]
                    if index + 1 < len(source_headings)
                    else len(source_lines)
                )
                source_body = "\n".join(source_lines[source_line_index + 1:source_end]).strip()
                end_line = matched[index + 1][0] if index + 1 < len(matched) else len(lines)
                segment_lines = lines[line_index + 1:end_line]
                segment_headings = _headings(segment_lines)
                importance = next(
                    (
                        heading
                        for heading in segment_headings
                        if heading[2] == _heading_key(IMPORTANCE_JUDGMENT)
                    ),
                    None,
                )
                explanation = next(
                    (
                        heading
                        for heading in segment_headings
                        if heading[2] == _heading_key(INLINE_EXPLANATION)
                    ),
                    None,
                )
                if requires_importance:
                    if importance is None:
                        errors.append(f"教材标题后缺少重要性判断：{title}")
                    else:
                        importance_text = _heading_body(segment_lines, segment_headings, importance)
                        if not importance_text:
                            errors.append(f"重要性判断为空：{title}")
                        elif "等级" not in importance_text:
                            errors.append(f"重要性判断缺少等级：{title}")
                        if explanation is not None and importance[0] > explanation[0]:
                            errors.append(f"重要性判断必须放在深度讲解前：{title}")
                if explanation is None:
                    errors.append(f"教材标题后缺少就地深度讲解：{title}")
                    continue

                source_area = "\n".join(segment_lines[:explanation[0]]).strip()
                if not _body_preserved(source_body, source_area):
                    errors.append(f"教材正文未完整保留或未放在讲解前：{title}")

                explanation_start = line_index + 1 + explanation[0] + 1
                explanation_text = "\n".join(lines[explanation_start:end_line]).strip()
                if not explanation_text:
                    errors.append(f"就地深度讲解为空：{title}")
                    continue
                if not re.search(r"^#{3,6}\s+408\s*怎么考", explanation_text, re.MULTILINE):
                    errors.append(f"就地深度讲解缺少 408 考法：{title}")
                if not re.search(r"^#{3,6}\s+易错点", explanation_text, re.MULTILINE):
                    errors.append(f"就地深度讲解缺少易错点：{title}")

    if any(pattern.search(content) for pattern in PLACEHOLDER_PATTERNS):
        errors.append("讲义中仍有未解决的占位内容")

    if re.search(r"!\[[^\]]*\]\(\s*(?:<>\s*)?\)", content):
        errors.append("讲义中存在空图片引用")

    fence_count = sum(
        1 for line in lines if re.match(r"^\s*(?:```|~~~)", line)
    )
    if fence_count % 2:
        errors.append("代码围栏未成对闭合")

    return errors


def main() -> int:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        usage="python validate_lecture.py <讲义.md> [--section <章节号>] [--source <教材节选.md>]"
    )
    parser.add_argument("lecture")
    parser.add_argument("--section")
    parser.add_argument("--source")
    args = parser.parse_args()

    lecture_path = Path(args.lecture)
    if not lecture_path.is_file():
        print(f"讲义文件不存在: {lecture_path}")
        return 2

    source_content = None
    if args.source:
        source_path = Path(args.source)
        if not source_path.is_file():
            print(f"教材节选不存在: {source_path}")
            return 2
        source_content = source_path.read_text(encoding="utf-8")

    errors = validate_lecture(
        lecture_path.read_text(encoding="utf-8"),
        expected_section=args.section,
        source_content=source_content,
    )
    if errors:
        print("讲义校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"讲义校验通过: {lecture_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

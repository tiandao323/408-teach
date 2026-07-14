#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
408教材解析器
功能：从教材OCR Markdown中提取指定章节内容
"""

import hashlib
import re
import json
from collections import Counter
from pathlib import Path
from typing import Any, List, Dict, Optional


class TextbookParser:
    """教材解析器"""

    _CHINESE_DIGITS = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    _SEPARATOR_TRANSLATION = str.maketrans({
        "．": ".",
        "。": ".",
        "·": ".",
        "-": ".",
        "—": ".",
        "–": ".",
    })
    _NUMBERED_HEADING = re.compile(
        r'^(\d+(?:\s*[.．。·\-—–]\s*\d+)*)'
        r'(?:\s*[、:：]\s*|\s+)?(.+)$'
    )
    _CHAPTER_HEADING = re.compile(
        r'^第\s*([零〇一二两三四五六七八九十百\d]+)\s*章(?:\s*[、:：\-—–]?\s*)(.*)$'
    )

    def __init__(self, textbook_path: str):
        """
        初始化解析器

        Args:
            textbook_path: 教材Markdown文件路径
        """
        self.textbook_path = Path(textbook_path)
        if not self.textbook_path.exists():
            raise FileNotFoundError(f"教材文件不存在: {textbook_path}")

        with open(self.textbook_path, 'r', encoding='utf-8') as f:
            self.content = f.read()

        self.lines = self.content.split('\n')

    @classmethod
    def normalize_section_number(cls, value: str) -> Optional[str]:
        """将常见 OCR 章节号统一为点分格式。"""
        value = value.strip()
        chapter_match = re.fullmatch(r'第\s*([零〇一二两三四五六七八九十百\d]+)\s*章', value)
        if chapter_match:
            return cls._normalize_chapter_number(chapter_match.group(1))

        compact = re.sub(r'\s+', '', value).translate(cls._SEPARATOR_TRANSLATION)
        if not re.fullmatch(r'\d+(?:\.\d+)*', compact):
            return None
        return compact

    @classmethod
    def _normalize_chapter_number(cls, value: str) -> Optional[str]:
        if value.isdigit():
            return value
        number = cls._chinese_number_to_int(value)
        return str(number) if number is not None else None

    @classmethod
    def _chinese_number_to_int(cls, value: str) -> Optional[int]:
        if not value:
            return None
        if all(char in cls._CHINESE_DIGITS for char in value):
            total = 0
            for char in value:
                total = total * 10 + cls._CHINESE_DIGITS[char]
            return total

        total = 0
        section = 0
        for char in value:
            if char in cls._CHINESE_DIGITS:
                section = cls._CHINESE_DIGITS[char]
            elif char == "十":
                total += (section or 1) * 10
                section = 0
            elif char == "百":
                total += (section or 1) * 100
                section = 0
            else:
                return None
        return total + section

    @classmethod
    def _parse_heading(cls, line: str) -> Optional[Dict[str, Any]]:
        markdown_match = re.match(r'^(#{1,6})\s*(.*?)\s*$', line)
        if not markdown_match:
            return None

        level = len(markdown_match.group(1))
        heading = markdown_match.group(2)

        chapter_match = cls._CHAPTER_HEADING.match(heading)
        if chapter_match:
            title = chapter_match.group(2).strip()
            if not title:
                title = f"第 {chapter_match.group(1)} 章"
            number = cls._normalize_chapter_number(chapter_match.group(1))
            if not number:
                return None
            return {
                "number": number,
                "title": title,
                "level": level,
                "kind": "chapter",
            }

        numbered_match = cls._NUMBERED_HEADING.match(heading)
        if not numbered_match:
            return None

        number = cls.normalize_section_number(numbered_match.group(1))
        title = numbered_match.group(2).strip()
        if not number or not title:
            return None
        return {
            "number": number,
            "title": title,
            "level": level,
            "kind": "numbered",
        }

    def extract_chapter_list(self) -> List[Dict[str, str]]:
        """
        提取教材中所有章节列表

        Returns:
            章节列表，格式：[{"number": "1.1", "title": "计算机的发展历程", "line": 123}, ...]
        """
        chapters = []
        for i, line in enumerate(self.lines):
            heading = self._parse_heading(line)
            if heading:
                chapters.append({
                    "number": heading["number"],
                    "title": heading["title"],
                    "line": i,
                    "level": heading["level"],
                    "kind": heading["kind"],
                })

        return chapters

    def extract_section(self, section_number: str) -> Optional[Dict[str, Any]]:
        """
        提取指定章节的完整内容

        Args:
            section_number: 章节号，如 "1.3" 或 "1.3.1"

        Returns:
            章节信息字典，包含 number, title, content, paragraphs
        """
        section_number = self.normalize_section_number(section_number)
        if not section_number:
            return None

        chapters = self.extract_chapter_list()

        # 查找目标章节
        target_chapter = None
        target_index = -1
        for i, chapter in enumerate(chapters):
            if chapter['number'] == section_number:
                target_chapter = chapter
                target_index = i
                break

        if not target_chapter:
            return None

        # 确定提取范围：从当前章节到下一个同级或更高级章节
        start_line = target_chapter['line']
        # 查找结束行
        end_line = len(self.lines)
        for i in range(target_index + 1, len(chapters)):
            next_chapter = chapters[i]
            if self._is_section_boundary(target_chapter, next_chapter):
                end_line = next_chapter['line']
                break

        # 提取内容
        section_lines = self.lines[start_line:end_line]
        content = '\n'.join(section_lines)

        # 拆分段落
        paragraphs = self._split_into_paragraphs(section_lines)

        return {
            "number": target_chapter['number'],
            "title": target_chapter['title'],
            "content": content,
            "paragraphs": paragraphs
        }

    @staticmethod
    def chunk_content(content: str, max_chars: int) -> List[str]:
        """Split content at paragraph boundaries while preserving every character."""
        if max_chars < 1:
            raise ValueError("max_chars 必须大于 0")
        if len(content) <= max_chars:
            return [content]

        units = re.split(r'(?<=\n\n)', content)
        chunks: List[str] = []
        current = ""
        for unit in units:
            if current and len(current) + len(unit) > max_chars:
                chunks.append(current)
                current = ""
            if len(unit) > max_chars:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(unit)
            else:
                current += unit
        if current or not chunks:
            chunks.append(current)
        return chunks

    @staticmethod
    def source_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def diagnose(self) -> List[Dict[str, Any]]:
        """Return deterministic OCR textbook structure diagnostics."""
        diagnostics: List[Dict[str, Any]] = []
        chapters = self.extract_chapter_list()
        if not chapters:
            diagnostics.append({
                "severity": "error",
                "code": "no_headings",
                "message": "未识别到带章节编号的 Markdown 标题",
            })

        counts = Counter(chapter["number"] for chapter in chapters)
        for number, count in counts.items():
            if count > 1:
                lines = [
                    chapter["line"] + 1 for chapter in chapters
                    if chapter["number"] == number
                ]
                diagnostics.append({
                    "severity": "warning",
                    "code": "duplicate_section",
                    "message": f"章节号 {number} 出现 {count} 次",
                    "section": number,
                    "lines": lines,
                })

        levels_by_depth: Dict[int, List[int]] = {}
        for chapter in chapters:
            depth = len(chapter["number"].split("."))
            levels_by_depth.setdefault(depth, []).append(chapter["level"])
        expected_levels = {
            depth: Counter(levels).most_common(1)[0][0]
            for depth, levels in levels_by_depth.items()
        }
        for chapter in chapters:
            depth = len(chapter["number"].split("."))
            expected = expected_levels[depth]
            if chapter["level"] != expected:
                diagnostics.append({
                    "severity": "warning",
                    "code": "inconsistent_heading_level",
                    "message": (
                        f"章节 {chapter['number']} 使用 H{chapter['level']}，"
                        f"同层章节通常使用 H{expected}"
                    ),
                    "section": chapter["number"],
                    "line": chapter["line"] + 1,
                })

        study_numbers = {chapter["number"] for chapter in self._study_chapters(chapters)}
        for index, chapter in enumerate(chapters):
            if chapter["number"] not in study_numbers:
                continue
            end_line = chapters[index + 1]["line"] if index + 1 < len(chapters) else len(self.lines)
            body = "\n".join(self.lines[chapter["line"] + 1:end_line]).strip()
            if not body:
                diagnostics.append({
                    "severity": "warning",
                    "code": "empty_section",
                    "message": f"章节 {chapter['number']} 在下一标题前没有正文",
                    "section": chapter["number"],
                    "line": chapter["line"] + 1,
                })

        suspicious = re.compile(
            r'^(?:#{1,6}\s*)?(?:第\s*[一二三四五六七八九十百零\d]+\s*章|\d+[.．。·\-—–]\d+)'
        )
        recognized_lines = {chapter["line"] for chapter in chapters}
        for index, line in enumerate(self.lines):
            if index not in recognized_lines and suspicious.match(line.strip()):
                diagnostics.append({
                    "severity": "warning",
                    "code": "suspicious_unparsed_heading",
                    "message": "疑似章节标题未被解析",
                    "line": index + 1,
                    "preview": line.strip()[:120],
                })

        return diagnostics

    def get_next_section(self, section_number: str) -> Optional[str]:
        """返回当前提取范围之后的下一节，跳过已包含的子节。"""
        section_number = self.normalize_section_number(section_number)
        if not section_number:
            return None

        chapters = self.extract_chapter_list()
        study_chapters = self._study_chapters(chapters)
        for index, chapter in enumerate(chapters):
            if chapter["number"] != section_number:
                continue
            for candidate in chapters[index + 1:]:
                if (
                    candidate in study_chapters
                    and self._is_section_boundary(chapter, candidate)
                ):
                    return candidate["number"]
            return None
        return None

    def get_first_study_section(self) -> Optional[str]:
        """返回第一学习单元，跳过仅用于组织子节的章标题。"""
        study_chapters = self._study_chapters(self.extract_chapter_list())
        return study_chapters[0]["number"] if study_chapters else None

    def _study_chapters(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        numbers = [chapter["number"] for chapter in chapters]
        result = []
        for chapter in chapters:
            number = chapter["number"]
            is_chapter_container = (
                "." not in number
                and any(other.startswith(number + ".") for other in numbers)
            )
            if not is_chapter_container:
                result.append(chapter)
        return result

    @staticmethod
    def _is_section_boundary(
        current: Dict[str, Any], candidate: Dict[str, Any]
    ) -> bool:
        """Return whether candidate starts after current's complete subtree."""
        current_number = current["number"]
        candidate_number = candidate["number"]

        if current.get("kind") == "chapter":
            return candidate.get("kind") == "chapter"
        if candidate.get("kind") == "chapter":
            return True
        if candidate_number.startswith(current_number + "."):
            return False

        current_parts = current_number.split(".")
        candidate_parts = candidate_number.split(".")
        if (
            len(candidate_parts) < len(current_parts)
            and candidate.get("kind") == "numbered"
            and candidate.get("level", 6) >= current.get("level", 1)
        ):
            return False
        if candidate_parts[0] != current_parts[0]:
            return True

        return True

    def _split_into_paragraphs(self, lines: List[str]) -> List[Dict[str, Any]]:
        """
        将章节内容拆分为段落

        Args:
            lines: 章节内容的行列表

        Returns:
            段落列表，每个段落包含 type, content, subtitle 等信息
        """
        paragraphs = []
        current_paragraph = []
        current_subtitle = None

        for line in lines[1:]:  # 跳过第一行（章节标题）
            stripped = line.strip()

            # 检测子标题（## 1. xxx 或 ## 1.3.1 xxx）
            subtitle_match = re.match(r'^#{1,6}\s*(.+)$', stripped)
            if subtitle_match:
                # 保存之前的段落
                if current_paragraph:
                    paragraphs.append({
                        "type": "paragraph",
                        "content": '\n'.join(current_paragraph).strip(),
                        "subtitle": current_subtitle
                    })
                    current_paragraph = []

                # 记录新的子标题
                current_subtitle = subtitle_match.group(1)
                paragraphs.append({
                    "type": "subtitle",
                    "content": current_subtitle
                })
                continue

            # 检测图片
            if re.match(r'^!\[[^\]]*\]\([^)]+\)', stripped):
                if current_paragraph:
                    paragraphs.append({
                        "type": "paragraph",
                        "content": '\n'.join(current_paragraph).strip(),
                        "subtitle": current_subtitle
                    })
                    current_paragraph = []

                paragraphs.append({
                    "type": "image",
                    "content": stripped,
                    "subtitle": current_subtitle
                })
                continue

            # 空行：段落分隔
            if not stripped:
                if current_paragraph:
                    paragraphs.append({
                        "type": "paragraph",
                        "content": '\n'.join(current_paragraph).strip(),
                        "subtitle": current_subtitle
                    })
                    current_paragraph = []
                continue

            # 普通文本行
            current_paragraph.append(line)

        # 保存最后一个段落
        if current_paragraph:
            paragraphs.append({
                "type": "paragraph",
                "content": '\n'.join(current_paragraph).strip(),
                "subtitle": current_subtitle
            })

        return paragraphs

    def search_keyword(self, keyword: str) -> List[Dict[str, str]]:
        """
        在教材中搜索关键词，返回所在章节

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的章节列表
        """
        chapters = self.extract_chapter_list()
        results = []

        for i, chapter in enumerate(chapters):
            # 确定该章节的范围
            start_line = chapter['line']
            if i + 1 < len(chapters):
                end_line = chapters[i + 1]['line']
            else:
                end_line = len(self.lines)

            # 在该章节范围内搜索关键词
            section_content = '\n'.join(self.lines[start_line:end_line])
            if keyword in section_content:
                results.append({
                    "number": chapter['number'],
                    "title": chapter['title'],
                    "preview": self._get_keyword_preview(section_content, keyword)
                })

        return results

    def _get_keyword_preview(self, content: str, keyword: str, context_length: int = 50) -> str:
        """
        获取关键词在内容中的预览片段

        Args:
            content: 内容
            keyword: 关键词
            context_length: 上下文长度

        Returns:
            预览片段
        """
        index = content.find(keyword)
        if index == -1:
            return ""

        start = max(0, index - context_length)
        end = min(len(content), index + len(keyword) + context_length)
        preview = content[start:end]

        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."

        return preview


def main():
    """测试函数"""
    import sys
    import io

    # 设置stdout为UTF-8编码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if len(sys.argv) < 3:
        print("用法: python parser.py <教材路径> <命令> [参数]")
        print("命令:")
        print("  list                 - 列出所有章节")
        print("  extract <章节号>     - 提取指定章节")
        print("  search <关键词>      - 搜索关键词")
        sys.exit(1)

    textbook_path = sys.argv[1]
    command = sys.argv[2]

    parser = TextbookParser(textbook_path)

    if command == "list":
        chapters = parser.extract_chapter_list()
        print(json.dumps(chapters, ensure_ascii=False, indent=2))

    elif command == "extract":
        if len(sys.argv) < 4:
            print("请指定章节号")
            sys.exit(1)

        section_number = sys.argv[3]
        section = parser.extract_section(section_number)

        if section:
            print(json.dumps(section, ensure_ascii=False, indent=2))
        else:
            print(f"未找到章节: {section_number}")

    elif command == "search":
        if len(sys.argv) < 4:
            print("请指定搜索关键词")
            sys.exit(1)

        keyword = sys.argv[3]
        results = parser.search_keyword(keyword)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

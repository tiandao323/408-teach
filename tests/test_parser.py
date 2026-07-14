import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from parser import TextbookParser


SAMPLE_TEXTBOOK = """# 第 1 章 绪论
章导言。

## 1．1无空格标题
第一节正文。

### 1-2 第二节
第二节正文。

#### 1.2.1 深层小节
深层正文。
![结构图](images/structure.png)

## 1.3 标准标题
第三节正文。

# 第 2 章 后续内容
## 2.1 下一章第一节
下一章正文。
"""


class TextbookParserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.textbook = Path(self.temp_dir.name) / "textbook.md"
        self.textbook.write_text(SAMPLE_TEXTBOOK, encoding="utf-8")
        self.parser = TextbookParser(str(self.textbook))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalizes_common_ocr_heading_variants(self):
        chapters = self.parser.extract_chapter_list()
        self.assertEqual(
            [chapter["number"] for chapter in chapters],
            ["1", "1.1", "1.2", "1.2.1", "1.3", "2", "2.1"],
        )
        self.assertEqual(chapters[1]["title"], "无空格标题")

    def test_normalizes_chinese_numeral_chapter_headings(self):
        textbook = Path(self.temp_dir.name) / "chinese-chapter.md"
        textbook.write_text(
            "# 第一章 绪论\n章导言。\n\n# 第十二章 后续内容\n正文。\n",
            encoding="utf-8",
        )

        parser = TextbookParser(str(textbook))
        chapters = parser.extract_chapter_list()

        self.assertEqual([chapter["number"] for chapter in chapters], ["1", "12"])
        self.assertEqual(TextbookParser.normalize_section_number("第十章"), "10")

    def test_extracts_parent_section_through_children(self):
        section = self.parser.extract_section("1．2")
        self.assertIn("第二节正文", section["content"])
        self.assertIn("深层正文", section["content"])
        self.assertNotIn("第三节正文", section["content"])

    def test_ocr_local_numbered_headings_do_not_truncate_parent_section(self):
        textbook = Path(self.temp_dir.name) / "ocr-numbering.md"
        textbook.write_text(
            "# 第 1 章 绪论\n"
            "## 1.3 系统层次\n父节正文。\n"
            "## 1. 算法和程序\n局部内容一。\n"
            "## 2. 编程语言\n局部内容二。\n"
            "## 1.3.2 不同用户\n子节正文。\n"
            "## 1.4 下一节\n下一节正文。\n",
            encoding="utf-8",
        )

        parser = TextbookParser(str(textbook))
        section = parser.extract_section("1.3")

        self.assertIn("局部内容一", section["content"])
        self.assertIn("局部内容二", section["content"])
        self.assertIn("子节正文", section["content"])
        self.assertNotIn("下一节正文", section["content"])
        self.assertEqual(parser.get_next_section("1.3"), "1.4")

    def test_recognizes_images_with_alt_text(self):
        section = self.parser.extract_section("1.2.1")
        images = [p for p in section["paragraphs"] if p["type"] == "image"]
        self.assertEqual(len(images), 1)

    def test_next_section_skips_descendants_already_in_parent_extract(self):
        self.assertEqual(self.parser.get_next_section("1.2"), "1.3")
        self.assertEqual(self.parser.get_next_section("1.2.1"), "1.3")
        self.assertEqual(self.parser.get_next_section("1.3"), "2.1")
        self.assertIsNone(self.parser.get_next_section("2.1"))

    def test_first_study_section_skips_chapter_container(self):
        self.assertEqual(self.parser.get_first_study_section(), "1.1")

    def test_chunking_preserves_every_source_character(self):
        content = self.parser.extract_section("1.2")["content"]
        chunks = self.parser.chunk_content(content, 30)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), content)
        self.assertEqual(len(self.parser.source_sha256(content)), 64)

    def test_doctor_reports_duplicate_empty_and_unparsed_headings(self):
        textbook = Path(self.temp_dir.name) / "broken.md"
        textbook.write_text(
            "# 1.1 重复\n\n# 1.1 重复\n正文\n\n2.2 没有井号\n",
            encoding="utf-8",
        )
        diagnostics = TextbookParser(str(textbook)).diagnose()
        codes = {item["code"] for item in diagnostics}

        self.assertIn("duplicate_section", codes)
        self.assertIn("empty_section", codes)
        self.assertIn("suspicious_unparsed_heading", codes)


if __name__ == "__main__":
    unittest.main()

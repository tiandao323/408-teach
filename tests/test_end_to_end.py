import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
MAIN = SKILL_DIR / "main.py"
VALIDATOR = SKILL_DIR / "scripts" / "validate_lecture.py"


LECTURE = """# 408考试大纲

本节对应测试大纲。

## 408os 考频分析

- 数据范围：2009-2026，共 18 年真题统计。
- 本节相关知识点：第一节，等级 S，题量 1，分值 2，考察年份 1 年。
- 本节讲解策略：测试讲义按深讲处理。

# 1.1 第一节
正文一。
![结构图](images/structure.png)

### 重要性判断
- 等级：S
- 依据：测试用 408os 考频分析。
- 学习策略：深讲

### 核心概念与深度讲解
#### 这段在说什么
解释第一节。
#### 408 怎么考
考查第一节定义。
#### 易错点
不要混淆第一节。
"""


class EndToEndTests(unittest.TestCase):
    def run_command(self, *args):
        return subprocess.run(
            [sys.executable, *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_project_archives_inline_lecture_image_and_advances(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            image_dir = project / "images"
            image_dir.mkdir()
            (image_dir / "structure.png").write_bytes(b"test-image")
            textbook = project / "book.md"
            textbook.write_text(
                "# 1．1第一节\n正文一。\n![结构图](images/structure.png)\n\n"
                "# 1-2 第二节\n正文二。\n",
                encoding="utf-8",
            )

            self.run_command(MAIN, "init", project)
            self.run_command(MAIN, "add", "测试教材", textbook, project)

            extracted = self.run_command(MAIN, "extract", "1．1", project)
            extracted_data = json.loads(extracted.stdout)
            self.assertEqual(extracted_data["section"]["number"], "1.1")

            lecture = project / "讲义.md"
            lecture.write_text(LECTURE, encoding="utf-8")

            completed = self.run_command(MAIN, "finalize", "1.1", lecture, project)
            completed_data = json.loads(completed.stdout)
            finalized = Path(completed_data["finalized_path"])
            self.assertEqual(completed_data["next"], "1.2")
            self.assertTrue(finalized.is_file())
            self.assertTrue((finalized.parent / "images" / "structure.png").is_file())
            self.assertIn(
                "images/structure.png",
                finalized.read_text(encoding="utf-8"),
            )

            continued = self.run_command(MAIN, "continue", project)
            continued_data = json.loads(continued.stdout)
            self.assertEqual(continued_data["section"]["number"], "1.2")

    def test_archives_image_link_with_spaces_and_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            image_dir = project / "images"
            image_dir.mkdir()
            (image_dir / "structure space.png").write_bytes(b"test-image")
            textbook = project / "book.md"
            textbook.write_text(
                "# 1.1 第一节\n正文一。\n![结构图](<images/structure space.png> \"图\")\n",
                encoding="utf-8",
            )

            self.run_command(MAIN, "init", project)
            self.run_command(MAIN, "add", "测试教材", textbook, project)

            lecture = project / "讲义.md"
            lecture.write_text(
                LECTURE.replace(
                    "![结构图](images/structure.png)",
                    "![结构图](<images/structure space.png> \"图\")",
                ),
                encoding="utf-8",
            )

            completed = self.run_command(MAIN, "finalize", "1.1", lecture, project)
            finalized = Path(json.loads(completed.stdout)["finalized_path"])

            self.assertTrue((finalized.parent / "images" / "structure space.png").is_file())
            self.assertIn(
                "![结构图](<images/structure space.png> \"图\")",
                finalized.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()

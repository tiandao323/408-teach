import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
MAIN = SKILL_DIR / "main.py"

VALID_LECTURE = """# 1.1 第一节
第一段。

第二段很长。

### 核心概念与深度讲解
#### 这段在说什么
解释第一节。
#### 408 怎么考
考查第一节定义。
#### 易错点
不要混淆第一节。
"""


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        self.textbook = self.project / "book.md"
        self.textbook.write_text(
            "# 1.1 第一节\n第一段。\n\n第二段很长。\n\n# 1.2 第二节\n第二节正文。\n",
            encoding="utf-8",
        )
        self.run_command(MAIN, "init", self.project)
        self.run_command(MAIN, "add", "测试教材", self.textbook, self.project)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_command(self, *args, check=True):
        return subprocess.run(
            [sys.executable, *map(str, args)],
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_failed_finalize_leaves_progress_and_destination_unchanged(self):
        draft = self.project / "invalid.md"
        draft.write_text("# 1.1 第一节\n\n内容不足。", encoding="utf-8")

        result = self.run_command(
            MAIN, "finalize", "1.1", draft, self.project, check=False
        )

        self.assertNotEqual(result.returncode, 0)
        progress = json.loads(
            (self.project / "测试教材" / "progress.json").read_text(encoding="utf-8")
        )
        self.assertEqual(progress["completed"], [])
        self.assertEqual(list((self.project / "测试教材" / "lectures").rglob("讲义.md")), [])

    def test_missing_local_image_does_not_advance_progress(self):
        draft = self.project / "missing-image.md"
        draft.write_text(
            VALID_LECTURE.replace(
                "第一段。",
                "第一段。\n![缺失图片](images/missing.png)",
            ),
            encoding="utf-8",
        )

        result = self.run_command(
            MAIN, "finalize", "1.1", draft, self.project, check=False
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("图片不存在", result.stderr)
        progress = json.loads(
            (self.project / "测试教材" / "progress.json").read_text(encoding="utf-8")
        )
        self.assertEqual(progress["completed"], [])
        self.assertEqual(list((self.project / "测试教材" / "lectures").rglob("讲义.md")), [])

    def test_partial_source_body_does_not_advance_progress(self):
        draft = self.project / "partial-source.md"
        draft.write_text(
            VALID_LECTURE.replace("\n\n第二段很长。", ""),
            encoding="utf-8",
        )

        result = self.run_command(
            MAIN, "finalize", "1.1", draft, self.project, check=False
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("教材正文", result.stderr)
        progress = json.loads(
            (self.project / "测试教材" / "progress.json").read_text(encoding="utf-8")
        )
        self.assertEqual(progress["completed"], [])
        self.assertEqual(list((self.project / "测试教材" / "lectures").rglob("讲义.md")), [])

    def test_finalize_is_idempotent(self):
        draft = self.project / "valid.md"
        draft.write_text(VALID_LECTURE, encoding="utf-8")

        first = self.run_command(MAIN, "finalize", "1.1", draft, self.project)
        second = self.run_command(MAIN, "finalize", "1.1", draft, self.project)

        self.assertEqual(
            json.loads(first.stdout)["finalized_path"],
            json.loads(second.stdout)["finalized_path"],
        )
        progress = json.loads(
            (self.project / "测试教材" / "progress.json").read_text(encoding="utf-8")
        )
        self.assertEqual(progress["completed"], ["1.1"])
        self.assertEqual(progress["current"], "1.2")

    def test_chunked_extract_reports_bounds_and_source_hash(self):
        result = self.run_command(
            MAIN, "extract", "1.1", self.project, "--max-chars", "20", "--chunk", "2"
        )
        data = json.loads(result.stdout)

        self.assertEqual(data["chunk_index"], 2)
        self.assertGreaterEqual(data["chunk_count"], 2)
        self.assertEqual(len(data["source_sha256"]), 64)

        invalid = self.run_command(
            MAIN, "extract", "1.1", self.project, "--max-chars", "20", "--chunk", "99",
            check=False,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("超出范围", invalid.stderr)

    def test_continue_from_empty_progress_emits_pure_json(self):
        result = self.run_command(MAIN, "continue", self.project)
        data = json.loads(result.stdout)

        self.assertEqual(data["type"], "section")
        self.assertEqual(data["section"]["number"], "1.1")
        self.assertTrue(data["started_from_first"])

    def test_multiple_keyword_matches_emit_pure_json(self):
        result = self.run_command(MAIN, "extract", "节", self.project)
        data = json.loads(result.stdout)

        self.assertEqual(data["type"], "multiple_matches")
        self.assertGreaterEqual(len(data["results"]), 2)
        self.assertNotIn("找到", result.stdout)

    def test_doctor_returns_machine_readable_diagnostics(self):
        result = self.run_command(MAIN, "doctor", self.project)
        data = json.loads(result.stdout)

        self.assertEqual(data["textbook"], "测试教材")
        self.assertFalse(data["fatal"])
        self.assertIsInstance(data["diagnostics"], list)

    def test_doctor_blocks_when_no_headings_are_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            textbook = project / "no-headings.md"
            textbook.write_text("只有正文，没有 Markdown 章节标题。", encoding="utf-8")

            self.run_command(MAIN, "init", project)
            self.run_command(MAIN, "add", "无标题教材", textbook, project)
            result = self.run_command(MAIN, "doctor", project, check=False)
            data = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(data["fatal"])
            self.assertIn("no_headings", {item["code"] for item in data["diagnostics"]})

    def test_help_option_succeeds(self):
        result = self.run_command(MAIN, "--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("用法: python main.py", result.stdout)


if __name__ == "__main__":
    unittest.main()

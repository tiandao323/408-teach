import json
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
CONFIG_SCRIPT = SKILL_DIR / "scripts" / "config.py"

from config import ConfigManager


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self.textbook = self.project_dir / "book.md"
        self.textbook.write_text("# 1.1 第一节\n正文", encoding="utf-8")
        self.manager = ConfigManager(str(self.project_dir))
        with redirect_stdout(io.StringIO()):
            self.manager.init_project()
            self.manager.add_textbook("操作系统", str(self.textbook))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_update_without_next_section_preserves_current(self):
        progress_path = self.project_dir / "操作系统" / "progress.json"
        progress_path.write_text(
            json.dumps({"completed": [], "current": "1.2", "finished": False}),
            encoding="utf-8",
        )

        self.manager.update_progress("操作系统", "1.1")

        progress = self.manager.get_progress("操作系统")
        self.assertEqual(progress["current"], "1.2")
        self.assertFalse(progress["finished"])

    def test_explicit_none_marks_textbook_finished(self):
        self.manager.update_progress("操作系统", "1.1", next_section=None)

        progress = self.manager.get_progress("操作系统")
        self.assertIsNone(progress["current"])
        self.assertTrue(progress["finished"])

    def test_cli_update_without_next_section_preserves_current(self):
        progress_path = self.project_dir / "操作系统" / "progress.json"
        progress_path.write_text(
            json.dumps({"completed": [], "current": "1.2", "finished": False}),
            encoding="utf-8",
        )

        subprocess.run(
            [sys.executable, str(CONFIG_SCRIPT), "update", "操作系统", "1.1"],
            cwd=self.project_dir,
            check=True,
            capture_output=True,
        )

        progress = self.manager.get_progress("操作系统")
        self.assertEqual(progress["current"], "1.2")
        self.assertFalse(progress["finished"])

    def test_rejects_unsafe_textbook_output_names(self):
        for name in ("..", "../outside", "CON", "bad:name"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.manager.add_textbook(name, str(self.textbook))

    def test_failed_atomic_write_preserves_existing_config(self):
        original = (self.project_dir / ".408-config.json").read_text(encoding="utf-8")

        with mock.patch("config.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                self.manager.switch_textbook("操作系统")

        self.assertEqual(
            (self.project_dir / ".408-config.json").read_text(encoding="utf-8"),
            original,
        )


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
MAIN = SKILL_DIR / "main.py"


class MaterialRegistrationTests(unittest.TestCase):
    def run_command(self, *args):
        return subprocess.run(
            [sys.executable, *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_add_textbook_records_pdf_authority_in_extract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            markdown = project / "book.md"
            markdown.write_text("# 1.1 第一节\n正文。", encoding="utf-8")
            source_pdf = project / "book.pdf"
            source_pdf.write_bytes(b"%PDF-1.4\n")

            self.run_command(MAIN, "init", project)
            self.run_command(
                MAIN,
                "add",
                "组成原理",
                markdown,
                project,
                "--source-pdf",
                source_pdf,
                "--authority",
                "pdf",
                "--md-role",
                "section_index_and_cache",
            )

            extracted = self.run_command(MAIN, "extract", "1.1", project)
            data = json.loads(extracted.stdout)

            self.assertEqual(data["source_authority"], "pdf")
            self.assertEqual(data["source_pdf"], str(source_pdf.resolve()))
            self.assertEqual(data["derived_markdown"], str(markdown.resolve()))
            self.assertEqual(data["markdown_role"], "section_index_and_cache")

    def test_bootstrap_computer_organization_registers_materials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            ocr_dir = project / "计算机组成与系统结构-第3版-袁春风" / "ocr"
            ocr_dir.mkdir(parents=True)
            stem = "11计算机组成与系统结构-第3版-袁春风"
            markdown = ocr_dir / f"{stem}.md"
            markdown.write_text("# 1.1 第一节\n正文。", encoding="utf-8")
            source_pdf = ocr_dir / f"{stem}_origin.pdf"
            source_pdf.write_bytes(b"%PDF-1.4\n")
            syllabus = project / "计算机组成原理大纲.md"
            syllabus.write_text("# 计算机组成原理", encoding="utf-8")
            papers_dir = project / "计算机组成原理真题"
            papers_dir.mkdir()
            (papers_dir / "计算机系统概述真题.pdf").write_bytes(b"%PDF-1.4\n")
            (papers_dir / "数据的机器表示.pdf").write_bytes(b"%PDF-1.4\n")

            result = self.run_command(MAIN, "bootstrap-co", project)
            data = json.loads(result.stdout)

            self.assertEqual(data["subject"], "计算机组成原理")
            self.assertEqual(data["textbook"]["sourceAuthority"], "pdf")
            self.assertEqual(data["textbook"]["sourcePdf"], str(source_pdf.resolve()))
            self.assertEqual(data["textbook"]["path"], str(markdown.resolve()))
            self.assertEqual(data["materials"]["syllabus"]["path"], str(syllabus.resolve()))
            self.assertEqual(len(data["materials"]["papers"]), 2)
            self.assertEqual(data["materials"]["futureIndex"]["status"], "not_built")

            materials = self.run_command(MAIN, "materials", project)
            materials_data = json.loads(materials.stdout)
            self.assertIn("计算机组成原理", materials_data["subjects"])


if __name__ == "__main__":
    unittest.main()

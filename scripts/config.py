#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
管理 .408-config.json 和 progress.json
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


_UNSET = object()
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def atomic_write_text(path: Path, content: str) -> None:
    """Write UTF-8 text without exposing a partially written destination."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write binary content without exposing a partially written destination."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def validate_path_component(value: str, label: str = "名称") -> str:
    """Require one portable Windows path component."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}不能为空")
    value = value.strip()
    if value in {".", ".."} or _INVALID_COMPONENT.search(value):
        raise ValueError(f"{label}包含 Windows 路径非法字符: {value}")
    if value.endswith((" ", ".")):
        raise ValueError(f"{label}不能以空格或句点结尾: {value}")
    if value.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{label}不能使用 Windows 保留名称: {value}")
    return value


def sanitize_path_component(value: str, fallback: str = "未命名章节") -> str:
    """Convert an OCR-derived title to a safe output directory component."""
    value = _INVALID_COMPONENT.sub("_", value).strip().rstrip(".")
    if not value or value.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        value = fallback
    return value[:80].rstrip(" .") or fallback


class ConfigManager:
    """配置管理器"""

    def __init__(self, project_dir: str = "."):
        """
        初始化配置管理器

        Args:
            project_dir: 项目根目录
        """
        self.project_dir = Path(project_dir).resolve()
        self.config_path = self.project_dir / ".408-config.json"

    def ensure_project(self) -> bool:
        """Create a project config if needed without printing."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            return False

        config = self._new_config()
        self._save_config(config)
        return True

    def init_project(self):
        """初始化项目，创建配置文件"""
        created = self.ensure_project()
        if not created:
            print(f"项目已初始化: {self.config_path}")
            return

        print(f"✅ 项目初始化成功: {self.config_path}")

    def add_textbook(
        self,
        name: str,
        textbook_path: str,
        *,
        source_pdf: Optional[str] = None,
        source_authority: str = "markdown",
        markdown_role: str = "primary_source",
        quiet: bool = False,
    ):
        """
        添加教材

        Args:
            name: 教材名称（如"计算机组成原理"）
            textbook_path: 教材文件路径
        """
        name = validate_path_component(name, "教材名称")
        config = self._load_config()
        source_authority = source_authority.strip().lower()
        if source_authority not in {"markdown", "pdf"}:
            raise ValueError("教材权威来源只能是 markdown 或 pdf")

        # 检查教材文件是否存在
        textbook_file = Path(textbook_path)
        if not textbook_file.is_file():
            raise FileNotFoundError(f"教材文件不存在: {textbook_path}")
        textbook_file = textbook_file.resolve()

        source_pdf_path = None
        if source_pdf:
            source_pdf_path = Path(source_pdf)
            if not source_pdf_path.is_file():
                raise FileNotFoundError(f"教材 PDF 不存在: {source_pdf}")
            source_pdf_path = source_pdf_path.resolve()
        elif source_authority == "pdf":
            raise ValueError("source_authority=pdf 时必须提供 source_pdf")

        # 创建教材输出目录
        output_dir = self._resolve_output_dir(name)
        output_dir.mkdir(exist_ok=True)
        (output_dir / "lectures").mkdir(exist_ok=True)

        # 初始化进度文件
        progress_path = output_dir / "progress.json"
        if not progress_path.exists():
            progress = {
                "completed": [],
                "current": None,
                "finished": False
            }
            self._save_json(progress_path, progress)

        # 更新配置
        textbook_info = {
            "path": str(textbook_file),
            "outputDir": name,
            "sourceAuthority": source_authority,
            "derivedMarkdown": str(textbook_file),
            "markdownRole": markdown_role,
        }
        if source_pdf_path:
            textbook_info["sourcePdf"] = str(source_pdf_path)
        config["textbooks"][name] = textbook_info

        # 如果是第一本教材，设为当前教材
        if not config["currentTextbook"]:
            config["currentTextbook"] = name

        self._save_config(config)
        if not quiet:
            print(f"✅ 已添加教材: {name}")
            print(f"   路径: {textbook_path}")
            if source_pdf_path:
                print(f"   PDF: {source_pdf_path}")
            print(f"   输出: {output_dir}")

    def switch_textbook(self, name: str):
        """
        切换当前教材

        Args:
            name: 教材名称
        """
        config = self._load_config()

        if name not in config["textbooks"]:
            raise ValueError(f"教材不存在: {name}，可用教材: {list(config['textbooks'].keys())}")

        config["currentTextbook"] = name
        self._save_config(config)
        print(f"✅ 已切换到教材: {name}")

    def get_current_textbook(self) -> Optional[Dict[str, str]]:
        """
        获取当前教材信息

        Returns:
            教材信息字典，包含 name, path, outputDir
        """
        config = self._load_config()
        current_name = config.get("currentTextbook")

        if not current_name:
            return None

        textbook_info = config["textbooks"].get(current_name)
        if not textbook_info:
            return None

        return {
            "name": current_name,
            **textbook_info,
        }

    def get_all_textbooks(self) -> Dict[str, Dict[str, str]]:
        """
        获取所有教材列表

        Returns:
            教材字典
        """
        config = self._load_config()
        return config.get("textbooks", {})

    def register_subject_materials(
        self,
        subject: str,
        *,
        textbook_name: Optional[str] = None,
        syllabus_path: Optional[str] = None,
        paper_paths: Optional[List[str]] = None,
        future_index_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register exam-facing materials for one 408 subject."""
        subject = validate_path_component(subject, "科目名称")
        config = self._load_config()

        if textbook_name is not None and textbook_name not in config["textbooks"]:
            raise ValueError(f"教材不存在: {textbook_name}")

        subject_info: Dict[str, Any] = dict(config.get("subjects", {}).get(subject, {}))
        if textbook_name is not None:
            subject_info["textbook"] = textbook_name

        if syllabus_path is not None:
            syllabus = Path(syllabus_path)
            if not syllabus.is_file():
                raise FileNotFoundError(f"考纲文件不存在: {syllabus_path}")
            subject_info["syllabus"] = {
                "path": str(syllabus.resolve()),
                "encoding": "utf-8",
                "role": "exam_scope",
            }

        if paper_paths is not None:
            papers = []
            for paper_path in sorted(paper_paths, key=lambda value: Path(value).name):
                paper = Path(paper_path)
                if not paper.is_file():
                    raise FileNotFoundError(f"真题文件不存在: {paper_path}")
                papers.append({
                    "title": paper.stem,
                    "path": str(paper.resolve()),
                    "role": "chapter_past_paper",
                })
            subject_info["papers"] = papers

        if future_index_dir is not None:
            subject_info["futureIndex"] = {
                "status": "not_built",
                "directory": future_index_dir,
                "chunks": "chunks.jsonl",
                "syllabusMap": "syllabus-map.json",
                "questions": "questions.jsonl",
                "mistakes": "mistakes.jsonl",
            }

        config.setdefault("subjects", {})[subject] = subject_info
        self._save_config(config)
        return subject_info

    def get_subject_materials(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """Return registered 408 subject materials."""
        config = self._load_config()
        subjects = config.get("subjects", {})
        if subject is None:
            return subjects
        if subject not in subjects:
            raise ValueError(f"科目不存在: {subject}，可用科目: {list(subjects.keys())}")
        return subjects[subject]

    def get_output_dir(self, textbook_name: str) -> Path:
        """Return the configured textbook output directory inside the project."""
        config = self._load_config()
        textbook_info = config["textbooks"].get(textbook_name)
        if not textbook_info:
            raise ValueError(f"教材不存在: {textbook_name}")
        return self._resolve_output_dir(textbook_info["outputDir"])

    def update_progress(self, textbook_name: str, section_number: str, next_section: Any = _UNSET):
        """
        更新学习进度

        Args:
            textbook_name: 教材名称
            section_number: 已完成的章节号
            next_section: 下一节章节号；省略时保留当前进度，显式传入 None 表示全书完成
        """
        config = self._load_config()
        textbook_info = config["textbooks"].get(textbook_name)

        if not textbook_info:
            raise ValueError(f"教材不存在: {textbook_name}")

        progress_path = self._resolve_output_dir(textbook_info["outputDir"]) / "progress.json"
        progress = self._load_progress(progress_path)

        # 添加到已完成列表（去重）
        if section_number not in progress["completed"]:
            progress["completed"].append(section_number)

        # 只有调用方明确给出下一节时才推进，避免可选参数清空进度。
        if next_section is not _UNSET:
            progress["current"] = next_section
            progress["finished"] = next_section is None

        self._save_json(progress_path, progress)

    def get_progress(self, textbook_name: str) -> Dict[str, Any]:
        """
        获取学习进度

        Args:
            textbook_name: 教材名称

        Returns:
            进度信息
        """
        config = self._load_config()
        textbook_info = config["textbooks"].get(textbook_name)

        if not textbook_info:
            raise ValueError(f"教材不存在: {textbook_name}")

        progress_path = self._resolve_output_dir(textbook_info["outputDir"]) / "progress.json"
        return self._load_progress(progress_path)

    def get_all_progress(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有教材的学习进度

        Returns:
            所有教材的进度字典
        """
        config = self._load_config()
        all_progress = {}

        for name in config["textbooks"]:
            try:
                all_progress[name] = self.get_progress(name)
            except Exception as e:
                all_progress[name] = {"error": str(e)}

        return all_progress

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在，请先运行 init 命令: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return self._normalize_config(json.load(f))

    def _save_config(self, config: Dict):
        """保存配置文件"""
        self._save_json(self.config_path, self._normalize_config(config))

    def _save_json(self, path: Path, data: Dict) -> None:
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))

    def _new_config(self) -> Dict[str, Any]:
        return {
            "textbooks": {},
            "currentTextbook": None,
            "subjects": {},
        }

    def _normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        config.setdefault("textbooks", {})
        config.setdefault("currentTextbook", None)
        config.setdefault("subjects", {})
        return config

    def _resolve_output_dir(self, output_dir: str) -> Path:
        output_dir = validate_path_component(output_dir, "教材输出目录")
        resolved = (self.project_dir / output_dir).resolve()
        try:
            resolved.relative_to(self.project_dir)
        except ValueError as exc:
            raise ValueError(f"教材输出目录超出项目目录: {output_dir}") from exc
        return resolved

    def _load_progress(self, progress_path: Path) -> Dict:
        """加载进度文件"""
        if not progress_path.exists():
            return {"completed": [], "current": None, "finished": False}

        with open(progress_path, 'r', encoding='utf-8') as f:
            progress = json.load(f)
        progress.setdefault("completed", [])
        progress.setdefault("current", None)
        progress.setdefault("finished", False)
        return progress


def main():
    """测试函数"""
    import sys
    import io

    # 设置stdout为UTF-8编码
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if len(sys.argv) < 2:
        print("用法: python config.py <命令> [参数]")
        print("命令:")
        print("  init                              - 初始化项目")
        print("  add <教材名> <教材路径>            - 添加教材")
        print("  switch <教材名>                   - 切换教材")
        print("  current                           - 显示当前教材")
        print("  list                              - 列出所有教材")
        print("  progress <教材名>                 - 查看进度")
        print("  update <教材名> <章节号> [下一节] - 更新进度")
        sys.exit(1)

    command = sys.argv[1]
    manager = ConfigManager()

    if command == "init":
        manager.init_project()

    elif command == "add":
        if len(sys.argv) < 4:
            print("请指定教材名和路径")
            sys.exit(1)
        name = sys.argv[2]
        path = sys.argv[3]
        manager.add_textbook(name, path)

    elif command == "switch":
        if len(sys.argv) < 3:
            print("请指定教材名")
            sys.exit(1)
        name = sys.argv[2]
        manager.switch_textbook(name)

    elif command == "current":
        textbook = manager.get_current_textbook()
        if textbook:
            print(json.dumps(textbook, ensure_ascii=False, indent=2))
        else:
            print("未设置当前教材")

    elif command == "list":
        textbooks = manager.get_all_textbooks()
        print(json.dumps(textbooks, ensure_ascii=False, indent=2))

    elif command == "progress":
        if len(sys.argv) < 3:
            print("请指定教材名")
            sys.exit(1)
        name = sys.argv[2]
        progress = manager.get_progress(name)
        print(json.dumps(progress, ensure_ascii=False, indent=2))

    elif command == "update":
        if len(sys.argv) < 4:
            print("请指定教材名和章节号")
            sys.exit(1)
        name = sys.argv[2]
        section = sys.argv[3]
        if len(sys.argv) > 4:
            manager.update_progress(name, section, sys.argv[4])
        else:
            manager.update_progress(name, section)
        print(f"✅ 已更新进度: {section}")

    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

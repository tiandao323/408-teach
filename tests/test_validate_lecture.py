import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from validate_lecture import validate_lecture


SOURCE = """## 1.1 第一节
第一节原文。
# 这不是教材章节标题

### 1.1.1 子节
子节原文。
"""

VALID_LECTURE = """# 1.1 第一节

第一节原文。
## 这不是教材章节标题

### 核心概念与深度讲解
#### 这段在说什么
解释第一节。
#### 408 怎么考
考查第一节定义。
#### 易错点
不要混淆第一节。

```text
# 围栏内不是讲义标题
```

## 1.1.1 子节

子节原文。

### 核心概念与深度讲解
#### 这段在说什么
解释子节。
#### 408 怎么考
考查子节定义。
#### 易错点
不要混淆子节。
"""


class LectureValidationTests(unittest.TestCase):
    def test_accepts_complete_inline_lecture(self):
        self.assertEqual(
            validate_lecture(VALID_LECTURE, "1.1", source_content=SOURCE),
            [],
        )

    def test_accepts_syllabus_preface_as_first_top_level_heading(self):
        lecture = "# 408考试大纲\n\n本节对应大纲。\n\n" + VALID_LECTURE

        self.assertEqual(
            validate_lecture(lecture, "1.1", source_content=SOURCE),
            [],
        )

    def test_rejects_two_top_level_headings_without_syllabus_preface(self):
        lecture = "# 临时说明\n\n不是大纲。\n\n" + VALID_LECTURE

        errors = validate_lecture(lecture, "1.1", source_content=SOURCE)

        self.assertTrue(any("408考试大纲" in error for error in errors))

    def test_rejects_wrong_section_and_missing_source_heading(self):
        invalid = VALID_LECTURE.replace("# 1.1 第一节", "# 2.1 第一节")
        invalid = invalid.replace("## 1.1.1 子节", "")

        errors = validate_lecture(invalid, "1.1", source_content=SOURCE)

        self.assertTrue(any("目标章节号" in error for error in errors))
        self.assertTrue(any("教材标题" in error for error in errors))

    def test_rejects_missing_inline_explanation(self):
        invalid = VALID_LECTURE.rsplit("### 核心概念与深度讲解", 1)[0]

        errors = validate_lecture(invalid, "1.1", source_content=SOURCE)

        self.assertTrue(any("缺少就地深度讲解" in error for error in errors))

    def test_rejects_missing_source_body_before_explanation(self):
        invalid = """# 1.1 第一节

### 核心概念与深度讲解
#### 这段在说什么
解释第一节。
#### 408 怎么考
考查第一节定义。
#### 易错点
不要混淆第一节。

## 1.1.1 子节

### 核心概念与深度讲解
#### 这段在说什么
解释子节。
#### 408 怎么考
考查子节定义。
#### 易错点
不要混淆子节。
"""

        errors = validate_lecture(invalid, "1.1", source_content=SOURCE)

        self.assertTrue(any("教材正文" in error for error in errors))

    def test_rejects_weak_explanation_placeholder_and_unclosed_fence(self):
        invalid = VALID_LECTURE.replace("#### 408 怎么考\n考查子节定义。\n", "")
        invalid += "\n深度讲解1.1.1 子节\n```python\nprint('x')\n"

        errors = validate_lecture(invalid, "1.1", source_content=SOURCE)

        self.assertTrue(any("408 考法" in error for error in errors))
        self.assertTrue(any("占位" in error for error in errors))
        self.assertTrue(any("代码围栏" in error for error in errors))

    def test_rejects_misordered_source_headings(self):
        invalid = VALID_LECTURE.replace("# 1.1 第一节", "# 临时标题")
        invalid = invalid.replace("## 1.1.1 子节", "# 1.1 第一节", 1)
        invalid = invalid.replace("# 临时标题", "## 1.1.1 子节", 1)

        errors = validate_lecture(invalid, source_content=SOURCE)

        self.assertTrue(any("顺序" in error for error in errors))

    def test_allows_self_drawn_mermaid_instead_of_source_image_link(self):
        source = """## 1.1 第一节
图1.1说明原理。
![](images/source.png)
图1.1 原理图
"""
        lecture = """# 1.1 第一节

图1.1说明原理。
图1.1 原理图（本讲义按教材图意自绘，不引用原图文件）

```mermaid
flowchart TD
  A --> B
```

### 核心概念与深度讲解
#### 这段在说什么
解释第一节。
#### 408 怎么考
考查第一节定义。
#### 易错点
不要混淆第一节。
"""

        self.assertEqual(
            validate_lecture(lecture, "1.1", source_content=source),
            [],
        )


if __name__ == "__main__":
    unittest.main()

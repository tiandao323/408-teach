# 408 Materials Registry

Use this file when selecting or verifying local 408 study materials.

## Current Computer-Organization Project

Project root:

```text
D:\co-2
```

Registered subject:

```text
计算机组成原理
```

Textbook:

```text
source_pdf: D:\co-2\计算机组成与系统结构-第3版-袁春风\ocr\11计算机组成与系统结构-第3版-袁春风_origin.pdf
derived_markdown: D:\co-2\计算机组成与系统结构-第3版-袁春风\ocr\11计算机组成与系统结构-第3版-袁春风.md
source_authority: pdf
markdown_role: section_index_and_cache
```

Use the Markdown for section lookup and extraction. Use the PDF as the authority for wording, formulas, tables, figures, and OCR correction.

Syllabus:

```text
D:\co-2\计算机组成原理大纲.md
encoding: utf-8
role: exam_scope
```

Past-paper PDFs:

```text
D:\co-2\计算机组成原理真题\计算机系统概述真题.pdf
D:\co-2\计算机组成原理真题\数据的机器表示.pdf
D:\co-2\计算机组成原理真题\第三章 存储系统.pdf
D:\co-2\计算机组成原理真题\第四章 指令系统.pdf
D:\co-2\计算机组成原理真题\第五章 中央处理器.pdf
D:\co-2\计算机组成原理真题\总线.pdf
D:\co-2\计算机组成原理真题\IO系统.pdf
```

Bootstrap command:

```bash
python C:/Users/大爱仙尊/.agents/skills/408-teach/main.py bootstrap-co D:\co-2
```

## Extending to Other 408 Subjects

For 操作系统、计算机网络、数据结构, keep the same shape:

```json
{
  "textbooks": {
    "科目名": {
      "path": "derived markdown used for section extraction",
      "outputDir": "科目名",
      "sourceAuthority": "pdf",
      "sourcePdf": "authoritative textbook pdf",
      "derivedMarkdown": "derived markdown cache",
      "markdownRole": "section_index_and_cache"
    }
  },
  "subjects": {
    "科目名": {
      "textbook": "科目名",
      "syllabus": {
        "path": "exam syllabus markdown",
        "encoding": "utf-8",
        "role": "exam_scope"
      },
      "papers": [
        {
          "title": "chapter or topic name",
          "path": "past-paper pdf",
          "role": "chapter_past_paper"
        }
      ],
      "futureIndex": {
        "status": "not_built",
        "directory": ".408-index/科目名"
      }
    }
  }
}
```

Prefer one subject per registered textbook unless a single textbook genuinely covers multiple 408 subjects.

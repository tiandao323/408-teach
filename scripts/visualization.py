#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可视化生成模块
判断是否需要生成可视化，并生成HTML文件
"""

import re
from typing import List, Dict, Optional


class VisualizationGenerator:
    """可视化生成器"""

    def __init__(self):
        """初始化生成器"""
        self.visualization_scenarios = {
            "层次结构": ["层次", "层级", "抽象层", "分层", "hierarchy"],
            "流程步骤": ["步骤", "过程", "流程", "执行", "转换", "process", "flow"],
            "状态转换": ["状态", "切换", "转移", "state"],
            "组件关系": ["组成", "结构", "部件", "组件", "模块", "architecture"],
            "对比关系": ["区别", "对比", "比较", "不同", "差异"]
        }

    def needs_visualization(self, content: str, has_images: bool = False) -> bool:
        """
        判断内容是否需要可视化

        Args:
            content: 章节内容
            has_images: 教材中是否包含图片

        Returns:
            是否需要生成可视化
        """
        # 如果教材有图片，肯定需要可视化
        if has_images:
            return True

        # 检测内容是否匹配可视化场景
        for scenario, keywords in self.visualization_scenarios.items():
            for keyword in keywords:
                if keyword in content:
                    return True

        return False

    def identify_scenarios(self, paragraphs: List[Dict]) -> List[Dict[str, str]]:
        """
        识别段落中的可视化场景

        Args:
            paragraphs: 段落列表

        Returns:
            可视化场景列表，格式：[{"type": "flowchart", "title": "xxx", "content": "..."}, ...]
        """
        scenarios = []

        for para in paragraphs:
            if para['type'] == 'image':
                # 教材有图片，需要重绘
                scenarios.append({
                    "type": "image_redraw",
                    "title": "教材图片重绘",
                    "content": para['content'],
                    "subtitle": para.get('subtitle')
                })

            elif para['type'] == 'paragraph':
                content = para['content']

                # 检测流程/步骤
                if self._contains_keywords(content, self.visualization_scenarios["流程步骤"]):
                    scenarios.append({
                        "type": "flowchart",
                        "title": para.get('subtitle', '流程图'),
                        "content": content
                    })

                # 检测层次结构
                elif self._contains_keywords(content, self.visualization_scenarios["层次结构"]):
                    scenarios.append({
                        "type": "hierarchy",
                        "title": para.get('subtitle', '层次结构'),
                        "content": content
                    })

                # 检测状态转换
                elif self._contains_keywords(content, self.visualization_scenarios["状态转换"]):
                    scenarios.append({
                        "type": "state",
                        "title": para.get('subtitle', '状态转换'),
                        "content": content
                    })

                # 检测组件关系
                elif self._contains_keywords(content, self.visualization_scenarios["组件关系"]):
                    scenarios.append({
                        "type": "component",
                        "title": para.get('subtitle', '组件关系'),
                        "content": content
                    })

        return scenarios

    def _contains_keywords(self, content: str, keywords: List[str]) -> bool:
        """检查内容是否包含关键词"""
        return any(keyword in content for keyword in keywords)

    def generate_html(self, section_number: str, section_title: str, mermaid_charts: List[Dict]) -> str:
        """
        生成可视化HTML文件

        Args:
            section_number: 章节号
            section_title: 章节标题
            mermaid_charts: Mermaid图表列表，格式：[{"title": "xxx", "code": "...", "description": "..."}, ...]

        Returns:
            HTML内容
        """
        charts_html = ""
        for chart in mermaid_charts:
            charts_html += f"""
    <h2>{chart['title']}</h2>
    <div class="mermaid">
{chart['code']}
    </div>
    <p class="description">{chart['description']}</p>
"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{section_number} {section_title} - 可视化</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body {{
            font-family: "Microsoft YaHei", Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 40px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }}
        .mermaid {{
            background-color: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .description {{
            color: #666;
            line-height: 1.6;
            margin: 10px 0 30px 0;
            padding: 10px;
            background-color: #fff;
            border-left: 4px solid #4CAF50;
        }}
    </style>
</head>
<body>
    <h1>{section_number} {section_title} - 可视化</h1>
{charts_html}
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            flowchart: {{
                useMaxWidth: true,
                htmlLabels: true
            }}
        }});
    </script>
</body>
</html>"""
        return html


def main():
    """测试函数"""
    # 测试用例
    test_content = """
    计算机系统是一个层次结构系统，每一层都通过向上层用户提供一个抽象的简洁接口。
    指令执行过程包括取指、译码、执行、访存、写回五个阶段。
    进程有新建、就绪、运行、阻塞、终止五种状态。
    """

    generator = VisualizationGenerator()
    needs_viz = generator.needs_visualization(test_content)
    print(f"需要可视化: {needs_viz}")

    # 测试HTML生成
    test_charts = [
        {
            "title": "计算机系统层次结构",
            "code": """graph TD
    A[应用问题] --> B[算法]
    B --> C[高级语言程序]
    C --> D[汇编语言程序]
    D --> E[机器语言程序]
    E --> F[硬件执行]""",
            "description": "此图展示了从应用问题到硬件执行的完整转换过程，体现了计算机系统的层次化设计思想。"
        }
    ]

    html = generator.generate_html("1.3", "计算机系统层次结构", test_charts)
    print("\n生成的HTML预览:")
    print(html[:500] + "...")


if __name__ == "__main__":
    main()

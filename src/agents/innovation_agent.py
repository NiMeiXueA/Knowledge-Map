from __future__ import annotations

from src.llm.provider import UnifiedLLMProvider


async def analyze_innovation(title: str, abstract: str, raw_text: str) -> dict:
    provider = UnifiedLLMProvider()
    return await provider.complete_json(
        "你是论文精读助手。必须中文输出，必须返回 JSON，不要输出 Markdown。",
        f"""
请基于论文原文提炼：
- summary
- idea
- innovation
- innovation_points: [{{point,evidence,confidence}}]
- flow_steps
- applications

要求：
- 不编造，尽量给出证据，表达适合技术路线图展示。
- `idea` 只能写论文的核心方法机制，限定 1-2 句。
- `idea` 不得写“实验表明、优于其他方法、更快收敛、性能更好”等结果性表述。
- 若论文是分析型/实验型工作，`idea` 写“研究核心问题 + 方法或分析路径”，不要伪装成算法贡献。

标题：{title}
摘要：{abstract}
正文片段：{raw_text[:]}
""".strip(),
        trace_label="innovation_agent",
        max_retries=1,
    )

from __future__ import annotations

from src.llm.provider import UnifiedLLMProvider


async def analyze_limitations(title: str, abstract: str, raw_text: str) -> dict:
    provider = UnifiedLLMProvider()
    return await provider.complete_json(
        "你是学术审稿风格的论文局限分析助手。必须中文输出 JSON。",
        f"""
请返回：
- limitations
- limitation_points: [{{point,evidence,type,severity}}]

其中 type 只能是 paper_claimed 或 inferred。
要求克制，不要过度推断。

标题：{title}
摘要：{abstract}
正文片段：{raw_text[:12000]}
""".strip(),
        trace_label="limitation_agent",
        max_retries=1,
    )

from __future__ import annotations

from src.config import CATEGORY_DEFINITIONS
from src.llm.provider import UnifiedLLMProvider


async def classify_paper(title: str, abstract: str, raw_text: str) -> dict:
    provider = UnifiedLLMProvider()
    category_list = [
        {"id": item.id, "name": item.name, "folder": item.folder}
        for item in CATEGORY_DEFINITIONS
    ]
    result = await provider.complete_json(
        "你是联邦学习论文分类助手。只能返回 JSON，不要解释。",
        f"""
可选大类：{category_list}

请根据标题、摘要和正文片段进行分类；不确定时必须输出 other。
输出字段：category_id, category_name, confidence, reason

标题：
{title}

摘要：
{abstract}

正文片段：
{raw_text[:5000]}
""".strip(),
    )
    return result


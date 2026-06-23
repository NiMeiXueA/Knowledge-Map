from __future__ import annotations

from src.llm.provider import UnifiedLLMProvider
from src.schemas import CategoryModel


async def classify_paper(
    title: str,
    abstract: str,
    raw_text: str,
    categories: list[CategoryModel],
) -> dict:
    """
    根据标题、摘要、正文片段把论文归入给定分类集合中的某一个。

    categories 必须由调用方从 papers.json 读取后传入，避免使用硬编码的
    CATEGORY_DEFINITIONS——否则会与用户在前端 CRUD 后的实际分类集合脱节，
    产生"论文被分到 papers.json 中不存在的分类"的孤儿数据。
    """
    provider = UnifiedLLMProvider()
    category_list = [
        {
            "id": item.id,
            "name": item.name,
            "folder": item.folder,
            "why": item.why,
            "advantages": item.advantages,
            "disadvantages": item.disadvantages,
        }
        for item in categories
    ]
    result = await provider.complete_json(
        "你是论文分类助手，只能返回 JSON，不要解释。"
        "请严格按照给定的可选大类做归类，不允许输出列表之外的 id。"
        "不确定时必须输出列表中 id 为 'other' 的分类（如果存在）。",
        f"""
可选大类：{category_list}

请根据标题、摘要和正文片段进行分类。
注意：必须从上方列表里选一个 id，不能自行编造或使用列表外的 id。
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

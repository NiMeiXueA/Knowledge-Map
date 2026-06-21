from __future__ import annotations

from src.llm.provider import UnifiedLLMProvider


async def reflect_analysis(state: dict) -> dict:
    provider = UnifiedLLMProvider()
    return await provider.complete_json(
        "你是论文分析质检助手。只返回 JSON。",
        f"""
请检查以下分析是否与原文一致，有无无证据编造，分类是否合理，来源是否可信。
输出：
- passed
- issues: [{{target,problem,suggestion}}]
- repair_targets

如果只是轻微问题，可 passed=true。

原文片段：
{state.get("raw_text", "")[:14000]}

分析结果：
{{
  "title": {state.get("title")},
  "abstract": {state.get("abstract")},
  "category_id": {state.get("category_id")},
  "innovation": {state.get("innovation")},
  "innovation_points": {state.get("innovation_points")},
  "limitations": {state.get("limitations")},
  "limitation_points": {state.get("limitation_points")},
  "source": {state.get("source")},
  "venue": {state.get("venue")},
  "year": {state.get("year")},
  "doi": {state.get("doi")}
}}
""".strip(),
        trace_label="reflection_agent",
        max_retries=1,
    )

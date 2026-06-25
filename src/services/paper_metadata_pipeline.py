from __future__ import annotations

import json
import re
from typing import Any

from src.config import get_env
from src.llm.provider import UnifiedLLMProvider
from src.services.external_paper_lookup import (
    fallback_source_result,
    lookup_paper_candidates,
    merge_citations,
    parse_reference_hint,
)
from src.services.metadata_extractor import extract_metadata, extract_references_text


async def build_verified_metadata(raw_text: str, reference_hint: str | None = None) -> dict[str, Any]:
    local_metadata = extract_metadata(raw_text)
    remote_candidates = await lookup_paper_candidates(local_metadata, raw_text, reference_hint)
    fallback = fallback_source_result(local_metadata, raw_text, reference_hint)
    return await _finalize_metadata(local_metadata, raw_text, remote_candidates, fallback, allow_llm=True)


async def build_verified_metadata_from_reference(reference: str) -> dict[str, Any]:
    hint = parse_reference_hint(reference)
    local_metadata: dict[str, Any] = {
        "title": hint.title,
        "authors": [],
        "abstract": "",
        "citations": [],
        "doi": hint.doi,
        "arxiv_id": hint.arxiv_id,
        "metadata_confidence": 0.25,
        "metadata_source_method": "reference_lookup",
        "metadata_verification_notes": "来自 DOI / arXiv / 论文链接或标题输入。",
        "source_candidates": [
            {
                "provider": "reference_lookup",
                "title": hint.title,
                "authors": [],
                "abstract": "",
                "year": None,
                "venue": None,
                "doi": hint.doi,
                "arxiv_id": hint.arxiv_id,
                "source_url": hint.source_url,
                "citation_text": None,
                "bibtex": None,
                "confidence": 0.25,
                "reason": "来自 DOI / arXiv / 论文链接或标题输入。",
            }
        ],
    }
    remote_candidates = await lookup_paper_candidates(local_metadata, reference, reference)
    fallback = fallback_source_result(local_metadata, reference, reference)
    return await _finalize_metadata(local_metadata, reference, remote_candidates, fallback, allow_llm=False)


async def _finalize_metadata(
    local_metadata: dict[str, Any],
    raw_text: str,
    remote_candidates: list[dict[str, Any]],
    fallback: dict[str, Any],
    allow_llm: bool,
) -> dict[str, Any]:

    if remote_candidates:
        try:
            if allow_llm:
                reconciled = await _reconcile_with_llm(local_metadata, remote_candidates, raw_text, fallback)
            else:
                reconciled = _fallback_reconcile(local_metadata, remote_candidates, fallback)
        except Exception:
            reconciled = _fallback_reconcile(local_metadata, remote_candidates, fallback)
    else:
        reconciled = fallback

    reconciled["source_candidates"] = [local_metadata["source_candidates"][0], *remote_candidates]
    remote_citations = _pick_remote_citations(reconciled, remote_candidates)
    local_citations = local_metadata.get("citations", [])
    # 在 PDF 模式下用 LLM 从 References 原文再提取一版结构化引用，
    # 与本地正则 + 联网候选合并去重，作为关系图引用边的最可靠来源
    if allow_llm:
        llm_citations = await _extract_citations_with_llm(raw_text)
    else:
        llm_citations = []
    reconciled["citations"] = merge_citations(local_citations, merge_citations(llm_citations, remote_citations))
    return reconciled


async def _extract_citations_with_llm(raw_text: str) -> list[dict[str, Any]]:
    """用 LLM 从 PDF 的 References 段落提取结构化引用列表。

    本地正则对各种引用格式（IEEE / ACM / Nature / 中文 GB/T 7714）容易切错标题或作者，
    而关系图完全依赖引用标题匹配，因此这里花一次 LLM 调用换取更准确的引用标题。
    References 段落缺失或 LLM 失败时返回空列表（调用方会继续用本地+联网结果兜底）。
    """
    references_text = extract_references_text(raw_text)
    if not references_text:
        return []
    # 控制 LLM 输入体积；正则路径不受影响（它在 _extract_citations 里处理完整文本）
    references_text = references_text[:12000]
    llm = UnifiedLLMProvider()
    max_items = int(get_env("PAPER_LLM_CITATION_MAX", 40) or 40)
    payload = {
        "task": "从论文的参考文献原文中提取结构化引用列表，每条引用必须有 title（论文/书籍标题）。",
        "rules": [
            "只提取参考文献条目，不要把正文句子当作引用。",
            "title 用条目中被引用的论文/书籍标题，去掉期刊名、会议名、页码、DOI。",
            "找不到明确标题的条目直接跳过，不要编造。",
            "authors 取作者全名列表，找不到则为空数组。",
            "year 取发表年份（整数），找不到则为 null。",
            f"最多返回 {max_items} 条，按原文顺序排列。",
        ],
        "output_schema": {
            "citations": [
                {
                    "title": "string（必填）",
                    "authors": ["string"],
                    "year": "int|null",
                }
            ]
        },
        "references_text": references_text,
    }
    try:
        result = await llm.complete_json(
            system_prompt=(
                "你是一名严谨的参考文献解析助手。"
                "只返回 JSON 对象，不要解释。"
                "从杂乱的参考文献原文里准确切出每条引用的论文标题、作者和年份。"
            ),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            trace_label="source_agent.citation_extract",
            max_retries=1,
        )
    except Exception:
        return []

    items = result.get("citations") if isinstance(result, dict) else None
    if not isinstance(items, list):
        return []
    normalized = [
        {
            "title": str(item.get("title") or "").strip(),
            "authors": [str(a).strip() for a in item.get("authors", []) if str(a).strip()],
            "year": item.get("year") if isinstance(item.get("year"), int) else None,
        }
        for item in items
        if isinstance(item, dict) and str(item.get("title") or "").strip()
    ]
    return normalized[:max_items]


async def _reconcile_with_llm(
    local_metadata: dict[str, Any],
    remote_candidates: list[dict[str, Any]],
    raw_text: str,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    llm = UnifiedLLMProvider()
    excerpt_chars = int(get_env("PAPER_METADATA_TEXT_EXCERPT_CHARS", 8000) or 8000)
    user_payload = {
        "task": "请比对 PDF 本地提取结果和联网检索结果，输出可信的标准化论文元数据。",
        "local_metadata": {
            "title": local_metadata.get("title"),
            "authors": local_metadata.get("authors"),
            "abstract": local_metadata.get("abstract"),
            "doi": local_metadata.get("doi"),
            "arxiv_id": local_metadata.get("arxiv_id"),
        },
        "remote_candidates": remote_candidates,
        "pdf_excerpt": raw_text[:excerpt_chars],
        "fallback": fallback,
        "output_schema": {
            "title": "string",
            "authors": ["string"],
            "abstract": "string",
            "year": "int|null",
            "venue": "string|null",
            "source": "string",
            "doi": "string|null",
            "arxiv_id": "string|null",
            "source_url": "string|null",
            "citation_text": "string|null",
            "bibtex": "string|null",
            "confidence": "float 0-1",
            "reason": "string",
        },
    }
    result = await llm.complete_json(
        system_prompt=(
            "你是一名严谨的论文元数据校验助手。"
            "你的任务是根据 PDF 提取内容和联网检索候选，选出最可信的论文标题、摘要、年份、来源和引用信息。"
            "如果候选与 PDF 明显不一致，优先使用 fallback。"
            "只返回 JSON 对象。"
        ),
        user_prompt=json.dumps(user_payload, ensure_ascii=False),
        trace_label="source_agent.metadata_reconcile",
        max_retries=1,
    )
    return _normalize_reconciled_output(result, fallback)


def _fallback_reconcile(
    local_metadata: dict[str, Any],
    remote_candidates: list[dict[str, Any]],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    if not remote_candidates:
        return fallback
    best = max(remote_candidates, key=lambda item: float(item.get("confidence") or 0.0))
    local_title = str(local_metadata.get("title") or "").lower()
    remote_title = str(best.get("title") or "").lower()
    title_overlap = 1.0 if local_title and local_title == remote_title else 0.0
    identifier_match = _same_identifier(local_metadata, best)
    if best.get("confidence", 0.0) < 0.45 and not title_overlap and not identifier_match:
        return fallback
    return {
        "title": best.get("title") or fallback["title"],
        "authors": best.get("authors") or fallback["authors"],
        "abstract": best.get("abstract") or fallback["abstract"],
        "year": best.get("year") or fallback["year"],
        "venue": best.get("venue") or fallback["venue"],
        "source": best.get("provider") or fallback["source"],
        "doi": best.get("doi") or fallback["doi"],
        "arxiv_id": best.get("arxiv_id") or fallback["arxiv_id"],
        "source_url": best.get("source_url") or fallback["source_url"],
        "citation_text": best.get("citation_text") or fallback["citation_text"],
        "bibtex": best.get("bibtex") or fallback["bibtex"],
        "confidence": max(float(best.get("confidence") or 0.0), float(fallback.get("confidence") or 0.0)),
        "reason": f"基于最高分候选自动对齐：{best.get('reason') or '标题最匹配'}",
    }


def _normalize_reconciled_output(result: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(result.get("title") or fallback["title"]).strip(),
        "authors": [str(item).strip() for item in result.get("authors", fallback["authors"]) if str(item).strip()],
        "abstract": str(result.get("abstract") or fallback["abstract"]).strip(),
        "year": result.get("year") if isinstance(result.get("year"), int) else fallback["year"],
        "venue": str(result.get("venue") or fallback["venue"] or "").strip() or None,
        "source": str(result.get("source") or fallback["source"]).strip(),
        "doi": str(result.get("doi") or fallback["doi"] or "").strip() or None,
        "arxiv_id": str(result.get("arxiv_id") or fallback["arxiv_id"] or "").strip() or None,
        "source_url": str(result.get("source_url") or fallback["source_url"] or "").strip() or None,
        "citation_text": str(result.get("citation_text") or fallback["citation_text"] or "").strip() or None,
        "bibtex": str(result.get("bibtex") or fallback["bibtex"] or "").strip() or None,
        "confidence": _normalize_confidence(result.get("confidence"), fallback["confidence"]),
        "reason": str(result.get("reason") or fallback["reason"]).strip(),
    }


def _pick_remote_citations(reconciled: dict[str, Any], remote_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for candidate in remote_candidates:
        candidate_doi = str(candidate.get("doi") or "").strip().lower()
        final_doi = str(reconciled.get("doi") or "").strip().lower()
        candidate_title = str(candidate.get("title") or "").strip().lower()
        final_title = str(reconciled.get("title") or "").strip().lower()
        if final_doi and candidate_doi and final_doi == candidate_doi:
            return candidate.get("citations") or []
        if final_title and candidate_title and final_title == candidate_title:
            return candidate.get("citations") or []
    best = max(remote_candidates, key=lambda item: float(item.get("confidence") or 0.0), default=None)
    return (best or {}).get("citations") or []


def _same_identifier(local_metadata: dict[str, Any], candidate: dict[str, Any]) -> bool:
    local_doi = str(local_metadata.get("doi") or "").strip().lower()
    candidate_doi = str(candidate.get("doi") or "").strip().lower()
    if local_doi and candidate_doi and local_doi == candidate_doi:
        return True

    local_arxiv = _strip_arxiv_version(str(local_metadata.get("arxiv_id") or ""))
    candidate_arxiv = _strip_arxiv_version(str(candidate.get("arxiv_id") or ""))
    return bool(local_arxiv and candidate_arxiv and local_arxiv == candidate_arxiv)


def _strip_arxiv_version(value: str) -> str:
    return re.sub(r"v\d+$", "", value.strip().replace("-", ".").lower())


def _normalize_confidence(value: object, fallback: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return max(0.0, min(1.0, float(fallback)))

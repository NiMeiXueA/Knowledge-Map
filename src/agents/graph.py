from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from collections.abc import Iterable

from langgraph.graph import END, StateGraph

from src.agents.classify_agent import classify_paper
from src.agents.innovation_agent import analyze_innovation
from src.agents.limitation_agent import analyze_limitations
from src.agents.reflection_agent import reflect_analysis
from src.agents.source_agent import analyze_source
from src.database.json_store import load_collection, save_analysis_json, upsert_paper
from src.database.kv import KVRepository
from src.llm.provider import LLMJSONParseError
from src.schemas import PaperModel
from src.services.metadata_extractor import extract_metadata
from src.services.paper_record_cleaner import build_paper_short, normalize_idea_text, normalize_short
from src.services.paper_file_manager import ensure_unique_paper_id, move_pdf_to_category, slugify_paper_id
from src.services.paper_graph_builder import sync_relationships_into_papers
from src.services.pdf_loader import extract_pdf_text


class PaperAnalysisState(TypedDict, total=False):
    """
    论文分析状态类型定义
    
    这是LangGraph工作流的状态结构，包含论文分析的所有中间和最终数据
    """
    # 任务信息
    task_id: str  # 任务ID
    paper_id: str  # 论文ID
    pdf_path: str  # PDF文件路径
    input_mode: str  # 输入模式：pdf / reference
    input_reference: str  # DOI / arXiv / URL / 标题
    
    # PDF解析结果
    raw_text: str  # PDF原始文本
    title: str  # 论文标题
    authors: list[str]  # 作者列表
    abstract: str  # 摘要
    citations: list[dict]  # 引用列表
    
    # 分类信息
    category_id: str  # 分类ID
    category_name: str  # 分类名称
    target_folder: str  # 目标文件夹
    short: str  # 论文缩写/简称（由分类 Agent 一并产出）
    
    # 分析结果
    summary: str  # 论文总结
    idea: str  # 核心思想
    innovation: str  # 创新点描述
    innovation_points: list[dict]  # 创新点列表
    limitations: str  # 局限性描述
    limitation_points: list[dict]  # 局限性点列表
    applications: str  # 应用场景
    flow_steps: list[str]  # 方法流程步骤
    
    # 元数据信息
    year: int | None  # 发表年份
    venue: str | None  # 发表会议/期刊
    source: str | None  # 来源
    doi: str | None  # DOI
    arxiv_id: str | None  # arXiv ID
    source_url: str | None  # 来源URL
    citation_text: str | None  # 引用文本
    bibtex: str | None  # BibTeX格式
    
    # 元数据验证信息
    metadata_confidence: float  # 元数据置信度
    metadata_source_method: str | None  # 元数据来源方法
    metadata_verification_notes: str | None  # 元数据验证说明
    source_candidates: list[dict]  # 来源候选列表
    
    # 反思和修复信息
    reflection_passed: bool  # 反思是否通过
    reflection_feedback: dict  # 反思反馈
    retry_count: int  # 重试次数
    needs_human_review: bool  # 是否需要人工审核
    
    # 最终输出
    final_json_path: str  # 最终JSON文件路径
    current_warning: str | None  # 当前警告信息
    used_ocr: bool  # 是否使用了OCR


# Redis键值存储实例
kv = KVRepository()


def _stringify(value: object, default: str = "") -> str:
    """将值转换为字符串，支持None和可迭代对象"""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Iterable) and not isinstance(value, (dict, bytes, bytearray)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "；".join(parts)
    return str(value).strip()


def _to_string_list(value: object) -> list[str]:
    """将值转换为字符串列表"""
    if value is None:
        return []
    if isinstance(value, list):
        return [_stringify(item) for item in value if _stringify(item)]
    text = _stringify(value)
    if not text:
        return []
    return [item.strip() for item in text.replace("\n", "；").split("；") if item.strip()]


def _normalize_confidence(value: object) -> float:
    """将置信度值归一化为0-1之间的浮点数"""
    if isinstance(value, (int, float)):
        return float(value)
    text = _stringify(value).lower()
    mapping = {
        "high": 0.9,
        "medium": 0.6,
        "low": 0.3,
        "高": 0.9,
        "较高": 0.8,
        "中": 0.6,
        "中等": 0.6,
        "低": 0.3,
        "较低": 0.2,
    }
    if text in mapping:
        return mapping[text]
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_severity(value: object) -> str:
    """将严重程度值标准化为low/medium/high"""
    text = _stringify(value).lower()
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "高": "high",
        "严重": "high",
        "较高": "high",
        "中": "medium",
        "中等": "medium",
        "一般": "medium",
        "低": "low",
        "轻微": "low",
        "较低": "low",
    }
    return mapping.get(text, "medium")


def _normalize_limitation_type(value: object) -> str:
    """将局限性类型标准化为paper_claimed或inferred"""
    text = _stringify(value).lower()
    mapping = {
        "paper_claimed": "paper_claimed",
        "claimed": "paper_claimed",
        "论文自述": "paper_claimed",
        "作者承认": "paper_claimed",
        "inferred": "inferred",
        "推断": "inferred",
        "推测": "inferred",
    }
    return mapping.get(text, "inferred")


def _normalize_innovation_points(value: object) -> list[dict]:
    """将创新点列表标准化为统一格式"""
    if not isinstance(value, list):
        return []
    normalized: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append(
                {
                    "point": _stringify(item.get("point")),
                    "evidence": _stringify(item.get("evidence")),
                    "confidence": _normalize_confidence(item.get("confidence")),
                }
            )
        else:
            point = _stringify(item)
            if point:
                normalized.append({"point": point, "evidence": "", "confidence": 0.0})
    return [item for item in normalized if item["point"]]


def _normalize_limitation_points(value: object) -> list[dict]:
    """将局限性点列表标准化为统一格式"""
    if not isinstance(value, list):
        return []
    normalized: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append(
                {
                    "point": _stringify(item.get("point")),
                    "evidence": _stringify(item.get("evidence")),
                    "type": _normalize_limitation_type(item.get("type")),
                    "severity": _normalize_severity(item.get("severity")),
                }
            )
        else:
            point = _stringify(item)
            if point:
                normalized.append(
                    {"point": point, "evidence": "", "type": "inferred", "severity": "medium"}
                )
    return [item for item in normalized if item["point"]]


def _normalize_venue_for_display(venue: object, year: object) -> str | None:
    """venue 展示规范化：若 venue 不含年份且 year 已知，补上年份（如 AISTATS → AISTATS 2017）。

    解决会议/期刊名只返回简称（Semantic Scholar 常返回 "AISTATS"、"NeurIPS" 这类裸简称）
    时展示信息不全的问题；已含 19xx/20xx 年份的 venue 保持原样。
    """
    if not venue:
        return None
    venue_text = str(venue).strip()
    if not venue_text:
        return None
    if re.search(r"(?:19|20)\d{2}", venue_text):
        return venue_text
    if isinstance(year, int) and 1900 <= year <= 2100:
        return f"{venue_text} {year}"
    return venue_text


def _normalize_state_for_save(state: PaperAnalysisState) -> PaperAnalysisState:
    """在保存前标准化状态中的所有字段"""
    state["venue"] = _normalize_venue_for_display(state.get("venue"), state.get("year"))
    state["summary"] = _stringify(state.get("summary"))
    state["idea"] = normalize_idea_text(_stringify(state.get("idea")))
    state["innovation"] = _stringify(state.get("innovation"))
    state["applications"] = _stringify(state.get("applications"))
    state["limitations"] = _stringify(state.get("limitations"))
    state["flow_steps"] = _to_string_list(state.get("flow_steps"))
    state["innovation_points"] = _normalize_innovation_points(state.get("innovation_points"))
    state["limitation_points"] = _normalize_limitation_points(state.get("limitation_points"))
    return state


def _task_update(state: PaperAnalysisState, stage: str, message: str, error: str | None = None) -> None:
    """更新任务状态到Redis"""
    kv.set_task(
        state["task_id"],
        status="failed" if error else "processing",
        stage=stage,
        message=message,
        paper_id=state.get("paper_id"),
        error=error,
    )


async def parse_pdf_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """
    PDF解析节点：提取PDF文本内容
    
    这是工作流的第一个节点，负责：
    1. 调用PDF解析器提取文本
    2. 检查是否成功提取到文本
    3. 记录警告信息（如使用了OCR）
    """
    _task_update(state, "pdf_parsing", "正在解析 PDF 文本")
    parsed = extract_pdf_text(Path(state["pdf_path"]))
    if not parsed["raw_text"]:
        raise ValueError("PDF 无法提取文本，请检查文件是否损坏或为纯扫描件。")
    state.update(parsed)
    if parsed.get("warning"):
        state["current_warning"] = parsed["warning"]
    return state


async def extract_metadata_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """
    元数据提取节点：从PDF文本中提取标题、作者、摘要等
    
    这是论文标题获取的第一步：本地PDF解析
    """
    _task_update(state, "metadata", "正在提取论文元信息")
    state.update(extract_metadata(state["raw_text"]))
    return state


async def source_agent_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """
    来源代理节点：联网检索并校验论文元数据
    
    这是论文标题获取的第二步和第三步：
    1. 联网检索候选论文（Crossref、Semantic Scholar、arXiv）
    2. 使用LLM对比本地提取结果和联网候选，选择最可信的标题
    """
    _task_update(state, "source", "正在联网检索并校验论文来源")
    try:
        result = await analyze_source(state["raw_text"], reference=state.get("input_reference"))
    except Exception as exc:
        state["current_warning"] = f"论文来源查询失败，已回退到本地结果：{_format_agent_exception(exc)}"
        return state

    # 更新状态：优先使用联网结果，如果失败则回退到本地结果
    state.update(
        title=result.get("title") or state.get("title"),
        authors=result.get("authors") or state.get("authors", []),
        abstract=result.get("abstract") or state.get("abstract", ""),
        year=result.get("year"),
        venue=result.get("venue"),
        source=result.get("source"),
        doi=result.get("doi") or state.get("doi"),
        arxiv_id=result.get("arxiv_id") or state.get("arxiv_id"),
        source_url=result.get("source_url"),
        citation_text=result.get("citation_text"),
        bibtex=result.get("bibtex"),
        citations=result.get("citations") or state.get("citations", []),
        metadata_confidence=float(result.get("confidence") or state.get("metadata_confidence") or 0.0),
        metadata_source_method=result.get("source"),
        metadata_verification_notes=result.get("reason"),
        source_candidates=result.get("source_candidates") or state.get("source_candidates", []),
    )
    return state


async def save_metadata_to_kv_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """将元数据保存到Redis键值存储"""
    kv.set_paper_payload(
        state["paper_id"],
        "meta",
        {
            "title": state["title"],
            "authors": state.get("authors", []),
            "abstract": state.get("abstract", ""),
            "citations": state.get("citations", []),
            "year": state.get("year"),
            "venue": state.get("venue"),
            "doi": state.get("doi"),
            "arxiv_id": state.get("arxiv_id"),
            "source_url": state.get("source_url"),
            "citation_text": state.get("citation_text"),
            "bibtex": state.get("bibtex"),
            "metadata_confidence": state.get("metadata_confidence", 0.0),
            "metadata_source_method": state.get("metadata_source_method"),
            "metadata_verification_notes": state.get("metadata_verification_notes"),
            "source_candidates": state.get("source_candidates", []),
        },
    )
    return state


async def classify_paper_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """论文分类节点：使用LLM将论文分类到当前 papers.json 中的类别"""
    _task_update(state, "classification", "正在分析论文分类")
    # 从 papers.json 读取当前真实分类集合，避免使用硬编码 CATEGORY_MAP 导致孤儿分类
    categories = load_collection().categories
    result = await classify_paper(
        state["title"],
        state.get("abstract", ""),
        state["raw_text"],
        categories,
    )
    category_id = result.get("category_id") or "other"

    # 在动态分类集合里查找；找不到时按 other → 列表第一个 兜底，
    # 都不行就保留 LLM 返回值（move_pdf_to_category_node 会跳过）
    matched = next((item for item in categories if item.id == category_id), None)
    if matched is None:
        matched = next((item for item in categories if item.id == "other"), None)
    if matched is None and categories:
        matched = categories[0]

    state["category_id"] = matched.id if matched else category_id
    state["category_name"] = matched.name if matched else result.get("category_name", "")
    state["target_folder"] = matched.folder if matched else ""
    # 分类 Agent 一并给出论文缩写；未给出时留空，保存节点会回退到启发式 build_paper_short
    state["short"] = str(result.get("short") or "").strip()
    return state


async def move_pdf_to_category_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """将PDF文件移动到对应的分类文件夹"""
    if not state.get("pdf_path") or not state.get("target_folder"):
        return state
    source = Path(state["pdf_path"])
    if not source.exists():
        return state
    moved = move_pdf_to_category(source, state["target_folder"], state["paper_id"])
    state["pdf_path"] = str(moved)
    return state


async def innovation_agent_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """创新点分析节点：使用LLM分析论文的创新点和核心思想"""
    _task_update(state, "innovation", "正在分析论文创新点")
    result = await analyze_innovation(state["title"], state.get("abstract", ""), state["raw_text"])
    state.update(
        summary=result.get("summary", ""),
        idea=result.get("idea", ""),
        innovation=result.get("innovation", ""),
        innovation_points=result.get("innovation_points", []),
        flow_steps=result.get("flow_steps", []),
        applications=result.get("applications", ""),
    )
    return state


async def limitation_agent_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """局限性分析节点：使用LLM分析论文的局限性和不足"""
    _task_update(state, "limitation", "正在分析论文缺陷与局限")
    result = await analyze_limitations(state["title"], state.get("abstract", ""), state["raw_text"])
    state["limitations"] = result.get("limitations", "")
    state["limitation_points"] = result.get("limitation_points", [])
    return state


async def reflection_agent_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """反思节点：使用LLM检查分析结果的质量和一致性"""
    _task_update(state, "reflection", "正在反思并校验分析结果")
    result = await reflect_analysis(state)
    state["reflection_passed"] = bool(result.get("passed"))
    state["reflection_feedback"] = result
    return state


async def repair_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """
    修复节点：根据反思反馈重新运行需要修复的代理
    
    最多重试2次，避免无限循环
    """
    targets = set(state.get("reflection_feedback", {}).get("repair_targets", []))
    state["retry_count"] = state.get("retry_count", 0) + 1
    if "innovation_agent" in targets:
        await innovation_agent_node(state)
    if "limitation_agent" in targets:
        await limitation_agent_node(state)
    if "source_agent" in targets:
        await source_agent_node(state)
    if "classify_agent" in targets:
        await classify_paper_node(state)
    return state


async def save_final_json_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """
    保存最终JSON节点：将分析结果保存到文件
    
    这是论文标题获取的最后一步：
    1. 标准化所有状态字段
    2. 创建PaperModel对象
    3. 保存到src/data/analysis/{paper_id}.json
    4. 更新papers.json集合
    """
    _task_update(state, "saving", "正在保存分析结果")
    state = _normalize_state_for_save(state)
    collection = load_collection()
    existing_ids = {paper.id for paper in collection.papers}
    state["paper_id"] = ensure_unique_paper_id(state["paper_id"], existing_ids - {state["paper_id"]})
    now = datetime.now(timezone.utc)
    
    # 创建PaperModel对象
    # short 优先取分类 Agent 给出的 AI 缩写（更准），清洗失败再回退到启发式规则
    heuristic_short = build_paper_short(
        state.get("title", state["paper_id"]),
        state.get("abstract", ""),
        state.get("raw_text", ""),
    )
    paper = PaperModel(
        id=state["paper_id"],
        short=normalize_short(state.get("short"), fallback=heuristic_short),
        title=state.get("title", state["paper_id"]),  # 论文标题
        year=state.get("year"),
        authors=state.get("authors", []),
        first_author=(state.get("authors") or [""])[0],
        venue=state.get("venue"),
        abstract=state.get("abstract", ""),
        summary=state.get("summary", ""),
        idea=state.get("idea", ""),
        categories=[state.get("category_id", "other")],
        source_path=state.get("pdf_path") or state.get("source_url") or state.get("input_reference", ""),
        innovation=state.get("innovation", ""),
        innovation_points=state.get("innovation_points", []),
        flow_steps=state.get("flow_steps", []),
        applications=state.get("applications", ""),
        limitations=state.get("limitations", ""),
        limitation_points=state.get("limitation_points", []),
        citations=state.get("citations", []),
        relationships=[],
        analysis_json_path="",
        needs_human_review=state.get("needs_human_review", False),
        created_at=now,
        updated_at=now,
        venue_source=state.get("source"),
        doi=state.get("doi"),
        arxiv_id=state.get("arxiv_id"),
        source_url=state.get("source_url"),
        citation_text=state.get("citation_text"),
        bibtex=state.get("bibtex"),
        metadata_confidence=float(state.get("metadata_confidence") or 0.0),
        metadata_source_method=state.get("metadata_source_method"),
        metadata_verification_notes=state.get("metadata_verification_notes"),
        source_candidates=state.get("source_candidates", []),
    )
    
    # 保存到分析结果目录（save_analysis_json 内部会把绝对路径回写到 paper.analysis_json_path）
    analysis_path = save_analysis_json(paper)
    upsert_paper(paper)
    state["final_json_path"] = str(analysis_path)
    kv.set_paper_payload(state["paper_id"], "analysis", paper.model_dump(mode="json"))
    return state


async def build_relationship_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """构建论文关系图：同步引用关系到论文记录"""
    sync_relationships_into_papers()
    return state


async def finish_node(state: PaperAnalysisState) -> PaperAnalysisState:
    """完成节点：标记任务完成"""
    kv.set_task(
        state["task_id"],
        status="completed",
        stage="completed",
        message=state.get("current_warning") or "论文分析完成",
        paper_id=state["paper_id"],
    )
    return state


def _route_after_reflection(state: PaperAnalysisState) -> str:
    """反思后的路由决策：决定是修复还是保存"""
    if state.get("reflection_passed"):
        return "save_final_json"
    if state.get("retry_count", 0) < 2:
        return "repair"
    state["needs_human_review"] = True
    return "save_final_json"


def build_analysis_graph():
    """
    构建论文分析工作流图
    
    工作流节点顺序：
    1. parse_pdf - 解析PDF文本
    2. extract_metadata - 提取元数据（标题、作者、摘要等）
    3. source_agent - 联网检索并校验论文来源
    4. save_metadata_to_kv - 保存元数据到Redis
    5. classify_paper - 论文分类
    6. move_pdf_to_category - 移动PDF到分类文件夹
    7. innovation_agent - 创新点分析
    8. limitation_agent - 局限性分析
    9. reflection_agent - 反思校验
    10. repair - 修复（如果反思未通过）
    11. save_final_json - 保存最终JSON
    12. build_relationship - 构建关系图
    13. finish - 完成
    """
    workflow = StateGraph(PaperAnalysisState)
    workflow.add_node("parse_pdf", parse_pdf_node)
    workflow.add_node("extract_metadata", extract_metadata_node)
    workflow.add_node("source_agent", source_agent_node)
    workflow.add_node("save_metadata_to_kv", save_metadata_to_kv_node)
    workflow.add_node("classify_paper", classify_paper_node)
    workflow.add_node("move_pdf_to_category", move_pdf_to_category_node)
    workflow.add_node("innovation_agent", innovation_agent_node)
    workflow.add_node("limitation_agent", limitation_agent_node)
    workflow.add_node("reflection_agent", reflection_agent_node)
    workflow.add_node("repair", repair_node)
    workflow.add_node("save_final_json", save_final_json_node)
    workflow.add_node("build_relationship", build_relationship_node)
    workflow.add_node("finish", finish_node)

    # 定义工作流边
    workflow.set_entry_point("parse_pdf")
    workflow.add_edge("parse_pdf", "extract_metadata")
    workflow.add_edge("extract_metadata", "source_agent")
    workflow.add_edge("source_agent", "save_metadata_to_kv")
    workflow.add_edge("save_metadata_to_kv", "classify_paper")
    workflow.add_edge("classify_paper", "move_pdf_to_category")
    workflow.add_edge("move_pdf_to_category", "innovation_agent")
    workflow.add_edge("innovation_agent", "limitation_agent")
    workflow.add_edge("limitation_agent", "reflection_agent")
    
    # 反思后的条件分支：修复或保存
    workflow.add_conditional_edges(
        "reflection_agent",
        _route_after_reflection,
        {
            "repair": "repair",
            "save_final_json": "save_final_json",
        },
    )
    workflow.add_edge("repair", "reflection_agent")
    workflow.add_edge("save_final_json", "build_relationship")
    workflow.add_edge("build_relationship", "finish")
    workflow.add_edge("finish", END)
    return workflow.compile()


async def run_analysis(task_id: str, pdf_path: str, reference: str | None = None) -> dict:
    """
    运行论文分析工作流
    
    Args:
        task_id: 任务ID
        pdf_path: PDF文件路径
        
    Returns:
        最终分析状态
    """
    collection = load_collection()
    candidate_id = slugify_paper_id(Path(pdf_path).stem)
    paper_id = ensure_unique_paper_id(candidate_id, {paper.id for paper in collection.papers})
    initial_state: PaperAnalysisState = {
        "task_id": task_id,
        "paper_id": paper_id,
        "pdf_path": pdf_path,
        "input_mode": "pdf",
        "input_reference": reference or "",
        "retry_count": 0,
        "needs_human_review": False,
    }
    graph = build_analysis_graph()
    return await graph.ainvoke(initial_state)


def _format_agent_exception(exc: Exception) -> str:
    """格式化代理异常信息"""
    if isinstance(exc, LLMJSONParseError):
        return str(exc)
    return str(exc)

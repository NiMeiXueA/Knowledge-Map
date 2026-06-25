from __future__ import annotations

from collections import defaultdict

from src.database.json_store import load_collection, save_collection
from src.schemas import GraphLink, GraphNode, GraphPayload, RelationshipItem


def build_graph_payload() -> GraphPayload:
    """构建论文关系图。

    关系图的边**只能由引用关系**构建：当某篇论文的 citations 命中了库内已有论文标题时，
    连一条「被引论文 → 引用方」的 citation 边。不再按分类/时间人为串联论文——
    没有真实引用关系的论文之间不应当出现边。
    """
    collection = load_collection()
    nodes = [
        GraphNode(
            id=paper.id,
            title=paper.title,
            short=paper.short,
            year=paper.year,
            category_id=paper.categories[0] if paper.categories else "other",
        )
        for paper in collection.papers
    ]

    links: list[GraphLink] = []
    # 标题 → 论文ID 的查找表；同时收录带/不带尾标点的小写标题，提升引用命中率
    title_to_id: dict[str, str] = {}
    for paper in collection.papers:
        for variant in _title_variants(paper.title):
            title_to_id.setdefault(variant, paper.id)

    for paper in collection.papers:
        for citation in paper.citations:
            matched_id = _match_citation(citation.title, title_to_id, paper.id)
            if matched_id:
                links.append(
                    GraphLink(
                        source=matched_id,
                        target=paper.id,
                        type="citation",
                        reason="该论文引用了库内已有论文。",
                    )
                )

    deduped: dict[tuple[str, str, str], GraphLink] = {}
    for link in links:
        deduped[(link.source, link.target, link.type)] = link
    return GraphPayload(nodes=nodes, links=list(deduped.values()))


def _title_variants(title: str) -> list[str]:
    """生成标题的小写归一化变体，用于引用标题匹配（容忍大小写/尾标点/多余空白差异）。"""
    base = (title or "").strip().lower()
    if not base:
        return []
    variants = {base}
    variants.add(base.rstrip("..,;:"))
    variants.add(" ".join(base.split()))
    return list(variants)


def _match_citation(citation_title: str, title_to_id: dict[str, str], self_id: str) -> str | None:
    """把单条引用标题匹配到库内论文 ID，匹配不到或命中自己则返回 None。"""
    for variant in _title_variants(citation_title):
        matched_id = title_to_id.get(variant)
        if matched_id and matched_id != self_id:
            return matched_id
    return None


def sync_relationships_into_papers() -> None:
    collection = load_collection()
    graph = build_graph_payload()
    rel_by_source: dict[str, list[RelationshipItem]] = defaultdict(list)
    for link in graph.links:
        rel_by_source[link.source].append(RelationshipItem(**link.model_dump()))
    for paper in collection.papers:
        paper.relationships = rel_by_source.get(paper.id, [])
    save_collection(collection)


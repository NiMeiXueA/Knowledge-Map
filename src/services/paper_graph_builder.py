from __future__ import annotations

from collections import defaultdict

from src.database.json_store import load_collection, save_collection
from src.schemas import GraphLink, GraphNode, GraphPayload, RelationshipItem


def build_graph_payload() -> GraphPayload:
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
    by_category: dict[str, list] = defaultdict(list)
    title_to_id = {paper.title.lower(): paper.id for paper in collection.papers}

    for paper in collection.papers:
        category_id = paper.categories[0] if paper.categories else "other"
        by_category[category_id].append(paper)

    for category_id, papers in by_category.items():
        ordered = sorted(papers, key=lambda item: ((item.year or 9999), item.short.lower()))
        for index in range(1, len(ordered)):
            links.append(
                GraphLink(
                    source=ordered[index - 1].id,
                    target=ordered[index].id,
                    type="same_category_evolution",
                    reason="同一类别中的时间演进关系。",
                )
            )

    for paper in collection.papers:
        for citation in paper.citations:
            matched_id = title_to_id.get(citation.title.lower())
            if matched_id and matched_id != paper.id:
                links.append(
                    GraphLink(
                        source=matched_id,
                        target=paper.id,
                        type="citation",
                        reason="引用信息与已有论文标题匹配。",
                    )
                )

    deduped: dict[tuple[str, str, str], GraphLink] = {}
    for link in links:
        deduped[(link.source, link.target, link.type)] = link
    return GraphPayload(nodes=nodes, links=list(deduped.values()))


def sync_relationships_into_papers() -> None:
    collection = load_collection()
    graph = build_graph_payload()
    rel_by_source: dict[str, list[RelationshipItem]] = defaultdict(list)
    for link in graph.links:
        rel_by_source[link.source].append(RelationshipItem(**link.model_dump()))
    for paper in collection.papers:
        paper.relationships = rel_by_source.get(paper.id, [])
    save_collection(collection)


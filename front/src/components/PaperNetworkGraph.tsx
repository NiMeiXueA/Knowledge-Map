import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { Category, GraphPayload, Paper } from "../types/paper";

type Props = {
  categories: Category[];
  papers: Paper[];
  graph: GraphPayload;
  filter: string;
  setFilter: (value: string) => void;
  selectedId: string | null;
  setSelectedId: (value: string) => void;
};

type NodeOffset = {
  dx: number;
  dy: number;
};

type DragState = {
  nodeId: string;
  pointerId: number;
  startX: number;
  startY: number;
  originDx: number;
  originDy: number;
  moved: boolean;
};

type PanState = {
  pointerId: number;
  startClientX: number;
  startClientY: number;
  originX: number;
  originY: number;
};

const VIEW_WIDTH = 1120;
const VIEW_HEIGHT = 680;
const categoryColors: Record<string, string> = {
  optimization: "#a43d2f",
  personalization: "#0f766e",
  distillation: "#ca8a04",
  graph: "#2563eb",
  generative: "#7c3aed",
  prompt: "#be185d",
  system: "#0f766e",
  survey: "#475569",
  other: "#8b5e3c"
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function isCoreLink(type: string) {
  return type === "same_category_evolution" || type === "core";
}

function getDirectedLink(link: GraphPayload["links"][number], paperMap: Map<string, Paper>) {
  const sourcePaper = paperMap.get(link.source);
  const targetPaper = paperMap.get(link.target);
  if (!sourcePaper || !targetPaper) return link;
  if ((sourcePaper.year ?? 0) < (targetPaper.year ?? 0)) return link;
  if ((sourcePaper.year ?? 0) > (targetPaper.year ?? 0)) {
    return {
      ...link,
      source: link.target,
      target: link.source
    };
  }
  return link;
}

function getArrowAdjustedPoints(
  source: { x: number; y: number; r: number },
  target: { x: number; y: number; r: number }
) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy) || 1;
  const ux = dx / distance;
  const uy = dy / distance;
  const sourcePadding = source.r + 6;
  const targetPadding = target.r + 16;

  return {
    x1: source.x + ux * sourcePadding,
    y1: source.y + uy * sourcePadding,
    x2: target.x - ux * targetPadding,
    y2: target.y - uy * targetPadding
  };
}

export function PaperNetworkGraph({
  categories,
  papers,
  graph,
  filter,
  setFilter,
  selectedId,
  setSelectedId
}: Props) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [nodeOffsets, setNodeOffsets] = useState<Record<string, NodeOffset>>({});
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const panRef = useRef<PanState | null>(null);
  const suppressClickRef = useRef<string | null>(null);

  const paperMap = useMemo(() => new Map(papers.map((paper) => [paper.id, paper])), [papers]);
  const visibleNodes = useMemo(
    () => graph.nodes.filter((node) => filter === "all" || node.category_id === filter),
    [filter, graph.nodes]
  );
  const visibleIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes]);
  const visibleLinks = useMemo(
    () => graph.links.filter((link) => visibleIds.has(link.source) && visibleIds.has(link.target)),
    [graph.links, visibleIds]
  );
  const directedVisibleLinks = useMemo(
    () => visibleLinks.map((link) => getDirectedLink(link, paperMap)),
    [paperMap, visibleLinks]
  );
  const currentId = selectedId && visibleIds.has(selectedId) ? selectedId : visibleNodes[0]?.id || null;
  const selectedPaper = papers.find((paper) => paper.id === currentId) || null;
  const connectedNodeIds = useMemo(() => {
    if (!currentId) return new Set<string>();
    const ids = new Set<string>();
    directedVisibleLinks.forEach((link) => {
      if (link.source === currentId) ids.add(link.target);
      if (link.target === currentId) ids.add(link.source);
    });
    return ids;
  }, [currentId, directedVisibleLinks]);

  useEffect(() => {
    if (!visibleNodes.length) return;
    if (!selectedId || !visibleIds.has(selectedId)) {
      setSelectedId(visibleNodes[0].id);
    }
  }, [selectedId, setSelectedId, visibleIds, visibleNodes]);

  const paperDegree = useMemo(() => {
    const degree: Record<string, number> = {};
    directedVisibleLinks.forEach((link) => {
      degree[link.source] = (degree[link.source] || 0) + 1;
      degree[link.target] = (degree[link.target] || 0) + 1;
    });
    return degree;
  }, [directedVisibleLinks]);

  const positions = useMemo(() => {
    const years = [...new Set(visibleNodes.map((node) => node.year).filter((year): year is number => typeof year === "number"))].sort((a, b) => a - b);
    const centerX = VIEW_WIDTH / 2;
    const centerY = VIEW_HEIGHT / 2;
    const categoryIds = filter === "all" ? categories.map((category) => category.id) : [filter];
    const centers = new Map<string, { x: number; y: number }>();
    const radiusX = filter === "all" ? 360 : 0;
    const radiusY = filter === "all" ? 235 : 0;

    const primaryCounts = new Map<string, number>();
    visibleNodes.forEach((node) => {
      primaryCounts.set(node.category_id, (primaryCounts.get(node.category_id) || 0) + 1);
    });

    const denseCategories = new Set(
      [...primaryCounts.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([categoryId]) => categoryId)
    );

    categoryIds.forEach((categoryId, index) => {
      if (filter !== "all") {
        centers.set(categoryId, { x: centerX, y: centerY });
        return;
      }

      const angle = (-Math.PI / 2) + (index / Math.max(categoryIds.length, 1)) * Math.PI * 2;
      const categoryWeight = primaryCounts.get(categoryId) || 0;
      const spreadBoost = denseCategories.has(categoryId) ? 1.16 + Math.min(categoryWeight * 0.01, 0.08) : 1;
      centers.set(categoryId, {
        x: centerX + Math.cos(angle) * radiusX * spreadBoost,
        y: centerY + Math.sin(angle) * radiusY * spreadBoost
      });
    });

    const byCategory = new Map<string, typeof visibleNodes>();
    visibleNodes.forEach((node) => {
      const categoryId = filter === "all" ? node.category_id : filter;
      const existing = byCategory.get(categoryId) || [];
      existing.push(node);
      byCategory.set(categoryId, existing);
    });

    const layout = new Map<string, { x: number; y: number; r: number }>();
    byCategory.forEach((categoryNodes, categoryId) => {
      const clusterCenter = centers.get(categoryId) || { x: centerX, y: centerY };
      const sorted = [...categoryNodes].sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.short.localeCompare(b.short));
      const densityBoost = denseCategories.has(categoryId) ? 1.24 : 1;

      sorted.forEach((node, index) => {
        const yearIndex = typeof node.year === "number" ? years.indexOf(node.year) : 0;
        const orbit = (88 + Math.max(yearIndex, 0) * 10) * densityBoost;
        const angle = (index / Math.max(sorted.length, 1)) * Math.PI * 2;
        const wobble = (index % 2 === 0 ? 28 : -24) * densityBoost;
        const offset = nodeOffsets[node.id] || { dx: 0, dy: 0 };

        layout.set(node.id, {
          x: clusterCenter.x + Math.cos(angle) * orbit + Math.sin(angle * 2) * 24 * densityBoost + offset.dx,
          y: clusterCenter.y + Math.sin(angle) * (orbit * 0.7) + wobble + offset.dy,
          r: 15 + Math.min((paperDegree[node.id] || 0) * 1.8, 10)
        });
      });
    });

    return layout;
  }, [categories, filter, nodeOffsets, paperDegree, visibleNodes]);

  const relatedLinks = selectedPaper
    ? directedVisibleLinks.filter((link) => link.source === selectedPaper.id || link.target === selectedPaper.id)
    : [];
  const incomingLinks = selectedPaper ? relatedLinks.filter((link) => link.target === selectedPaper.id) : [];
  const outgoingLinks = selectedPaper ? relatedLinks.filter((link) => link.source === selectedPaper.id) : [];

  const relatedPills = relatedLinks.slice(0, 5).map((link) => {
    const neighborId = link.source === selectedPaper?.id ? link.target : link.source;
    const neighbor = paperMap.get(neighborId);
    return neighbor ? `${neighbor.short} · ${isCoreLink(link.type) ? "主线" : "启发"}` : link.type;
  });

  const getSvgPoint = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };

    const rect = svg.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * VIEW_WIDTH;
    const y = ((clientY - rect.top) / rect.height) * VIEW_HEIGHT;
    return {
      x: (x - (VIEW_WIDTH / 2 - (VIEW_WIDTH / 2) * zoom) - pan.x) / zoom,
      y: (y - (VIEW_HEIGHT / 2 - (VIEW_HEIGHT / 2) * zoom) - pan.y) / zoom
    };
  };

  const handlePointerDown = (nodeId: string, event: React.PointerEvent<SVGGElement>) => {
    event.stopPropagation();
    const point = getSvgPoint(event.clientX, event.clientY);
    const currentOffset = nodeOffsets[nodeId] || { dx: 0, dy: 0 };
    dragRef.current = {
      nodeId,
      pointerId: event.pointerId,
      startX: point.x,
      startY: point.y,
      originDx: currentOffset.dx,
      originDy: currentOffset.dy,
      moved: false
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (drag && drag.pointerId === event.pointerId) {
      const point = getSvgPoint(event.clientX, event.clientY);
      const deltaX = point.x - drag.startX;
      const deltaY = point.y - drag.startY;
      drag.moved = Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2;

      setNodeOffsets((current) => ({
        ...current,
        [drag.nodeId]: {
          dx: drag.originDx + deltaX,
          dy: drag.originDy + deltaY
        }
      }));
      return;
    }

    const activePan = panRef.current;
    if (!activePan || activePan.pointerId !== event.pointerId) return;

    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const dx = ((event.clientX - activePan.startClientX) / rect.width) * VIEW_WIDTH;
    const dy = ((event.clientY - activePan.startClientY) / rect.height) * VIEW_HEIGHT;
    setPan({
      x: activePan.originX + dx,
      y: activePan.originY + dy
    });
  };

  const handlePointerEnd = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (drag && drag.pointerId === event.pointerId) {
      if (svgRef.current?.hasPointerCapture(event.pointerId)) {
        svgRef.current.releasePointerCapture(event.pointerId);
      }

      if (drag.moved) {
        suppressClickRef.current = drag.nodeId;
      } else {
        setSelectedId(drag.nodeId);
      }
      dragRef.current = null;
      return;
    }

    const activePan = panRef.current;
    if (activePan && activePan.pointerId === event.pointerId) {
      if (svgRef.current?.hasPointerCapture(event.pointerId)) {
        svgRef.current.releasePointerCapture(event.pointerId);
      }
      panRef.current = null;
    }
  };

  const handleNodeClick = (nodeId: string) => {
    if (suppressClickRef.current === nodeId) {
      suppressClickRef.current = null;
      return;
    }
    setSelectedId(nodeId);
  };

  const handleCanvasPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.target !== event.currentTarget) return;
    panRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      originX: pan.x,
      originY: pan.y
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  return (
    <section className="detail-card network-page-card">
      <div className="network-head network-head-page">
        <div>
          <p className="eyebrow">Paper Network</p>
          <h1>论文关系网</h1>
          <p className="network-copy">把不同论文之间的继承关系、同方向演进和跨方向启发集中在一页里。你可以拖拽节点调整布局，并按方向查看聚类分布。</p>
        </div>
        <div className="network-side">
          <div className="network-filters">
            <button className={`filter-chip ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")} type="button">
              全部论文
            </button>
            {categories.map((category) => (
              <button
                className={`filter-chip ${filter === category.id ? "active" : ""}`}
                key={category.id}
                onClick={() => setFilter(category.id)}
                type="button"
              >
                {category.name}
              </button>
            ))}
          </div>
          <div className="network-legend">
            <span>
              <i className="legend-line" />
              同类演进（早 → 晚）
            </span>
            <span>
              <i className="legend-line dashed" />
              跨类启发（早 → 晚）
            </span>
            <span>
              <i className="legend-dot" />
              论文节点（可拖拽）
            </span>
          </div>
        </div>
      </div>
      <div className="network-layout">
        <div className="network-canvas-wrap">
          <div className="network-toolbar">
            <button className="network-tool-btn" type="button" onClick={() => setZoom((value) => clamp(Number((value * 1.15).toFixed(2)), 0.7, 2.2))}>
              +
            </button>
            <button className="network-tool-btn" type="button" onClick={() => setZoom((value) => clamp(Number((value / 1.15).toFixed(2)), 0.7, 2.2))}>
              -
            </button>
            <button className="network-tool-btn" type="button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); setNodeOffsets({}); }}>
              重置
            </button>
          </div>
          <svg
            ref={svgRef}
            className={`network-canvas ${dragRef.current || panRef.current ? "is-dragging" : ""}`}
            viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
            role="img"
            aria-label="论文关系网络图"
            onPointerDown={handleCanvasPointerDown}
            onPointerCancel={handlePointerEnd}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerEnd}
          >
            <defs>
              <marker id="arrow-core" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(164, 61, 47, 0.72)" />
              </marker>
              <marker id="arrow-cross" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(15, 118, 110, 0.82)" />
              </marker>
            </defs>
            <g transform={`translate(${VIEW_WIDTH / 2 - (VIEW_WIDTH / 2) * zoom + pan.x} ${VIEW_HEIGHT / 2 - (VIEW_HEIGHT / 2) * zoom + pan.y}) scale(${zoom})`}>
              {directedVisibleLinks.map((link) => {
                const source = positions.get(link.source);
                const target = positions.get(link.target);
                if (!source || !target) return null;

                const lineClass = isCoreLink(link.type) ? "network-link core" : "network-link cross";
                const connected = currentId ? link.source === currentId || link.target === currentId : false;
                const highlightedClass = connected ? "highlighted" : currentId ? "dimmed" : "";
                const adjusted = getArrowAdjustedPoints(source, target);

                return (
                  <line
                    className={`${lineClass} ${highlightedClass}`}
                    key={`${link.source}-${link.target}-${link.type}`}
                    markerEnd={`url(#${isCoreLink(link.type) ? "arrow-core" : "arrow-cross"})`}
                    x1={adjusted.x1}
                    y1={adjusted.y1}
                    x2={adjusted.x2}
                    y2={adjusted.y2}
                  />
                );
              })}
              {visibleNodes.map((node) => {
                const point = positions.get(node.id);
                if (!point) return null;

                const active = currentId === node.id;
                const connected = connectedNodeIds.has(node.id);
                const dimmed = Boolean(currentId && !active && !connected);

                return (
                  <g
                    className={`network-node ${active ? "active" : ""} ${connected ? "connected" : ""} ${dimmed ? "dimmed" : ""}`}
                    key={node.id}
                    onClick={() => handleNodeClick(node.id)}
                    onPointerDown={(event) => handlePointerDown(node.id, event)}
                    role="button"
                    tabIndex={0}
                    aria-label={node.short}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        handleNodeClick(node.id);
                      }
                    }}
                  >
                    <circle cx={point.x} cy={point.y} fill={categoryColors[node.category_id] || categoryColors.other} r={point.r} />
                    <circle cx={point.x} cy={point.y} fill="transparent" r={point.r + 7} stroke="rgba(30, 36, 48, 0.08)" strokeWidth={1} />
                    <text className={`network-label ${dimmed ? "dimmed" : ""}`} x={point.x} y={point.y + point.r + 20}>
                      {node.short}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
        <aside className="network-detail">
          {selectedPaper ? (
            <>
              <div>
                <p className="eyebrow">Selected Paper</p>
                <h3>{selectedPaper.short}</h3>
                <p>{selectedPaper.title}</p>
              </div>
              <div className="detail-meta-grid">
                <div className="meta-box">
                  <strong>年份</strong>
                  <span>{selectedPaper.year ?? "未知"}</span>
                </div>
                <div className="meta-box">
                  <strong>作者</strong>
                  <span>{selectedPaper.first_author || "未知作者"}</span>
                </div>
                <div className="meta-box">
                  <strong>方向</strong>
                  <span>{selectedPaper.categories.map((id) => categories.find((item) => item.id === id)?.name || id).join(" / ")}</span>
                </div>
                <div className="meta-box">
                  <strong>Venue</strong>
                  <span>{selectedPaper.venue || "待补充"}</span>
                </div>
              </div>
              <p>{selectedPaper.idea || selectedPaper.summary || "等待分析结果生成。"}</p>
              <div className="detail-tags">
                {relatedPills.length ? relatedPills.map((label) => <span className="chip" key={label}>{label}</span>) : <span className="chip">当前没有已定义的关联节点</span>}
              </div>
              <p>{relatedLinks[0]?.reason || "点击左侧其它节点可以查看它与当前技术路线中的连接原因。"}</p>
              <div className="detail-flow">
                <div className="detail-flow-block">
                  <strong>受到这些论文启发</strong>
                  <div className="detail-flow-list">
                    {incomingLinks.length ? incomingLinks.map((link) => {
                      const neighbor = paperMap.get(link.source);
                      return (
                        <span className="chip" key={`${link.source}-${link.target}-${link.reason}`}>
                          {neighbor?.short || link.source} · {isCoreLink(link.type) ? "主线输入" : "跨类启发"}
                        </span>
                      );
                    }) : <span className="chip">当前未标注更早来源</span>}
                  </div>
                </div>
                <div className="detail-flow-block">
                  <strong>又启发了这些论文</strong>
                  <div className="detail-flow-list">
                    {outgoingLinks.length ? outgoingLinks.map((link) => {
                      const neighbor = paperMap.get(link.target);
                      return (
                        <span className="chip" key={`${link.source}-${link.target}-${link.reason}`}>
                          {neighbor?.short || link.target} · {isCoreLink(link.type) ? "主线输出" : "跨类外溢"}
                        </span>
                      );
                    }) : <span className="chip">当前未标注后续影响</span>}
                  </div>
                </div>
              </div>
              <Link className="detail-link" to={`/paper/${selectedPaper.id}`}>
                查看论文详情
              </Link>
            </>
          ) : (
            <p className="network-empty">当前筛选下暂无论文节点。</p>
          )}
        </aside>
      </div>
    </section>
  );
}

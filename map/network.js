const networkSvg = document.getElementById('paper-network');
const networkFilters = document.getElementById('network-filters');
const networkDetail = document.getElementById('network-detail');
const zoomInButton = document.getElementById('zoom-in');
const zoomOutButton = document.getElementById('zoom-out');
const zoomResetButton = document.getElementById('zoom-reset');

const SVG_NS = 'http://www.w3.org/2000/svg';
const NETWORK_VIEW = { width: 1120, height: 680 };
const networkState = {
  filter: 'all',
  selectedId: null,
  zoom: 1,
  panX: 0,
  panY: 0,
  isDragging: false,
  dragStartX: 0,
  dragStartY: 0,
  dragOriginX: 0,
  dragOriginY: 0,
  draggedNodeId: null,
  draggedNodeMoved: false,
  suppressClickNodeId: null,
  nodeDragStartX: 0,
  nodeDragStartY: 0,
  nodeDragBaseX: 0,
  nodeDragBaseY: 0,
  nodeDragOriginDx: 0,
  nodeDragOriginDy: 0
};

const CATEGORY_BY_ID = new Map(CATEGORIES.map((category) => [category.id, category]));
const PAPER_BY_ID = new Map(PAPERS.map((paper) => [paper.id, paper]));
const CATEGORY_COLORS = {
  optimization: '#a43d2f',
  personalization: '#0f766e',
  distillation: '#ca8a04',
  graph: '#2563eb',
  generative: '#7c3aed',
  prompt: '#be185d',
  system: '#0f766e',
  survey: '#475569'
};

const uniqueYears = [...new Set(PAPERS.map((paper) => paper.year))].sort((a, b) => a - b);
let networkViewport = null;
const nodeOffsets = new Map();
const renderedGraph = {
  positions: new Map(),
  groups: new Map(),
  labels: new Map(),
  linksByPaper: new Map()
};

const escapeHtml = (text) =>
  String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');

const getCategoryName = (id) => CATEGORY_BY_ID.get(id)?.name || id;
const getPrimaryCategory = (paper) => paper.categories[0];
const getNodeOffset = (paperId) => nodeOffsets.get(paperId) || { dx: 0, dy: 0 };
const getDirectedLink = (link) => {
  const sourcePaper = PAPER_BY_ID.get(link.source);
  const targetPaper = PAPER_BY_ID.get(link.target);
  if (!sourcePaper || !targetPaper) return link;
  if (sourcePaper.year < targetPaper.year) return link;
  if (sourcePaper.year > targetPaper.year) {
    return {
      ...link,
      source: link.target,
      target: link.source
    };
  }
  return link;
};
const getArrowAdjustedPoints = (source, target) => {
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
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const applyViewportTransform = () => {
  if (!networkViewport) return;
  networkViewport.setAttribute(
    'transform',
    `translate(${networkState.panX} ${networkState.panY}) scale(${networkState.zoom})`
  );
};

const setZoom = (nextZoom, anchorX = NETWORK_VIEW.width / 2, anchorY = NETWORK_VIEW.height / 2) => {
  const clampedZoom = clamp(nextZoom, 0.55, 2.6);
  const ratio = clampedZoom / networkState.zoom;

  networkState.panX = anchorX - (anchorX - networkState.panX) * ratio;
  networkState.panY = anchorY - (anchorY - networkState.panY) * ratio;
  networkState.zoom = clampedZoom;
  applyViewportTransform();
};

const resetViewport = () => {
  networkState.zoom = 1;
  networkState.panX = 0;
  networkState.panY = 0;
  applyViewportTransform();
};

const getSvgPoint = (clientX, clientY) => {
  const rect = networkSvg.getBoundingClientRect();
  const scaleX = NETWORK_VIEW.width / rect.width;
  const scaleY = NETWORK_VIEW.height / rect.height;
  return {
    x: (clientX - rect.left) * scaleX,
    y: (clientY - rect.top) * scaleY
  };
};

const bindViewportInteractions = () => {
  zoomInButton?.addEventListener('click', () => {
    setZoom(networkState.zoom * 1.18);
  });

  zoomOutButton?.addEventListener('click', () => {
    setZoom(networkState.zoom / 1.18);
  });

  zoomResetButton?.addEventListener('click', () => {
    resetViewport();
  });

  networkSvg.addEventListener(
    'wheel',
    (event) => {
      event.preventDefault();
      const point = getSvgPoint(event.clientX, event.clientY);
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      setZoom(networkState.zoom * factor, point.x, point.y);
    },
    { passive: false }
  );

  networkSvg.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    if (event.target instanceof Element && event.target.closest('.network-node')) return;
    networkState.isDragging = true;
    networkState.dragStartX = event.clientX;
    networkState.dragStartY = event.clientY;
    networkState.dragOriginX = networkState.panX;
    networkState.dragOriginY = networkState.panY;
    networkSvg.classList.add('is-dragging');
    networkSvg.setPointerCapture(event.pointerId);
  });

  networkSvg.addEventListener('pointermove', (event) => {
    if (!networkState.isDragging) return;
    const rect = networkSvg.getBoundingClientRect();
    const deltaX = ((event.clientX - networkState.dragStartX) / rect.width) * NETWORK_VIEW.width;
    const deltaY = ((event.clientY - networkState.dragStartY) / rect.height) * NETWORK_VIEW.height;
    networkState.panX = networkState.dragOriginX + deltaX;
    networkState.panY = networkState.dragOriginY + deltaY;
    applyViewportTransform();
  });

  const stopDragging = (event) => {
    if (!networkState.isDragging) return;
    networkState.isDragging = false;
    networkSvg.classList.remove('is-dragging');
    if (event?.pointerId !== undefined && networkSvg.hasPointerCapture(event.pointerId)) {
      networkSvg.releasePointerCapture(event.pointerId);
    }
  };

  networkSvg.addEventListener('pointerup', stopDragging);
  networkSvg.addEventListener('pointercancel', stopDragging);
  networkSvg.addEventListener('pointerleave', stopDragging);
};

const beginNodeDrag = (paperId, group, event) => {
  event.stopPropagation();
  const point = getSvgPoint(event.clientX, event.clientY);
  const offset = getNodeOffset(paperId);
  const currentPosition = renderedGraph.positions.get(paperId);
  if (!currentPosition) return;

  networkState.draggedNodeId = paperId;
  networkState.draggedNodeMoved = false;
  networkState.nodeDragStartX = point.x;
  networkState.nodeDragStartY = point.y;
  networkState.nodeDragBaseX = currentPosition.x;
  networkState.nodeDragBaseY = currentPosition.y;
  networkState.nodeDragOriginDx = offset.dx;
  networkState.nodeDragOriginDy = offset.dy;
  group.classList.add('is-node-dragging');
  group.setPointerCapture(event.pointerId);
};

const updateNodePosition = (paperId, nextX, nextY) => {
  const position = renderedGraph.positions.get(paperId);
  const group = renderedGraph.groups.get(paperId);
  const label = renderedGraph.labels.get(paperId);
  if (!position || !group || !label) return;

  position.x = nextX;
  position.y = nextY;

  group.querySelectorAll('circle').forEach((circle) => {
    circle.setAttribute('cx', nextX);
    circle.setAttribute('cy', nextY);
  });

  label.setAttribute('x', nextX);
  label.setAttribute('y', nextY + position.r + 20);

  const links = renderedGraph.linksByPaper.get(paperId) || [];
  links.forEach(({ line, sourceId, targetId }) => {
    const source = renderedGraph.positions.get(sourceId);
    const target = renderedGraph.positions.get(targetId);
    if (!source || !target) return;
    const adjusted = getArrowAdjustedPoints(source, target);
    line.setAttribute('x1', adjusted.x1);
    line.setAttribute('y1', adjusted.y1);
    line.setAttribute('x2', adjusted.x2);
    line.setAttribute('y2', adjusted.y2);
  });
};

const dragNode = (event) => {
  if (!networkState.draggedNodeId) return;
  const point = getSvgPoint(event.clientX, event.clientY);
  const deltaX = (point.x - networkState.nodeDragStartX) / networkState.zoom;
  const deltaY = (point.y - networkState.nodeDragStartY) / networkState.zoom;
  const nextX = networkState.nodeDragBaseX + deltaX;
  const nextY = networkState.nodeDragBaseY + deltaY;
  networkState.draggedNodeMoved = Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2;

  nodeOffsets.set(networkState.draggedNodeId, {
    dx: networkState.nodeDragOriginDx + deltaX,
    dy: networkState.nodeDragOriginDy + deltaY
  });

  updateNodePosition(networkState.draggedNodeId, nextX, nextY);
};

const endNodeDrag = (event) => {
  if (!networkState.draggedNodeId) return;
  const group = renderedGraph.groups.get(networkState.draggedNodeId);
  if (group) {
    group.classList.remove('is-node-dragging');
    if (event?.pointerId !== undefined && group.hasPointerCapture(event.pointerId)) {
      group.releasePointerCapture(event.pointerId);
    }
  }
  if (networkState.draggedNodeMoved) {
    networkState.suppressClickNodeId = networkState.draggedNodeId;
  }
  networkState.draggedNodeId = null;
  networkState.draggedNodeMoved = false;
};

const buildPaperLinks = () => {
  const links = [];
  const seen = new Set();
  const addLink = (source, target, type, reason) => {
    if (!PAPER_BY_ID.has(source) || !PAPER_BY_ID.has(target) || source === target) return;
    const key = [source, target].sort().join('::');
    if (seen.has(key)) return;
    seen.add(key);
    links.push({ source, target, type, reason });
  };

  CATEGORIES.forEach((category) => {
    const papers = PAPERS
      .filter((paper) => paper.categories.includes(category.id))
      .sort((a, b) => a.year - b.year || a.short.localeCompare(b.short));

    for (let index = 1; index < papers.length; index += 1) {
      addLink(
        papers[index - 1].id,
        papers[index].id,
        'core',
        `${category.name}方向内的时间演进`
      );
    }
  });

  const manualLinks = [
    ['kd_foundation', 'fedfree', 'cross', '知识蒸馏基础启发异构联邦知识迁移'],
    ['fedavg', 'fedprox', 'core', '在FedAvg上缓解异构环境下的本地漂移'],
    ['fedavg', 'scaffold', 'core', '围绕FedAvg训练不稳定问题做校正'],
    ['fedavg', 'fedadam', 'core', '服务端优化器沿着FedAvg聚合范式演进'],
    ['fedavg', 'perfedavg', 'cross', '从统一全局模型延展到个性化初始化'],
    ['fedprox', 'moon', 'cross', '从优化稳定性进一步延伸到个性化表征约束'],
    ['scaffold', 'moon', 'cross', '从控制漂移延伸到对比式个性化建模'],
    ['feddiff', 'feddm', 'core', '扩散模型在联邦场景中的进一步训练范式'],
    ['promptfl', 'fedtp', 'core', '联邦提示学习路线内部的延展'],
    ['comm', 'moon', 'cross', '对齐与表征学习思想对个性化联邦有启发'],
    ['fairness_frontier', 'fairness_survey_2026', 'core', '公平性综述脉络的持续展开'],
    ['dtfl', 'fedavg', 'cross', '系统部署路线建立在经典联邦训练范式之上']
  ];

  manualLinks.forEach(([source, target, type, reason]) => addLink(source, target, type, reason));
  return links;
};

const PAPER_LINKS = buildPaperLinks();

const paperDegree = PAPER_LINKS.reduce((accumulator, link) => {
  accumulator[link.source] = (accumulator[link.source] || 0) + 1;
  accumulator[link.target] = (accumulator[link.target] || 0) + 1;
  return accumulator;
}, {});

const getVisiblePapers = () =>
  PAPERS.filter((paper) =>
    networkState.filter === 'all' ? true : paper.categories.includes(networkState.filter)
  );

const getVisiblePaperIds = () => new Set(getVisiblePapers().map((paper) => paper.id));

const getVisibleLinks = () => {
  const visibleIds = getVisiblePaperIds();
  return PAPER_LINKS.filter((link) => visibleIds.has(link.source) && visibleIds.has(link.target));
};

const buildLayout = (papers) => {
  const categories = networkState.filter === 'all'
    ? CATEGORIES.map((category) => category.id)
    : [networkState.filter];
  const centers = new Map();
  const radiusX = networkState.filter === 'all' ? 370 : 0;
  const radiusY = networkState.filter === 'all' ? 245 : 0;
  const centerX = NETWORK_VIEW.width / 2;
  const centerY = NETWORK_VIEW.height / 2;

  const primaryCategoryCounts = papers.reduce((accumulator, paper) => {
    const categoryId = getPrimaryCategory(paper);
    accumulator.set(categoryId, (accumulator.get(categoryId) || 0) + 1);
    return accumulator;
  }, new Map());
  const denseCategories = new Set(
    [...primaryCategoryCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([categoryId]) => categoryId)
  );

  categories.forEach((categoryId, index) => {
    if (networkState.filter === 'all') {
      const angle = (-Math.PI / 2) + (index / categories.length) * Math.PI * 2;
      const categoryWeight = primaryCategoryCounts.get(categoryId) || 0;
      const spreadBoost = denseCategories.has(categoryId) ? 1.16 + Math.min(categoryWeight * 0.01, 0.08) : 1;
      centers.set(categoryId, {
        x: centerX + Math.cos(angle) * radiusX * spreadBoost,
        y: centerY + Math.sin(angle) * radiusY * spreadBoost
      });
    } else {
      centers.set(categoryId, { x: centerX, y: centerY });
    }
  });

  const byCategory = new Map();
  papers.forEach((paper) => {
    const categoryId = networkState.filter === 'all'
      ? getPrimaryCategory(paper)
      : networkState.filter;
    if (!byCategory.has(categoryId)) byCategory.set(categoryId, []);
    byCategory.get(categoryId).push(paper);
  });

  const positions = new Map();
  byCategory.forEach((categoryPapers, categoryId) => {
    const clusterCenter = centers.get(categoryId);
    const sorted = [...categoryPapers].sort((a, b) => a.year - b.year || a.short.localeCompare(b.short));
    const densityBoost = denseCategories.has(categoryId) ? 1.24 : 1;

    sorted.forEach((paper, index) => {
      const yearIndex = uniqueYears.indexOf(paper.year);
      const orbit = (88 + yearIndex * 10) * densityBoost;
      const angle = (index / Math.max(sorted.length, 1)) * Math.PI * 2;
      const wobble = (index % 2 === 0 ? 28 : -24) * densityBoost;
      const offset = getNodeOffset(paper.id);
      positions.set(paper.id, {
        x: clusterCenter.x + Math.cos(angle) * orbit + Math.sin(angle * 2) * 24 * densityBoost + offset.dx,
        y: clusterCenter.y + Math.sin(angle) * (orbit * 0.7) + wobble + offset.dy,
        r: 15 + Math.min((paperDegree[paper.id] || 0) * 1.8, 10)
      });
    });
  });

  return positions;
};

const renderFilterChips = () => {
  const chips = [
    { id: 'all', label: '全部论文' },
    ...CATEGORIES.map((category) => ({ id: category.id, label: category.name }))
  ];

  networkFilters.innerHTML = chips
    .map(
      (chip) =>
        `<button class="filter-chip ${networkState.filter === chip.id ? 'active' : ''}" data-filter="${chip.id}" type="button">${escapeHtml(chip.label)}</button>`
    )
    .join('');

  networkFilters.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      networkState.filter = button.dataset.filter;
      const visiblePapers = getVisiblePapers();
      if (!visiblePapers.some((paper) => paper.id === networkState.selectedId)) {
        networkState.selectedId = visiblePapers[0]?.id || null;
      }
      renderPaperNetwork();
      renderFilterChips();
    });
  });
};

const renderNetworkDetail = (paper, links) => {
  if (!paper) {
    networkDetail.innerHTML = '<p class="network-empty">当前筛选下暂无论文节点。</p>';
    return;
  }

  const incoming = links
    .filter((link) => link.target === paper.id)
    .map((link) => {
      const neighborId = link.source;
      return {
        paper: PAPER_BY_ID.get(neighborId),
        reason: link.reason,
        type: link.type
      };
    })
    .filter((item) => item.paper);
  const outgoing = links
    .filter((link) => link.source === paper.id)
    .map((link) => {
      const neighborId = link.target;
      return {
        paper: PAPER_BY_ID.get(neighborId),
        reason: link.reason,
        type: link.type
      };
    })
    .filter((item) => item.paper);
  const neighbors = [...incoming, ...outgoing];

  networkDetail.innerHTML = `
    <div>
      <p class="eyebrow">Selected Paper</p>
      <h3>${escapeHtml(paper.short)}</h3>
      <p>${escapeHtml(paper.title)}</p>
    </div>
    <div class="detail-meta-grid">
      <div class="meta-box">
        <strong>年份</strong>
        <span>${paper.year}</span>
      </div>
      <div class="meta-box">
        <strong>作者</strong>
        <span>${escapeHtml(paper.first_author)}</span>
      </div>
      <div class="meta-box">
        <strong>方向</strong>
        <span>${escapeHtml(paper.categories.map(getCategoryName).join(' / '))}</span>
      </div>
      <div class="meta-box">
        <strong>Venue</strong>
        <span>${escapeHtml(paper.venue)}</span>
      </div>
    </div>
    <p>${escapeHtml(paper.idea)}</p>
    <div class="detail-tags">
      ${neighbors.length
        ? neighbors
            .slice(0, 5)
            .map(
              (neighbor) =>
                `<span class="chip">${escapeHtml(neighbor.paper.short)} · ${escapeHtml(neighbor.type === 'core' ? '主线' : '启发')}</span>`
            )
            .join('')
        : '<span class="chip">当前没有已定义的关联节点</span>'}
    </div>
    <div class="detail-flow">
      <div class="detail-flow-block">
        <strong>受到这些论文启发</strong>
        <div class="detail-flow-list">
          ${incoming.length
            ? incoming
                .map(
                  (item) =>
                    `<span class="chip">${escapeHtml(item.paper.short)} · ${escapeHtml(item.type === 'core' ? '主线输入' : '跨类启发')}</span>`
                )
                .join('')
            : '<span class="chip">当前未标注更早来源</span>'}
        </div>
      </div>
      <div class="detail-flow-block">
        <strong>又启发了这些论文</strong>
        <div class="detail-flow-list">
          ${outgoing.length
            ? outgoing
                .map(
                  (item) =>
                    `<span class="chip">${escapeHtml(item.paper.short)} · ${escapeHtml(item.type === 'core' ? '主线输出' : '跨类外溢')}</span>`
                )
                .join('')
            : '<span class="chip">当前未标注后续影响</span>'}
        </div>
      </div>
    </div>
    <p>${escapeHtml(neighbors[0]?.reason || '点击左侧其它节点可以查看它与当前技术路线中的连接原因。')}</p>
    <a class="detail-link" href="paper.html?id=${encodeURIComponent(paper.id)}">查看论文详情</a>
  `;
};

const renderPaperNetwork = () => {
  const visiblePapers = getVisiblePapers();
  const visibleLinks = getVisibleLinks();
  const directedVisibleLinks = visibleLinks.map(getDirectedLink);
  const layout = buildLayout(visiblePapers);

  if (!visiblePapers.some((paper) => paper.id === networkState.selectedId)) {
    const fallback = [...visiblePapers].sort((a, b) => (paperDegree[b.id] || 0) - (paperDegree[a.id] || 0))[0];
    networkState.selectedId = fallback?.id || null;
  }

  networkSvg.innerHTML = '';
  renderedGraph.positions = new Map(layout);
  renderedGraph.groups = new Map();
  renderedGraph.labels = new Map();
  renderedGraph.linksByPaper = new Map();
  const defs = document.createElementNS(SVG_NS, 'defs');
  defs.innerHTML = `
    <marker id="arrow-core" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(164, 61, 47, 0.72)"></path>
    </marker>
    <marker id="arrow-cross" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(15, 118, 110, 0.82)"></path>
    </marker>
  `;
  networkSvg.appendChild(defs);
  networkViewport = document.createElementNS(SVG_NS, 'g');
  networkViewport.setAttribute('class', 'network-viewport');
  networkSvg.appendChild(networkViewport);

  directedVisibleLinks.forEach((directedLink) => {
    const source = layout.get(directedLink.source);
    const target = layout.get(directedLink.target);
    if (!source || !target) return;
    const adjusted = getArrowAdjustedPoints(source, target);

    const line = document.createElementNS(SVG_NS, 'line');
    const isActive = directedLink.source === networkState.selectedId || directedLink.target === networkState.selectedId;
    line.setAttribute('x1', adjusted.x1);
    line.setAttribute('y1', adjusted.y1);
    line.setAttribute('x2', adjusted.x2);
    line.setAttribute('y2', adjusted.y2);
    line.setAttribute('class', `network-link ${directedLink.type} ${networkState.selectedId && !isActive ? 'dimmed' : ''}`);
    line.setAttribute('marker-end', `url(#${directedLink.type === 'core' ? 'arrow-core' : 'arrow-cross'})`);
    networkViewport.appendChild(line);

    [directedLink.source, directedLink.target].forEach((paperId) => {
      if (!renderedGraph.linksByPaper.has(paperId)) renderedGraph.linksByPaper.set(paperId, []);
      renderedGraph.linksByPaper.get(paperId).push({
        line,
        sourceId: directedLink.source,
        targetId: directedLink.target
      });
    });
  });

  visiblePapers.forEach((paper) => {
    const node = layout.get(paper.id);
    if (!node) return;

    const group = document.createElementNS(SVG_NS, 'g');
    const isActive = paper.id === networkState.selectedId;
    const isConnected = directedVisibleLinks.some(
      (link) =>
        (link.source === networkState.selectedId && link.target === paper.id) ||
        (link.target === networkState.selectedId && link.source === paper.id)
    );
    const shouldDim = networkState.selectedId && !isActive && !isConnected;
    group.setAttribute('class', `network-node ${isActive ? 'active' : ''} ${shouldDim ? 'dimmed' : ''}`);
    group.setAttribute('tabindex', '0');
    group.setAttribute('role', 'button');
    group.setAttribute('aria-label', paper.short);

    const circle = document.createElementNS(SVG_NS, 'circle');
    circle.setAttribute('cx', node.x);
    circle.setAttribute('cy', node.y);
    circle.setAttribute('r', node.r);
    circle.setAttribute('fill', CATEGORY_COLORS[getPrimaryCategory(paper)] || '#a43d2f');
    group.appendChild(circle);

    const ring = document.createElementNS(SVG_NS, 'circle');
    ring.setAttribute('cx', node.x);
    ring.setAttribute('cy', node.y);
    ring.setAttribute('r', node.r + 7);
    ring.setAttribute('fill', 'transparent');
    ring.setAttribute('stroke', 'rgba(30, 36, 48, 0.08)');
    ring.setAttribute('stroke-width', '1');
    group.appendChild(ring);

    group.addEventListener('pointerdown', (event) => {
      if (event.button !== 0) return;
      beginNodeDrag(paper.id, group, event);
    });
    group.addEventListener('pointermove', (event) => {
      dragNode(event);
    });
    group.addEventListener('pointerup', (event) => {
      endNodeDrag(event);
    });
    group.addEventListener('pointercancel', (event) => {
      endNodeDrag(event);
    });
    group.addEventListener('click', () => {
      if (networkState.suppressClickNodeId === paper.id) {
        networkState.suppressClickNodeId = null;
        return;
      }
      networkState.selectedId = paper.id;
      renderPaperNetwork();
    });
    group.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        networkState.selectedId = paper.id;
        renderPaperNetwork();
      }
    });
    networkViewport.appendChild(group);
    renderedGraph.groups.set(paper.id, group);

    const label = document.createElementNS(SVG_NS, 'text');
    label.setAttribute('x', node.x);
    label.setAttribute('y', node.y + node.r + 20);
    label.setAttribute('class', `network-label ${shouldDim ? 'dimmed' : ''}`);
    label.textContent = paper.short;
    networkViewport.appendChild(label);
    renderedGraph.labels.set(paper.id, label);
  });

  applyViewportTransform();
  renderNetworkDetail(PAPER_BY_ID.get(networkState.selectedId), directedVisibleLinks);
};

bindViewportInteractions();
renderFilterChips();
renderPaperNetwork();

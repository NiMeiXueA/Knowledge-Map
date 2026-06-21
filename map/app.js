const root = document.getElementById('category-root');
const stats = document.getElementById('hero-stats');
const searchInput = document.getElementById('paper-search-input');
const searchClear = document.getElementById('paper-search-clear');
const searchStatus = document.getElementById('search-status');
const searchToggle = document.getElementById('paper-search-toggle');
const searchPanel = document.getElementById('hero-search-panel');

const CATEGORY_BY_ID = new Map(CATEGORIES.map((category) => [category.id, category]));
const uniqueYears = [...new Set(PAPERS.map((paper) => paper.year))].sort((a, b) => a - b);
const totalCategoryCopies = PAPERS.reduce((sum, paper) => sum + paper.categories.length, 0);

stats.innerHTML = [
  `<span class="stat-pill">论文总数：${PAPERS.length}</span>`,
  `<span class="stat-pill">大类数量：${CATEGORIES.length}</span>`,
  `<span class="stat-pill">分类副本数：${totalCategoryCopies}</span>`,
  `<span class="stat-pill">时间跨度：${uniqueYears[0]} - ${uniqueYears[uniqueYears.length - 1]}</span>`
].join('');

const escapeHtml = (text) =>
  String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');

const innovationFocus = (paper) => {
  const seed = paper.idea.split(/[，。]/)[0].trim();
  return seed.length > 28 ? `${seed.slice(0, 28)}...` : seed;
};

const getCategoryName = (id) => CATEGORY_BY_ID.get(id)?.name || id;

const normalizeText = (text) =>
  String(text ?? '')
    .toLocaleLowerCase()
    .replace(/\s+/g, '');

const matchesPaper = (paper, keyword) => {
  if (!keyword) return true;

  const categoryNames = paper.categories.map(getCategoryName).join(' ');
  const searchableFields = [
    paper.short,
    paper.title,
    paper.first_author,
    paper.venue,
    paper.idea,
    paper.innovation,
    paper.year,
    categoryNames
  ];

  return searchableFields.some((field) => normalizeText(field).includes(keyword));
};

const renderEmptyState = (rawKeyword) => {
  const empty = document.createElement('section');
  empty.className = 'search-empty';
  empty.innerHTML = `
    <h2>没有找到匹配论文</h2>
    <p>当前关键词“${escapeHtml(rawKeyword)}”没有命中结果。可以试试论文简称、作者、年份、会议或更短的关键词。</p>
  `;
  root.appendChild(empty);
};

const updateSearchStatus = (rawKeyword, matchedPaperCount, matchedCategoryCount) => {
  if (!rawKeyword) {
    searchStatus.textContent = `当前展示全部 ${PAPERS.length} 篇论文，覆盖 ${CATEGORIES.length} 个方向。`;
    return;
  }

  searchStatus.textContent = `关键词“${rawKeyword}”匹配到 ${matchedPaperCount} 篇论文，分布在 ${matchedCategoryCount} 个方向。`;
};

const renderCategories = (rawKeyword = '') => {
  const normalizedKeyword = normalizeText(rawKeyword);
  root.innerHTML = '';

  let matchedPaperCount = 0;
  let matchedCategoryCount = 0;

  CATEGORIES.forEach((category) => {
    const papers = PAPERS
      .filter((paper) => paper.categories.includes(category.id) && matchesPaper(paper, normalizedKeyword))
      .sort((a, b) => a.year - b.year || a.short.localeCompare(b.short));

    if (!papers.length) return;

    matchedPaperCount += papers.length;
    matchedCategoryCount += 1;

    const byYear = new Map();
    papers.forEach((paper) => {
      if (!byYear.has(paper.year)) byYear.set(paper.year, []);
      byYear.get(paper.year).push(paper);
    });

    const section = document.createElement('section');
    section.className = 'category-panel';
    section.innerHTML = `
      <div class="category-head">
        <div>
          <p class="eyebrow">${escapeHtml(category.name)}</p>
          <h2>${escapeHtml(category.name)}</h2>
          <p>${escapeHtml(category.why)}</p>
        </div>
        <div class="category-overview">
          <article class="overview-box">
            <h3>为什么需要这一类</h3>
            <p>${escapeHtml(category.why)}</p>
          </article>
          <article class="overview-box">
            <h3>优点</h3>
            <p>${escapeHtml(category.advantages)}</p>
          </article>
          <article class="overview-box">
            <h3>缺点</h3>
            <p>${escapeHtml(category.disadvantages)}</p>
          </article>
        </div>
      </div>
      <div class="timeline"></div>
    `;

    const timeline = section.querySelector('.timeline');
    [...byYear.entries()].forEach(([year, yearPapers]) => {
      const branch = document.createElement('article');
      branch.className = 'year-branch';
      branch.innerHTML = `
        <div class="year-head">
          <span class="year">${year}</span>
          <span class="chip">该年论文：${yearPapers.length} 篇</span>
          <span class="chip">创新主线：${yearPapers.map((paper) => escapeHtml(innovationFocus(paper))).join(' / ')}</span>
        </div>
        <div class="innovation-tree"></div>
      `;

      const tree = branch.querySelector('.innovation-tree');
      yearPapers.forEach((paper) => {
        const node = document.createElement('article');
        node.className = 'innovation-branch';
        const categoryNames = paper.categories.map(getCategoryName).join(' / ');

        node.innerHTML = `
          <div class="innovation-label">
            <span class="innovation-kicker">创新点</span>
            <strong>${escapeHtml(innovationFocus(paper))}</strong>
          </div>
          <a class="paper-card" href="paper.html?id=${encodeURIComponent(paper.id)}">
            <div class="paper-meta">
              <span>${paper.year}</span>
              <span>${escapeHtml(paper.first_author)}</span>
            </div>
            <h3>${escapeHtml(paper.short)}</h3>
            <p><strong>主要思想：</strong>${escapeHtml(paper.idea)}</p>
            <p><strong>期刊/会议：</strong>${escapeHtml(paper.venue)}</p>
            <p><strong>方向：</strong>${escapeHtml(categoryNames)}</p>
            <div class="card-labels">
              <span class="chip">${escapeHtml(paper.title)}</span>
            </div>
            <div class="card-link">查看论文详情</div>
          </a>
        `;
        tree.appendChild(node);
      });

      timeline.appendChild(branch);
    });

    root.appendChild(section);
  });

  if (!matchedPaperCount) {
    renderEmptyState(rawKeyword);
  }

  updateSearchStatus(rawKeyword, matchedPaperCount, matchedCategoryCount);
};

searchInput?.addEventListener('input', (event) => {
  renderCategories(event.target.value.trim());
});

searchClear?.addEventListener('click', () => {
  searchInput.value = '';
  searchInput.focus();
  renderCategories('');
});

searchToggle?.addEventListener('click', () => {
  const isOpen = !searchPanel.hidden;
  searchPanel.hidden = isOpen;
  searchToggle.setAttribute('aria-expanded', String(!isOpen));

  if (!isOpen) {
    searchInput.focus();
  }
});

renderCategories();

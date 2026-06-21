const params = new URLSearchParams(window.location.search);
const paperId = params.get('id');
const paper = PAPERS.find((item) => item.id === paperId);
const root = document.getElementById('detail-root');

const buildFlowNarrative = (steps) => {
  if (!steps || !steps.length) return '当前未整理到该论文的流程说明。';
  if (steps.length === 1) return `这篇方法的主体过程集中在一个关键动作上：${steps[0]}。`;
  const first = steps[0];
  const middle = steps.slice(1, -1).join('，然后');
  const last = steps[steps.length - 1];
  return `从流程上看，这篇论文先${first}；随后${middle || first}；最后${last}。整个设计体现的是“先建立协同基础，再在本地或服务端完成知识融合，最后把结果回流到下一轮训练”的联邦优化思路。`;
};

if (!paper) {
  root.innerHTML = `
    <section class="detail-card">
      <a class="back-link" href="index.html">← 返回路线图</a>
      <h1>未找到对应论文</h1>
      <p class="detail-summary">请从首页重新进入，或检查 URL 参数是否正确。</p>
    </section>
  `;
} else {
  const categoryNames = paper.categories
    .map((id) => CATEGORIES.find((item) => item.id === id)?.name || id)
    .join(' / ');
  const flow = paper.flow_steps
    .map((step, index) => `
      <div class="flow-box">
        <span class="flow-index">0${index + 1}</span>
        <p>${step}</p>
      </div>
      ${index < paper.flow_steps.length - 1 ? '<div class="flow-arrow">↓</div>' : ''}
    `)
    .join('');
  const flowNarrative = paper.flow_narrative || buildFlowNarrative(paper.flow_steps);

  root.innerHTML = `
    <section class="detail-card">
      <a class="back-link" href="index.html">← 返回路线图</a>
      <div class="detail-header">
        <div>
          <p class="eyebrow">${paper.short}</p>
          <h1>${paper.title}</h1>
          <p class="detail-summary">${paper.idea}</p>
        </div>
        <div class="detail-meta">
          <div class="meta-box"><strong>简称</strong>${paper.short}</div>
          <div class="meta-box"><strong>年份</strong>${paper.year}</div>
          <div class="meta-box"><strong>第一作者</strong>${paper.first_author}</div>
          <div class="meta-box"><strong>期刊/会议</strong>${paper.venue}</div>
          <div class="meta-box"><strong>所属方向</strong>${categoryNames}</div>
          <div class="meta-box"><strong>原始文件</strong><span class="source-path">${paper.source_path}</span></div>
        </div>
      </div>
      <div class="section-grid">
        <section class="text-section">
          <h2>创新点</h2>
          <p>${paper.innovation}</p>
        </section>
        <section class="flow-section">
          <h2>主要流程图</h2>
          <div class="flow-diagram">${flow}</div>
          <p class="flow-caption">${flowNarrative}</p>
        </section>
      </div>
      <div class="section-grid">
        <section class="text-section">
          <h2>应用场景</h2>
          <p>${paper.applications}</p>
        </section>
        <section class="text-section">
          <h2>缺陷与局限</h2>
          <p>${paper.limitations}</p>
        </section>
      </div>
      <p class="detail-footer">说明：详情页内容基于当前工作区论文标题、摘要与方法线索整理成中文技术说明，适合做开题梳理、技术路线说明和论文对比阅读。</p>
    </section>
  `;
}

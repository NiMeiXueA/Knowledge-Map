import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Paper } from "../types/paper";

// 局限性类型与严重程度的中文标签映射，避免前端直接展示英文枚举
const LIMITATION_TYPE_LABELS: Record<string, string> = {
  paper_claimed: "论文自述",
  inferred: "推断",
};

const SEVERITY_LABELS: Record<string, string> = {
  low: "影响较小",
  medium: "影响中等",
  high: "影响较大",
};

function buildFlowNarrative(steps: string[]) {
  if (!steps.length) return "当前未整理到该论文的流程说明。";
  if (steps.length === 1) return `这篇方法的主体过程集中在一个关键动作上：${steps[0]}。`;

  const first = steps[0];
  const middle = steps.slice(1, -1).join("，然后");
  const last = steps[steps.length - 1];
  return `从流程上看，这篇论文先${first}；随后${middle || first}；最后${last}。整体思路是“先搭建问题与方法的基础，再在核心环节完成关键设计，最后落地到实验或应用验证”。`;
}

export function PaperDetailPage() {
  const { paperId = "" } = useParams();
  const [paper, setPaper] = useState<Paper | null>(null);

  useEffect(() => {
    api.getPaper(paperId).then(setPaper).catch(() => setPaper(null));
  }, [paperId]);

  if (!paper) {
    return (
      <main className="detail-shell">
        <section className="detail-card">
          <Link className="back-link" to="/">
            ← 返回路线图
          </Link>
          <h1>未找到对应论文</h1>
          <p className="detail-summary">请从首页重新进入，或等待论文分析任务完成。</p>
        </section>
      </main>
    );
  }

  const categoryNames = paper.categories.join(" / ");
  const flowNarrative = paper.flow_narrative || buildFlowNarrative(paper.flow_steps);
  const innovationItems = paper.innovation_points || [];
  const limitationItems = paper.limitation_points || [];

  return (
    <main className="detail-shell">
      <section className="detail-card">
        <Link className="back-link" to="/">
          ← 返回路线图
        </Link>
        <div className="detail-header">
          <div>
            <p className="eyebrow">{paper.short}</p>
            <h1>{paper.title}</h1>
            <p className="detail-summary">{paper.idea || paper.summary || "等待分析摘要生成。"}</p>
          </div>
          <div className="detail-meta">
            <div className="meta-box">
              <strong>简称</strong>
              {paper.short}
            </div>
            <div className="meta-box">
              <strong>年份</strong>
              {paper.year ?? "未知"}
            </div>
            <div className="meta-box">
              <strong>第一作者</strong>
              {paper.first_author || paper.authors[0] || "未知"}
            </div>
            <div className="meta-box">
              <strong>期刊/会议</strong>
              {paper.venue || "待补充"}
            </div>
            <div className="meta-box">
              <strong>所属方向</strong>
              {categoryNames}
            </div>
            <div className="meta-box">
              <strong>原始文件</strong>
              <span className="source-path">{paper.source_path}</span>
            </div>
          </div>
        </div>
        <div className="section-grid">
          <section className="text-section">
            <h2>创新点</h2>
            {innovationItems.length ? (
              <ul className="point-list">
                {innovationItems.map((item, index) => (
                  <li className="point-item" key={`inn-${index}`}>
                    <p className="point-head">{item.point}</p>
                    {item.evidence ? <p className="point-evidence">证据：{item.evidence}</p> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p>{paper.innovation || "暂无创新点分析。"}</p>
            )}
          </section>
          <section className="flow-section">
            <h2>主要流程图</h2>
            <div className="flow-diagram">
              {paper.flow_steps.length ? (
                paper.flow_steps.map((step, index) => (
                  <div key={`${step}-${index}`}>
                    <div className="flow-box">
                      <span className="flow-index">{String(index + 1).padStart(2, "0")}</span>
                      <p>{step}</p>
                    </div>
                    {index < paper.flow_steps.length - 1 ? <div className="flow-arrow">↓</div> : null}
                  </div>
                ))
              ) : (
                <p className="flow-caption">当前尚未抽取到结构化流程步骤。</p>
              )}
            </div>
            <p className="flow-caption">{flowNarrative}</p>
          </section>
        </div>
        <div className="section-grid">
          <section className="text-section">
            <h2>应用场景</h2>
            <p>{paper.applications || "暂无应用场景分析。"}</p>
          </section>
          <section className="text-section">
            <h2>缺陷与局限</h2>
            {limitationItems.length ? (
              <ul className="point-list">
                {limitationItems.map((item, index) => (
                  <li className="point-item" key={`lim-${index}`}>
                    <p className="point-head">{item.point}</p>
                    {item.evidence ? <p className="point-evidence">证据：{item.evidence}</p> : null}
                    <p className="point-tags">
                      <span className={`tag tag-type-${item.type}`}>
                        {LIMITATION_TYPE_LABELS[item.type] ?? item.type}
                      </span>
                      <span className={`tag tag-severity-${item.severity}`}>
                        {SEVERITY_LABELS[item.severity] ?? item.severity}
                      </span>
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p>{paper.limitations || "暂无局限性分析。"}</p>
            )}
          </section>
        </div>
        <p className="detail-footer">说明：详情页内容基于当前工作区论文标题、摘要与方法线索整理成中文技术说明，适合做开题梳理、技术路线说明和论文对比阅读。</p>
      </section>
    </main>
  );
}

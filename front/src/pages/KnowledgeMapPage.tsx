import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ApiModelSettings } from "../components/ApiModelSettings";
import { CategoryTimeline } from "../components/CategoryTimeline";
import { PaperSearchPanel } from "../components/PaperSearchPanel";
import { PaperUploadButton } from "../components/PaperUploadButton";
import { PaperUploadModal } from "../components/PaperUploadModal";
import { TaskProgressPanel } from "../components/TaskProgressPanel";
import type { PapersResponse, UploadTask } from "../types/paper";

type Props = {
  data: PapersResponse | null;
  refresh: () => Promise<void>;
};

export function KnowledgeMapPage({ data, refresh }: Props) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [task, setTask] = useState<UploadTask | null>(null);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const stats = useMemo(() => {
    if (!data) return { total: 0, categories: 0, copies: 0, range: "暂无" };
    const years = data.papers.map((paper) => paper.year).filter((year): year is number => typeof year === "number").sort((a, b) => a - b);
    const copies = data.papers.reduce((sum, paper) => sum + paper.categories.length, 0);
    return {
      total: data.papers.length,
      categories: data.categories.length,
      copies,
      range: years.length ? `${years[0]} - ${years[years.length - 1]}` : "暂无"
    };
  }, [data]);

  return (
    <>
      <header className="hero">
        <div className="hero-inner">
          <div className="hero-actions">
            <button className="hero-action-btn hero-settings-btn" type="button" onClick={() => setSettingsOpen(true)}>
              设置
            </button>
            <PaperSearchPanel keyword={keyword} open={searchOpen} onToggle={() => setSearchOpen((value) => !value)} onChange={setKeyword} />
            <PaperUploadButton onClick={() => setUploadOpen(true)} />
            <Link className="hero-action-btn hero-network-btn" to="/network">
              论文关系网
            </Link>
          </div>
          <section className="hero-main">
            <p className="eyebrow">Paper Research Roadmap</p>
            <h1>论文技术路线图</h1>
            <p className="hero-copy">
              上传任意研究方向的论文，自动按贡献类型、年份和创新点梳理成技术发展脉络，构建你自己的论文知识地图。
            </p>
            <div className="hero-stats">
              <span className="stat-pill">论文总数：{stats.total}</span>
              <span className="stat-pill">大类数量：{stats.categories}</span>
              <span className="stat-pill">分类副本数：{stats.copies}</span>
              <span className="stat-pill">时间跨度：{stats.range}</span>
            </div>
          </section>
        </div>
      </header>
      <main className="main-shell">
        <TaskProgressPanel task={task} />
        <section className="legend-card">
          <div>
            <h2>阅读方式</h2>
            <p>每个大类先给出“为什么会出现、优点、缺点”，下面按年份组织为树状时间线。点击卡片可进入论文详情页，查看创新点、主要流程、应用场景与缺陷分析。</p>
          </div>
          <div className="legend-tags">
            <span>年份节点</span>
            <span>创新标签</span>
            <span>论文卡片</span>
            <span>详情页跳转</span>
          </div>
        </section>
        {data ? <CategoryTimeline categories={data.categories} papers={data.papers} keyword={keyword} /> : <section className="legend-card"><p>正在加载论文数据...</p></section>}
      </main>
      <ApiModelSettings
        categories={data?.categories ?? []}
        onClose={() => setSettingsOpen(false)}
        onCollectionChanged={refresh}
        open={settingsOpen}
      />
      <PaperUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onCompleted={() => {
          void refresh();
          setUploadOpen(false);
        }}
        onTaskChange={setTask}
      />
    </>
  );
}

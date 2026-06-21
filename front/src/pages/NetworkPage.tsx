import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { PaperNetworkGraph } from "../components/PaperNetworkGraph";
import type { GraphPayload, PapersResponse } from "../types/paper";

type Props = {
  data: PapersResponse | null;
};

export function NetworkPage({ data }: Props) {
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], links: [] });
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    api.getGraph().then(setGraph);
  }, []);

  return (
    <main className="detail-shell">
      <Link className="back-link" to="/">
        ← 返回路线图首页
      </Link>
      {data ? (
        <PaperNetworkGraph
          categories={data.categories}
          papers={data.papers}
          graph={graph}
          filter={filter}
          setFilter={setFilter}
          selectedId={selectedId}
          setSelectedId={setSelectedId}
        />
      ) : (
        <section className="detail-card">
          <div className="network-head network-head-page">
            <div>
              <p className="eyebrow">Paper Network</p>
              <h1>论文关系网</h1>
              <p className="network-copy">把不同论文之间的继承关系、同方向演进和跨方向启发集中在一页里。你可以按方向筛选、点击节点查看说明，再进入论文详情页。</p>
            </div>
          </div>
          <p>正在加载关系图...</p>
        </section>
      )}
    </main>
  );
}

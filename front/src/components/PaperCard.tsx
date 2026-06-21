import { Link } from "react-router-dom";
import type { Category, Paper } from "../types/paper";

type Props = {
  paper: Paper;
  categories: Category[];
};

export function PaperCard({ paper, categories }: Props) {
  const categoryNames = paper.categories
    .map((id) => categories.find((category) => category.id === id)?.name || id)
    .join(" / ");

  return (
    <Link className="paper-card" to={`/paper/${paper.id}`}>
      <div className="paper-meta">
        <span>{paper.year ?? "未知"}</span>
        <span>{paper.first_author || "未知作者"}</span>
      </div>
      <h3>{paper.short}</h3>
      <p>
        <strong>主要思想：</strong>
        {paper.idea || paper.summary || "等待分析完成后展示。"}
      </p>
      <p>
        <strong>期刊/会议：</strong>
        {paper.venue || "待补充"}
      </p>
      <p>
        <strong>方向：</strong>
        {categoryNames}
      </p>
      <div className="card-labels">
        <span className="chip">{paper.title}</span>
      </div>
      <div className="card-link">查看论文详情</div>
    </Link>
  );
}


import type { UploadTask } from "../types/paper";

type Props = {
  task: UploadTask | null;
};

export function TaskProgressPanel({ task }: Props) {
  if (!task) return null;
  return (
    <section className="legend-card task-panel">
      <div>
        <h2>分析任务进度</h2>
        <p>{task.message}</p>
      </div>
      <div className="legend-tags">
        <span>状态：{task.status}</span>
        <span>阶段：{task.stage}</span>
        {task.paper_id ? <span>论文 ID：{task.paper_id}</span> : null}
      </div>
    </section>
  );
}


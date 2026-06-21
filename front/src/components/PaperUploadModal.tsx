import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { UploadTask } from "../types/paper";

type Props = {
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
  onTaskChange: (task: UploadTask | null) => void;
};

export function PaperUploadModal({ open, onClose, onCompleted, onTaskChange }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [references, setReferences] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!open) return;
    setFiles([]);
    setReferences("");
    setMessage("");
  }, [open]);

  if (!open) return null;

  const attachFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const pdfs = Array.from(incoming).filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    setFiles(pdfs);
  };

  const pollTask = async (taskId: string) => {
    const timer = window.setInterval(async () => {
      try {
        const task = await api.getTask(taskId);
        onTaskChange(task);
        if (task.status === "completed" || task.status === "failed") {
          window.clearInterval(timer);
          setUploading(false);
          if (task.status === "completed") {
            onCompleted();
          }
        }
      } catch (error) {
        window.clearInterval(timer);
        setUploading(false);
        setMessage(error instanceof Error ? error.message : "轮询任务失败");
      }
    }, 1800);
  };

  const submit = async () => {
    const items = references
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (!files.length || !items.length) return;
    if (items.length !== files.length) {
      setMessage("PDF 数量必须和 DOI / arXiv / 论文链接数量一致。");
      return;
    }
    setUploading(true);
    setMessage("");
    try {
      const response = await api.uploadPapers(files, items);
      onTaskChange({
        task_id: response.task_id,
        status: "processing",
        stage: "queued",
        message: "任务已创建，等待处理"
      });
      pollTask(response.task_id);
    } catch (error) {
      setUploading(false);
      setMessage(error instanceof Error ? error.message : "上传失败");
    }
  };

  return (
    <div className="overlay" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-head">
          <div>
            <p className="eyebrow">PDF Upload</p>
            <h2>添加论文</h2>
          </div>
          <button className="hero-action-btn" type="button" onClick={onClose}>
            关闭
          </button>
        </div>
        <button
          type="button"
          className={`upload-dropzone ${dragging ? "is-dragging" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            attachFiles(event.dataTransfer.files);
          }}
        >
          <strong>拖拽 PDF 到这里，或点击选择文件</strong>
          <span>每个 PDF 需要对应一行 DOI / arXiv / 论文链接</span>
        </button>
        <input ref={inputRef} type="file" hidden multiple accept="application/pdf" onChange={(event) => attachFiles(event.target.files)} />
        <div className="legend-tags">
          {files.length ? files.map((file) => <span key={file.name}>{file.name}</span>) : <span>当前尚未选择文件</span>}
        </div>
        <label className="search-field" style={{ display: "grid", gap: "0.5rem", marginTop: "1rem" }}>
          <span className="search-label">DOI / arXiv / 论文链接</span>
          <textarea
            rows={4}
            value={references}
            placeholder={"每行一个 DOI、arXiv ID、论文链接或标题\n例如：10.1145/3366423.3380143"}
            onChange={(event) => setReferences(event.target.value)}
          />
        </label>
        <div className="modal-actions">
          <button
            className="hero-action-btn hero-network-btn"
            type="button"
            onClick={submit}
            disabled={!files.length || !references.trim() || uploading}
          >
            {uploading ? "处理中..." : "开始检索并分析"}
          </button>
        </div>
        <p className="search-status">{message}</p>
      </div>
    </div>
  );
}

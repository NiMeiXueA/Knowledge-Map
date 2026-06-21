from __future__ import annotations

from datetime import datetime, timezone

from src.database.redis_client import RedisBackedStore


class KVRepository:
    """
    键值存储仓库：封装Redis操作，用于存储任务状态、论文数据和模型设置
    
    当Redis不可用时，自动回退到内存+文件存储
    """
    
    def __init__(self) -> None:
        self.store = RedisBackedStore()

    def set_task(
        self,
        task_id: str,
        *,
        status: str,
        stage: str,
        message: str,
        paper_id: str | None = None,
        error: str | None = None,
        created_at: str | None = None,
    ) -> dict:
        """
        设置任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态（processing/completed/failed）
            stage: 当前阶段（如pdf_parsing, metadata, source等）
            message: 状态消息
            paper_id: 关联的论文ID（可选）
            error: 错误信息（可选）
            created_at: 创建时间（可选，如不提供则使用当前时间）
            
        Returns:
            任务状态字典
        """
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_task(task_id) or {}
        payload = {
            "task_id": task_id,
            "status": status,
            "stage": stage,
            "message": message,
            "paper_id": paper_id or existing.get("paper_id"),
            "error": error,
            "created_at": created_at or existing.get("created_at") or now,
            "updated_at": now,
        }
        self.store.set_json(f"task:{task_id}", payload)
        return payload

    def get_task(self, task_id: str) -> dict | None:
        """获取任务状态"""
        return self.store.get_json(f"task:{task_id}")

    def set_paper_payload(self, paper_id: str, suffix: str, payload: dict) -> None:
        """
        设置论文数据载荷
        
        Args:
            paper_id: 论文ID
            suffix: 后缀（如"meta"表示元数据，"analysis"表示分析结果）
            payload: 数据载荷
        """
        self.store.set_json(f"paper:{paper_id}:{suffix}", payload)

    def get_model_settings(self) -> dict | None:
        """获取模型设置"""
        return self.store.get_json("settings:model")

    def set_model_settings(self, payload: dict) -> None:
        """设置模型设置"""
        self.store.set_json("settings:model", payload)


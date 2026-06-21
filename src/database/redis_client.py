from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path

from redis import Redis
from redis.exceptions import RedisError

from src.config import DATA_DIR, get_env

logger = logging.getLogger(__name__)

# 内存存储（Redis不可用时的回退）
_memory_store: dict[str, str] = {}
# 文件存储路径（Redis不可用时持久化到本地）
_fallback_store_path = DATA_DIR / "runtime_kv.json"


def _read_file_store() -> dict[str, str]:
    """从文件读取KV存储"""
    if not _fallback_store_path.exists():
        return {}
    try:
        return json.loads(_fallback_store_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_file_store(payload: dict[str, str]) -> None:
    """将KV存储写入文件"""
    _fallback_store_path.parent.mkdir(parents=True, exist_ok=True)
    _fallback_store_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_redis_client() -> Redis | None:
    """
    获取Redis客户端
    
    如果Redis不可用，返回None并记录警告日志
    """
    url = get_env("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = Redis.from_url(url, decode_responses=True)
        client.ping()
        return client
    except RedisError as exc:
        logger.warning("Redis unavailable, using in-memory fallback: %s", exc)
        return None


class RedisBackedStore:
    """
    Redis支持的存储类
    
    当Redis可用时使用Redis，否则回退到内存+文件存储
    """
    
    def __init__(self) -> None:
        self.client = get_redis_client()

    def set_json(self, key: str, value: Mapping[str, object]) -> None:
        """
        设置JSON数据
        
        Args:
            key: 键名
            value: 要存储的字典数据
        """
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if self.client is None:
            # Redis不可用，使用内存+文件存储
            _memory_store[key] = payload
            file_store = _read_file_store()
            file_store[key] = payload
            _write_file_store(file_store)
            return
        self.client.set(key, payload)

    def get_json(self, key: str) -> dict | None:
        """
        获取JSON数据
        
        Args:
            key: 键名
            
        Returns:
            解析后的字典，或None（如果不存在）
        """
        if self.client is None:
            # Redis不可用，从文件/内存读取
            file_store = _read_file_store()
            raw = file_store.get(key)
            if raw is not None:
                _memory_store[key] = raw
            else:
                raw = _memory_store.get(key)
        else:
            raw = self.client.get(key)
        if not raw:
            return None
        return json.loads(raw)

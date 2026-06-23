from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Mapping
from pathlib import Path

from redis import Redis
from redis.exceptions import RedisError

from src.config import DATA_DIR, get_env

logger = logging.getLogger(__name__)

# 内存存储（Redis不可用时的回退）
# 桌面单用户场景下足够使用，且作为 Redis 写入失败时的瞬态缓冲
_memory_store: dict[str, str] = {}
_memory_store_lock = threading.Lock()

# 文件存储路径（Redis不可用时持久化到本地）
# 注意：DATA_DIR 在桌面模式下会被重定向到用户数据目录
# 因此 runtime_kv.json 会跟随用户数据走，不会丢在安装目录
_FALLBACK_FILENAME = "runtime_kv.json"


def _fallback_store_path() -> Path:
    """
    根据当前 DATA_DIR 计算 fallback 文件路径。

    每次调用都会重新读取 DATA_DIR，确保桌面模式下数据目录重定向后路径仍然正确。
    """
    # 允许用户通过环境变量显式覆盖
    override = os.getenv("KNOWLEDGE_MAP_KV_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return DATA_DIR / _FALLBACK_FILENAME


def _read_file_store() -> dict[str, str]:
    """从文件读取KV存储"""
    path = _fallback_store_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_file_store(payload: dict[str, str]) -> None:
    """将KV存储写入文件"""
    path = _fallback_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 原子写入：先写入临时文件，再 rename，避免崩溃时数据损坏
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def get_redis_client() -> Redis | None:
    """
    获取Redis客户端

    如果Redis不可用，返回None并记录警告日志。

    桌面模式下：
    - REDIS_URL 未配置或无法连接时，自动降级到本地文件 + 内存存储
    - 用户不需要手动启动 Redis
    """
    url = get_env("REDIS_URL", "")  # 默认不强制连接 localhost:6379，桌面模式更友好
    if not url:
        return None
    try:
        client = Redis.from_url(url, decode_responses=True)
        client.ping()
        return client
    except RedisError as exc:
        logger.warning("Redis unavailable, using in-memory + file fallback: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001 — 任何意外都不应阻断 App 启动
        logger.warning("Redis init failed (%s), using in-memory + file fallback", exc)
        return None


class RedisBackedStore:
    """
    Redis支持的存储类

    当Redis可用时使用Redis，否则回退到内存+文件存储。

    线程安全：内存存储加锁，文件存储通过原子 rename 保证一致性。
    """

    def __init__(self) -> None:
        self.client = get_redis_client()
        if self.client is None:
            logger.info(
                "KVStore initialized with local fallback. File: %s",
                _fallback_store_path(),
            )

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
            with _memory_store_lock:
                _memory_store[key] = payload
                file_store = _read_file_store()
                file_store[key] = payload
                _write_file_store(file_store)
            return
        try:
            self.client.set(key, payload)
        except RedisError as exc:
            # 运行期 Redis 异常时，临时降级到内存 + 文件
            logger.warning("Redis set failed, falling back to local store: %s", exc)
            with _memory_store_lock:
                _memory_store[key] = payload
                file_store = _read_file_store()
                file_store[key] = payload
                _write_file_store(file_store)

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
                with _memory_store_lock:
                    _memory_store[key] = raw
            else:
                raw = _memory_store.get(key)
        else:
            try:
                raw = self.client.get(key)
            except RedisError as exc:
                logger.warning("Redis get failed, reading from local store: %s", exc)
                file_store = _read_file_store()
                raw = file_store.get(key) or _memory_store.get(key)
        if not raw:
            return None
        return json.loads(raw)

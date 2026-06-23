"""
桌面版后端启动脚本。

设计目标：
1. 不需要用户手动安装 Redis、手动启动 FastAPI。
2. 启动时自动选择可用端口（默认 8000，被占用时尝试 8001~8003）。
3. 把实际监听地址通过 stdout 协议通知父进程（Tauri）：
       KNOWLEDGE_MAP_LISTENING_ON http://127.0.0.1:PORT
   Tauri 端按行扫描 stdout 找到这行即可拿到 API 地址。
4. 始终监听 127.0.0.1，不对外暴露。
5. 关闭信号时优雅退出。

使用方式：
    python desktop/backend/run_backend.py

可选环境变量：
    KNOWLEDGE_MAP_PORT         强制使用指定端口（不再探测）
    KNOWLEDGE_MAP_HOST         监听地址（默认 127.0.0.1）
    KNOWLEDGE_MAP_DATA_DIR     数据目录（桌面模式由 Tauri 注入）
    KNOWLEDGE_MAP_ENV_PATH     显式指定 .env 路径
"""

from __future__ import annotations

import logging
import os
import socket
import sys
from pathlib import Path
from typing import Iterable

# ---------- 项目根目录与 sys.path ----------
# 源码模式下：本脚本位于 desktop/backend/run_backend.py，项目根目录往上跳三级。
# PyInstaller 打包模式下：代码会解压到 sys._MEIPASS，src 目录就在 _MEIPASS 下；
#   此时不存在"项目根"概念，主要靠 _MEIPASS 定位 src，靠 KNOWLEDGE_MAP_DATA_DIR 定位数据。
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    PROJECT_ROOT = Path(sys._MEIPASS).resolve()
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 把项目根目录加入 sys.path，保证 `from src.xxx import ...` 这种绝对 import 可用
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 切换工作目录到项目根，让相对路径（uploads/、paper/ 等）解析正确
# 桌面模式下：所有数据目录都由 KNOWLEDGE_MAP_DATA_DIR 重定向，chdir 不会影响实际写入位置
os.chdir(PROJECT_ROOT)

# 桌面模式默认重定向数据目录（仅当用户没有显式指定时）
# Tauri 端会通过环境变量 KNOWLEDGE_MAP_DATA_DIR 直接传入用户目录，
# 因此这里只在桌面运行且未指定时做兜底。
# 必须用 OS 用户目录而不是 PROJECT_ROOT——PyInstaller onefile 模式下
# PROJECT_ROOT 是 _MEIPASS（%TEMP%\_MEIxxxxx\），进程退出即清理，
# 数据会丢失。这里的兜底路径与 src-tauri/src/main.rs::user_data_dir() 对齐。
if not os.environ.get("KNOWLEDGE_MAP_DATA_DIR") and os.environ.get("KNOWLEDGE_MAP_DESKTOP") == "1":
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
        fallback_dir = base / "Knowledge-Map"
    elif sys.platform == "darwin":
        fallback_dir = Path.home() / "Library" / "Application Support" / "Knowledge-Map"
    else:
        fallback_dir = Path.home() / ".local" / "share" / "Knowledge-Map"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    os.environ["KNOWLEDGE_MAP_DATA_DIR"] = str(fallback_dir)

# ---------- 加载 .env ----------
# 优先加载项目根的 .env；桌面模式下 .env 可能在用户数据目录中（由 config.py 处理）
from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env", override=False)

# ---------- 标准库 / 第三方 import ----------
import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("knowledge_map.backend")

# ---------- 端口探测 ----------
DEFAULT_PORT_CANDIDATES = (8000, 8001, 8002, 8003)


def is_port_free(host: str, port: int) -> bool:
    """探测端口是否可用（bind 成功即视为可用）"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def pick_port(host: str, candidates: Iterable[int], forced: int | None) -> int:
    """从候选端口中选择一个可用端口；如果指定了 forced，直接返回它"""
    if forced is not None:
        return forced
    for port in candidates:
        if is_port_free(host, port):
            return port
    raise RuntimeError(
        "没有可用的端口（已尝试：" + ", ".join(str(p) for p in candidates) + "）。"
        " 可以通过环境变量 KNOWLEDGE_MAP_PORT 指定端口。"
    )


# ---------- stdout 协议 ----------
# Tauri 端按行读取 stdout，匹配以下前缀：
#   KNOWLEDGE_MAP_LISTENING_ON <url>     表示后端已在该地址监听
#   KNOWLEDGE_MAP_ERROR <msg>            表示后端启动失败
# 健康检查由 Tauri 端用 reqwest 轮询 /api/health 完成，sidecar 不再做自检
# （原来的 KNOWLEDGE_MAP_READY 协议行 Tauri 端没有处理，是冗余的）
LISTENING_TAG = "KNOWLEDGE_MAP_LISTENING_ON"


def emit_listening(host: str, port: int) -> None:
    url = f"http://{host}:{port}"
    # 必须 flush，否则父进程读不到
    print(f"{LISTENING_TAG} {url}", flush=True)
    logger.info("backend listening on %s", url)


# ---------- 主入口 ----------
def build_app() -> FastAPI:
    """延迟导入 FastAPI app，确保 sys.path / .env 已就绪"""
    from src.main import app  # noqa: WPS433 — 延迟导入避免上面的副作用影响 import 顺序
    return app


def main() -> None:
    host = os.environ.get("KNOWLEDGE_MAP_HOST", "127.0.0.1")
    forced_port_raw = os.environ.get("KNOWLEDGE_MAP_PORT", "").strip()
    forced_port = int(forced_port_raw) if forced_port_raw.isdigit() else None

    try:
        port = pick_port(host, DEFAULT_PORT_CANDIDATES, forced_port)
    except Exception as exc:
        # 探测失败时也要在 stdout 留痕，便于 Tauri 弹错误提示
        print(f"KNOWLEDGE_MAP_ERROR {exc}", flush=True)
        raise

    base_url = f"http://{host}:{port}"

    # 先 emit LISTENING，Tauri 端会拿这个地址做健康检查
    emit_listening(host, port)

    # 延迟导入 FastAPI app，确保 sys.path / .env 已就绪
    app = build_app()

    logger.info(
        "starting uvicorn at %s, data_dir=%s",
        base_url,
        os.environ.get("KNOWLEDGE_MAP_DATA_DIR") or "(project src/data)",
    )

    # 重要：不开 reload，桌面模式不需要也不应该开
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,  # 减少 stdout 噪音，让协议行更醒目
    )


if __name__ == "__main__":
    main()

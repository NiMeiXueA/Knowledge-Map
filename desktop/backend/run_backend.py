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

import ctypes
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Iterable

# ---------- 启动早期诊断日志（绕开 stdout/stderr 的不确定性）----------
# 之前的 bug：sidecar 启动后秒死，但 Tauri 端完全收不到 stdout/stderr。
# 这段代码直接写文件，让我们能看到 Python 是否启动到这一步、sys.stdout 是否有效、
# 父进程 pid 是什么。绕开 stdout 是否被新 console 接管的问题。
def _early_boot_log(msg: str) -> None:
    try:
        log_dir = os.environ.get("KNOWLEDGE_MAP_DATA_DIR") or os.path.expanduser("~")
        log_path = Path(log_dir) / "sidecar-boot.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass  # 诊断日志不能影响主流程

_early_boot_log(
    f"=== sidecar boot start, pid={os.getpid()}, ppid={os.getppid()}, "
    f"frozen={getattr(sys, 'frozen', False)}, stdout={sys.stdout!r}, stderr={sys.stderr!r}"
)

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


# ---------- 父进程 watchdog ----------
# 问题：Tauri 端的 `Child::kill()` 只能 kill 直接子进程——也就是 PyInstaller onefile
# 的 boot loader。真正的 Python 解释器是 boot loader 的子进程，Windows 不会自动级联 kill，
# 所以 Tauri 主应用异常退出（崩溃 / 任务管理器强杀 / 关机）时 Python 子进程会变成孤儿，
# 继续占用 8000~8003 端口。下次启动 Tauri 探测到端口被占，会逐个递增端口，最终
# `pick_port` raise RuntimeError，前端表现为 "Failed to fetch"。
#
# 解法：sidecar 启动时记录父进程 PID，后台 daemon 线程每秒探测父进程是否还活着，
# 父进程死了立即 `os._exit(0)` 强制退出（不能 raise SystemExit，因为 daemon 线程
# 抛不到主线程；用 os._exit 跳过 Python 清理，保证立即释放端口）。
def _parent_pid_at_start() -> int:
    """优先用 Tauri 注入的 KNOWLEDGE_MAP_PARENT_PID（更准确）。
    回退到 os.getppid()（PyInstaller onefile 模式下拿到的是 boot loader pid，
    不是 Tauri pid，监控这个 pid 不能检测到 Tauri 退出）。"""
    env_pid = os.environ.get("KNOWLEDGE_MAP_PARENT_PID", "").strip()
    if env_pid.isdigit():
        return int(env_pid)
    return os.getppid()


def _is_parent_alive(parent_pid: int) -> bool:
    """探测父进程是否还活着。Windows 用 OpenProcess，POSIX 用 os.kill(pid, 0)。"""
    if parent_pid <= 0:
        return False
    if sys.platform == "win32":
        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000；父进程死了 OpenProcess 会返回 0
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # 关键：必须显式声明返回值类型为 c_void_p（64-bit 指针），否则 ctypes 默认 c_int
        # 是 32-bit，64-bit Windows 上 HANDLE 的高位被截断后可能变成 0，误判父进程已死，
        # watchdog 会立刻 kill 自己 —— 这是 release 模式下 sidecar 启动后秒死的元凶之一
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
        ]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, parent_pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(parent_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # 进程存在但没权限发信号——视为还活着
        return True
    return True


def _start_parent_watchdog(parent_pid: int) -> None:
    _early_boot_log(f"watchdog starting, monitoring parent_pid={parent_pid}")

    def _loop():
        while True:
            time.sleep(1.0)
            try:
                if not _is_parent_alive(parent_pid):
                    # 父进程已退出——立即终止自己，避免变成孤儿占用端口
                    # 用 os._exit 而不是 sys.exit：daemon 线程里 sys.exit 抛不到主线程
                    # 用退出码 0 而非非零：这是预期退出，不是崩溃
                    _early_boot_log(
                        f"watchdog: parent_pid={parent_pid} no longer alive, exiting sidecar"
                    )
                    os._exit(0)
            except Exception as exc:
                # 探测本身异常不能让 sidecar 死掉，下一轮继续尝试
                _early_boot_log(f"watchdog: probe error: {exc!r}")
                continue

    threading.Thread(target=_loop, daemon=True, name="parent-watchdog").start()


# ---------- 主入口 ----------
def build_app() -> FastAPI:
    """延迟导入 FastAPI app，确保 sys.path / .env 已就绪"""
    from src.main import app  # noqa: WPS433 — 延迟导入避免上面的副作用影响 import 顺序
    return app


def main() -> None:
    # 尽早启动 watchdog——必须在 uvicorn 占用端口之前装好，否则来不及保护
    _start_parent_watchdog(_parent_pid_at_start())

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
    # access_log 暂时打开，用于诊断前端 fetch 是否到达后端
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()

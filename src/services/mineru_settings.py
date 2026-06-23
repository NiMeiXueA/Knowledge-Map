from __future__ import annotations

from dataclasses import dataclass

from dotenv import dotenv_values, set_key

from src.config import ENV_PATH
from src.schemas import MineruSettingsIn, MineruSettingsSummary


@dataclass
class RuntimeMineruSettings:
    """运行时 MinerU 远程解析配置"""
    api_token: str
    api_base_url: str
    backend: str
    lang: str
    api_timeout: int


def _clean_str(value: object, default: str = "") -> str:
    text = str(value or default)
    return text.strip().strip("'").strip('"')


def save_mineru_settings(payload: MineruSettingsIn) -> MineruSettingsSummary:
    """保存 MinerU 配置到 .env，返回摘要"""
    ENV_PATH.touch(exist_ok=True)
    cleaned_token = payload.api_token.strip()
    cleaned_base_url = payload.api_base_url.strip() or "https://mineru.net"
    cleaned_backend = payload.backend.strip() or "pipeline"
    cleaned_lang = payload.lang.strip() or "ch"
    timeout = max(60, int(payload.api_timeout or 600))

    set_key(str(ENV_PATH), "MINERU_API_TOKEN", cleaned_token)
    set_key(str(ENV_PATH), "MINERU_API_BASE_URL", cleaned_base_url)
    set_key(str(ENV_PATH), "MINERU_BACKEND", cleaned_backend)
    set_key(str(ENV_PATH), "MINERU_LANG", cleaned_lang)
    set_key(str(ENV_PATH), "MINERU_API_TIMEOUT", str(timeout))

    # 同步到当前进程的 os.environ，避免重启立即生效
    import os
    os.environ["MINERU_API_TOKEN"] = cleaned_token
    os.environ["MINERU_API_BASE_URL"] = cleaned_base_url
    os.environ["MINERU_BACKEND"] = cleaned_backend
    os.environ["MINERU_LANG"] = cleaned_lang
    os.environ["MINERU_API_TIMEOUT"] = str(timeout)

    return MineruSettingsSummary(
        api_base_url=cleaned_base_url,
        backend=cleaned_backend,  # type: ignore[arg-type]
        lang=cleaned_lang,
        api_timeout=timeout,
        api_token_configured=bool(cleaned_token),
    )


def get_mineru_settings_summary() -> MineruSettingsSummary:
    """获取 MinerU 配置摘要（不含 token 明文）"""
    values = dotenv_values(ENV_PATH)
    backend_raw = _clean_str(values.get("MINERU_BACKEND"), "pipeline")
    if backend_raw not in {"pipeline", "vlm"}:
        backend_raw = "pipeline"
    return MineruSettingsSummary(
        api_base_url=_clean_str(values.get("MINERU_API_BASE_URL"), "https://mineru.net") or "https://mineru.net",
        backend=backend_raw,  # type: ignore[arg-type]
        lang=_clean_str(values.get("MINERU_LANG"), "ch") or "ch",
        api_timeout=int(values.get("MINERU_API_TIMEOUT") or 600),
        api_token_configured=bool(_clean_str(values.get("MINERU_API_TOKEN"))),
    )


def get_runtime_mineru_settings() -> RuntimeMineruSettings:
    """获取运行时 MinerU 配置（含 token 明文，用于实际调用）"""
    import os
    backend = _clean_str(os.getenv("MINERU_BACKEND"), "pipeline")
    if backend not in {"pipeline", "vlm"}:
        backend = "pipeline"
    return RuntimeMineruSettings(
        api_token=_clean_str(os.getenv("MINERU_API_TOKEN")),
        api_base_url=_clean_str(os.getenv("MINERU_API_BASE_URL"), "https://mineru.net") or "https://mineru.net",
        backend=backend,
        lang=_clean_str(os.getenv("MINERU_LANG"), "ch") or "ch",
        api_timeout=max(60, int(os.getenv("MINERU_API_TIMEOUT") or 600)),
    )

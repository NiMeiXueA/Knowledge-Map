from __future__ import annotations

from dataclasses import dataclass

from dotenv import dotenv_values, set_key

from src.config import ENV_PATH
from src.database.kv import KVRepository
from src.schemas import ModelSettingsIn, ModelSettingsSummary


@dataclass
class RuntimeModelSettings:
    """运行时LLM模型设置"""
    provider: str  # LLM提供商（openai或anthropic）
    api_key: str  # API密钥
    base_url: str  # API基础URL
    model: str  # 模型名称
    temperature: float  # 温度参数
    max_tokens: int  # 最大token数


def _clean_str(value: object, default: str = "") -> str:
    """清理字符串：去除首尾空白和引号"""
    text = str(value or default)
    return text.strip().strip("'").strip('"')


def save_model_settings(payload: ModelSettingsIn) -> ModelSettingsSummary:
    """
    保存LLM模型设置到.env文件和Redis缓存
    
    Args:
        payload: 模型设置输入数据
        
    Returns:
        保存后的设置摘要
    """
    ENV_PATH.touch(exist_ok=True)
    key_name = "OPENAI_API_KEY" if payload.provider == "openai" else "ANTHROPIC_API_KEY"
    cleaned_api_key = payload.api_key.strip()
    cleaned_base_url = payload.base_url.strip()
    cleaned_model = payload.model.strip()
    
    # 写入.env文件
    set_key(str(ENV_PATH), key_name, cleaned_api_key)
    set_key(str(ENV_PATH), "LLM_PROVIDER", payload.provider.strip())
    set_key(str(ENV_PATH), "LLM_BASE_URL", cleaned_base_url)
    set_key(str(ENV_PATH), "LLM_MODEL", cleaned_model)
    set_key(str(ENV_PATH), "LLM_TEMPERATURE", str(payload.temperature))
    set_key(str(ENV_PATH), "LLM_MAX_TOKENS", str(payload.max_tokens))

    # 同时写入Redis缓存
    summary = ModelSettingsSummary(
        provider=payload.provider,
        base_url=cleaned_base_url,
        model=cleaned_model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        api_key_configured=True,
    )
    KVRepository().set_model_settings(summary.model_dump())
    return summary


def get_model_settings_summary() -> ModelSettingsSummary:
    """
    获取当前模型设置摘要（不包含API Key明文）
    
    用于前端显示和API密钥配置检查
    """
    values = dotenv_values(ENV_PATH)
    provider = _clean_str(values.get("LLM_PROVIDER"), "openai")
    api_key_name = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    api_key_configured = bool(_clean_str(values.get(api_key_name)))
    return ModelSettingsSummary(
        provider=provider,  # type: ignore[arg-type]
        base_url=_clean_str(values.get("LLM_BASE_URL"), "https://api.openai.com/v1"),
        model=_clean_str(values.get("LLM_MODEL"), "gpt-4o-mini"),
        temperature=float(values.get("LLM_TEMPERATURE") or 0.2),
        max_tokens=int(values.get("LLM_MAX_TOKENS") or 4096),
        api_key_configured=api_key_configured,
    )


def get_runtime_settings() -> RuntimeModelSettings:
    """
    获取运行时LLM设置（包含API Key）
    
    用于实际调用LLM API
    """
    values = dotenv_values(ENV_PATH)
    provider = _clean_str(values.get("LLM_PROVIDER"), "openai")
    api_key_name = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    api_key = _clean_str(values.get(api_key_name))
    return RuntimeModelSettings(
        provider=provider,
        api_key=api_key,
        base_url=_clean_str(values.get("LLM_BASE_URL"), "https://api.openai.com/v1"),
        model=_clean_str(values.get("LLM_MODEL"), "gpt-4o-mini"),
        temperature=float(values.get("LLM_TEMPERATURE") or 0.2),
        max_tokens=int(values.get("LLM_MAX_TOKENS") or 4096),
    )

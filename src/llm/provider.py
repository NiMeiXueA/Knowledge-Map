from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

import httpx

from src.llm.settings import get_runtime_settings

logger = logging.getLogger(__name__)


class LLMConfigurationError(RuntimeError):
    """LLM配置错误（如未配置API Key）"""
    pass


class LLMJSONParseError(RuntimeError):
    """LLM返回的JSON无法解析错误"""
    def __init__(
        self,
        *,
        trace_label: str,
        attempt: int,
        raw_response: str,
        original_error: Exception,
    ) -> None:
        self.trace_label = trace_label  # 追踪标签
        self.attempt = attempt  # 尝试次数
        self.raw_response = raw_response  # 原始响应
        self.original_error = original_error  # 原始错误
        snippet = self._build_snippet(raw_response)
        super().__init__(
            f"{trace_label} 返回了无法解析的 JSON（第 {attempt} 次尝试）：{original_error}。"
            f" 原始响应片段：{snippet}"
        )

    @staticmethod
    def _build_snippet(raw_response: str) -> str:
        """构建响应片段（用于错误信息）"""
        compact = re.sub(r"\s+", " ", (raw_response or "").strip())
        return compact[:400] if compact else "<empty>"


class UnifiedLLMProvider:
    """统一LLM提供商：支持OpenAI和Anthropic API"""
    
    def _parse_json_content(self, content: str) -> dict:
        """
        解析LLM返回的JSON内容
        
        尝试多种解析策略：
        1. 直接解析
        2. 提取```json```代码块
        3. 提取{...}对象
        4. 提取[...]数组
        """
        text = content.strip()
        if not text:
            raise ValueError("模型返回内容为空，无法解析 JSON。")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        fenced_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced_match:
            return json.loads(fenced_match.group(1))

        object_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
        if object_match:
            return json.loads(object_match.group(1))

        array_match = re.search(r"(\[.*\])", text, flags=re.DOTALL)
        if array_match:
            parsed = json.loads(array_match.group(1))
            return {"items": parsed}

        raise ValueError(f"模型返回的内容不是合法 JSON：{text[:300]}")

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        trace_label: str = "llm_json_call",
        max_retries: int = 1,
    ) -> dict:
        """
        调用LLM并返回JSON结果
        
        支持重试机制：如果JSON解析失败，会自动重试
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            trace_label: 追踪标签（用于日志）
            max_retries: 最大重试次数
            
        Returns:
            解析后的JSON字典
        """
        settings = get_runtime_settings()
        if not settings.api_key:
            raise LLMConfigurationError("未配置 API Key，请先在前端设置 API / 模型。")

        last_error: Exception | None = None
        raw_response = ""
        for attempt in range(1, max_retries + 2):
            current_system_prompt = self._build_retry_system_prompt(system_prompt, attempt)
            current_user_prompt = self._build_retry_user_prompt(user_prompt, attempt)
            raw_response = await self._request_text(
                provider=settings.provider,
                api_key=settings.api_key,
                base_url=settings.base_url,
                model=settings.model,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                system_prompt=current_system_prompt,
                user_prompt=current_user_prompt,
            )
            try:
                return self._parse_json_content(raw_response)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "%s JSON parse failed on attempt %s: %s | response=%s",
                    trace_label,
                    attempt,
                    exc,
                    LLMJSONParseError._build_snippet(raw_response),
                )
                if attempt > max_retries:
                    raise LLMJSONParseError(
                        trace_label=trace_label,
                        attempt=attempt,
                        raw_response=raw_response,
                        original_error=exc,
                    ) from exc
        raise RuntimeError(f"{trace_label} 调用失败：{last_error}")

    def _build_retry_system_prompt(self, system_prompt: str, attempt: int) -> str:
        """构建重试时的系统提示词"""
        if attempt == 1:
            return system_prompt
        return (
            f"{system_prompt}\n\n"
            "上一次返回无法解析。请这一次只返回一个合法 JSON 对象。"
            "不要输出解释、不要输出 Markdown 代码块、不要输出额外前后缀。"
        )

    def _build_retry_user_prompt(self, user_prompt: str, attempt: int) -> str:
        """构建重试时的用户提示词（截断过长内容）"""
        if attempt == 1:
            return user_prompt
        max_chars = max(2000, int(len(user_prompt) * 0.75))
        trimmed = user_prompt[:max_chars]
        return f"{trimmed}\n\n请重新输出合法 JSON。"

    async def _request_text(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """根据提供商类型调用相应的API"""
        if provider == "anthropic":
            return await self._anthropic_text(api_key, model, system_prompt, user_prompt, max_tokens)
        return await self._openai_text(
            api_key,
            base_url,
            model,
            temperature,
            max_tokens,
            system_prompt,
            user_prompt,
        )

    def _build_openai_chat_url(self, base_url: str) -> str:
        """构建OpenAI兼容API的聊天补全URL"""
        cleaned = base_url.strip().rstrip("/")
        parsed = urlparse(cleaned)
        path = parsed.path.rstrip("/")
        if path.endswith("/chat/completions"):
            return cleaned
        if path.endswith("/v1"):
            return f"{cleaned}/chat/completions"
        if path == "":
            return f"{cleaned}/v1/chat/completions"
        return f"{cleaned}/chat/completions"

    async def _openai_text(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """调用OpenAI兼容API"""
        url = self._build_openai_chat_url(base_url)
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def _anthropic_text(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str:
        """调用Anthropic Claude API"""
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            response.raise_for_status()
            parts = response.json()["content"]
            return "".join(part.get("text", "") for part in parts)

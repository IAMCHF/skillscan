"""
LLM API 客户端 — 通过 OpenAI 兼容接口调用大模型进行 TRACE 静态分析
支持自定义 API URL / Key / Model，默认从环境变量读取
"""
from __future__ import annotations
import os
import json
import time
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("skillscan.llm")

# ─── 配置（环境变量）────────────────────────────────────
# 注意：这些只作为 fallback，延迟读取由 LLMClient 构造函数处理

def _get_env(key: str, default: str) -> str:
    """延迟读取环境变量，确保 env_loader 已完成加载"""
    return os.getenv(key, default)

# ─── JSON 提取 ──────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")
_BARE_JSON_RE = re.compile(r"\{[\s\S]*\}")


def extract_json(text: str) -> str:
    """从 LLM 输出中提取 JSON 块"""
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _BARE_JSON_RE.search(text)
    if m:
        return m.group(0).strip()
    return text.strip()


# ─── LLM Client ─────────────────────────────────────────

@dataclass
class LLMResponse:
    success: bool
    content: str = ""
    parsed: dict | None = None
    error: str = ""
    tokens_used: int = 0
    model: str = ""
    latency_ms: int = 0


class LLMClient:
    """OpenAI 兼容 LLM 客户端"""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        # 延迟读取环境变量，确保 env_loader 已完成加载
        self.api_url = api_url or _get_env("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
        self.api_key = api_key or _get_env("LLM_API_KEY", "")
        self.model = model or _get_env("LLM_MODEL", "gpt-4o")
        self.timeout = timeout or int(_get_env("LLM_TIMEOUT", "120"))

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        expect_json: bool = True,
    ) -> LLMResponse:
        """发送聊天补全请求并解析响应"""
        if not self.api_key:
            return LLMResponse(success=False, error="LLM_API_KEY 未配置，请在环境变量中设置")

        # 延迟读取 max_tokens
        effective_max_tokens = max_tokens if max_tokens is not None else int(_get_env("LLM_MAX_TOKENS", "8192"))

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
        }

        t_start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.api_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)
            latency = int((time.perf_counter() - t_start) * 1000)

            result = LLMResponse(
                success=True,
                content=content,
                parsed=None,
                tokens_used=tokens,
                model=data.get("model", self.model),
                latency_ms=latency,
            )

            if expect_json:
                try:
                    json_str = extract_json(content)
                    result.parsed = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 解析失败: {e}, 原始内容前 500 字: {content[:500]}")
                    result.error = f"JSON 解析失败: {e}"
                    result.success = False

            return result

        except httpx.TimeoutException:
            return LLMResponse(success=False, error=f"LLM 请求超时 ({self.timeout}s)")
        except httpx.HTTPStatusError as e:
            # 显示完整错误信息，便于排查
            error_detail = e.response.text[:500] if e.response.text else "无响应体"
            return LLMResponse(success=False, error=f"LLM API 错误 {e.response.status_code}: {error_detail}")
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


# ─── 全局单例 ───────────────────────────────────────────

_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

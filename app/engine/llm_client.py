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

DEFAULT_API_URL = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
DEFAULT_API_KEY = os.getenv("LLM_API_KEY", "")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))

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
        api_url: str = DEFAULT_API_URL,
        api_key: str = DEFAULT_API_KEY,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        expect_json: bool = True,
    ) -> LLMResponse:
        """发送聊天补全请求并解析响应"""
        if not self.api_key:
            return LLMResponse(success=False, error="LLM_API_KEY 未配置，请在环境变量中设置")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
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
            return LLMResponse(success=False, error=f"LLM API 错误 {e.response.status_code}")
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


# ─── 全局单例 ───────────────────────────────────────────

_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

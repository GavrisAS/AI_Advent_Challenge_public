"""Low-level DeepSeek-compatible HTTP client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from ai_advent_agent.config import AgentConfig, DEFAULT_API_URL

Message = dict[str, str]


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek API request fails or returns malformed data."""


@dataclass(slots=True)
class ChatResult:
    """Normalized LLM response returned by LLMClient."""

    content: str
    finish_reason: str | None
    usage: dict[str, Any]
    elapsed_seconds: float
    model: str
    raw: dict[str, Any]
    has_reasoning_content: bool = False


class LLMClient:
    """HTTP client for chat completions.

    This class owns transport details: URL, headers, JSON serialization,
    HTTP errors and timeout. The agent owns conversation state and behavior.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_url: str = DEFAULT_API_URL,
        timeout_seconds: int = 120,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key не должен быть пустым")
        if not api_url.strip():
            raise ValueError("api_url не должен быть пустым")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds должен быть больше 0")

        self.api_key = api_key
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds

    def chat(self, messages: list[Message], config: AgentConfig) -> ChatResult:
        """Send chat messages to the configured LLM and return normalized result."""

        payload = self._build_payload(messages, config)
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        started_at = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise DeepSeekError(
                f"DeepSeek API вернул HTTP {error.code}: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            raise DeepSeekError(f"Не удалось подключиться к DeepSeek API: {error}") from error

        elapsed_seconds = time.perf_counter() - started_at
        return self._parse_response(response_body, config.model, elapsed_seconds)

    @staticmethod
    def _build_payload(messages: list[Message], config: AgentConfig) -> dict[str, Any]:
        config.validate()

        payload: dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            "stream": False,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "thinking": {"type": config.thinking_type},
        }

        if config.reasoning_effort:
            payload["reasoning_effort"] = config.reasoning_effort
        if config.stop:
            payload["stop"] = config.stop

        return payload

    @staticmethod
    def _parse_response(response_body: str, model: str, elapsed_seconds: float) -> ChatResult:
        try:
            data = json.loads(response_body)
            choice = data["choices"][0]
            message = choice["message"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise DeepSeekError(
                f"Не удалось разобрать ответ DeepSeek API: {response_body[:1000]}"
            ) from error

        return ChatResult(
            content=message.get("content", ""),
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage", {}) or {},
            elapsed_seconds=elapsed_seconds,
            model=model,
            raw=data,
            has_reasoning_content=bool(message.get("reasoning_content")),
        )

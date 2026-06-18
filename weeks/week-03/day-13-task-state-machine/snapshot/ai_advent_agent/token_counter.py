"""Approximate token counting utilities for the AI Advent Challenge training agent.

The exact tokenizer depends on the model/provider. This project intentionally keeps
zero external dependencies, so the local counter is an estimate. The API `usage`
field remains the source of truth when the provider returns it.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from ai_advent_agent.llm_client import Message

MESSAGE_OVERHEAD_TOKENS = 4
CHAT_OVERHEAD_TOKENS = 3


@dataclass(slots=True, frozen=True)
class TokenBreakdown:
    """Token estimate split by role categories."""

    total: int
    system: int
    user: int
    assistant: int
    tool: int
    message_count: int


class ApproxTokenCounter:
    """Fast dependency-free token estimator.

    Heuristic: approximately one token per four UTF-8 bytes plus a small
    chat-message overhead. This is not exact, but it is stable, cheap and works
    reasonably for mixed Russian/English/code text.
    """

    def count_text(self, text: str) -> int:
        if not text:
            return 0
        return max(1, ceil(len(text.encode("utf-8")) / 4))

    def count_message(self, message: Message) -> int:
        role = message.get("role", "")
        content = message.get("content", "")
        return MESSAGE_OVERHEAD_TOKENS + self.count_text(role) + self.count_text(content)

    def count_messages(self, messages: list[Message]) -> int:
        if not messages:
            return 0
        return CHAT_OVERHEAD_TOKENS + sum(self.count_message(message) for message in messages)

    def breakdown(self, messages: list[Message]) -> TokenBreakdown:
        buckets = {"system": 0, "user": 0, "assistant": 0, "tool": 0}
        for message in messages:
            role = message.get("role", "tool")
            if role not in buckets:
                role = "tool"
            buckets[role] += self.count_message(message)

        total = CHAT_OVERHEAD_TOKENS + sum(buckets.values()) if messages else 0
        return TokenBreakdown(
            total=total,
            system=buckets["system"],
            user=buckets["user"],
            assistant=buckets["assistant"],
            tool=buckets["tool"],
            message_count=len(messages),
        )


__all__ = ["ApproxTokenCounter", "TokenBreakdown"]

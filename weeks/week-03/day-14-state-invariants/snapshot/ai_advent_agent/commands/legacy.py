"""Legacy slash-command aliases kept for backwards compatibility."""

from __future__ import annotations

LEGACY_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("quit",), ("exit",)),
    (("context",), ("status", "context")),
    (("tokens",), ("status", "tokens")),
    (("last-report",), ("status", "report")),
    (("history",), ("status", "history")),
    (("history", "full"), ("status", "history", "full")),
    (("strategy",), ("config", "strategy")),
    (("summary-mode",), ("config", "summary")),
    (("context-mode",), ("config", "overflow")),
    (("reset",), ("session", "reset")),
    (("clear-context",), ("storage", "clear", "context")),
    (("summary",), ("memory", "summary")),
    (("facts",), ("memory", "facts")),
    (("remember", "short"), ("memory", "add", "short")),
    (("remember", "working"), ("memory", "set", "working")),
    (("remember", "long"), ("memory", "set", "long")),
    (("forget", "working"), ("memory", "forget", "working")),
    (("forget", "long"), ("memory", "forget", "long")),
    (("branches",), ("branch", "list")),
    (("checkpoint",), ("branch", "checkpoint")),
    (("switch",), ("branch", "switch")),
    (("analyze-file",), ("file", "analyze")),
    (("ask-file",), ("file", "ask")),
)

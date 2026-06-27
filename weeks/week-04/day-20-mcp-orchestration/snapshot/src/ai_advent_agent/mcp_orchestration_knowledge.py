"""Deterministic knowledge MCP server for Week 04 orchestration context."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from mcp.server.fastmcp import FastMCP
from pydantic import Field

McpDay = Literal["day-18", "day-19", "day-20"]
BestPracticeTopic = Literal["multi-server-orchestration", "model-agnostic-planning"]


class KnowledgePayload(TypedDict):
    id: str
    title: str
    summary: str
    key_points: list[str]


DAY_CONTEXTS: dict[str, KnowledgePayload] = {
    "day-18": {
        "id": "day-18",
        "title": "Scheduler-aware MCP tools",
        "summary": "Bounded periodic collection with SQLite snapshots and deterministic tools.",
        "key_points": [
            "Фоновый цикл ограничен max-runs и timeout.",
            "MCP tools отделены от scheduler service и persistence.",
            "Offline flow не требует внешней сети или API key.",
        ],
    },
    "day-19": {
        "id": "day-19",
        "title": "Composition tools внутри одного MCP server",
        "summary": "Planner выбирает search, report и save tools одного stdio server.",
        "key_points": [
            "Tool schemas обнаруживаются через tools/list.",
            "Report строится детерминированно без LLM внутри tool.",
            "Успех проверяется ordered subsequence, а не точным равенством sequence.",
        ],
    },
    "day-20": {
        "id": "day-20",
        "title": "Orchestration нескольких MCP servers",
        "summary": "Host маршрутизирует neutral JSON actions между несколькими MCP sessions.",
        "key_points": [
            "Каждый server имеет отдельную ответственность и stdio session.",
            "Normalized registry связывает tool с server и routing target.",
            "Финальные report/state сохраняются только через storage MCP server.",
        ],
    },
}

BEST_PRACTICES: dict[str, KnowledgePayload] = {
    "multi-server-orchestration": {
        "id": "multi-server-orchestration",
        "title": "Multi-server orchestration",
        "summary": "Discovery, validation and routing must be explicit and auditable.",
        "key_points": [
            "Использовать стабильные server ids и минимальные tool schemas.",
            "Валидировать принадлежность tool выбранному server до call_tool.",
            "Хранить trace и routing decisions без secrets и raw environment.",
        ],
    },
    "model-agnostic-planning": {
        "id": "model-agnostic-planning",
        "title": "Model-agnostic planning",
        "summary": "Planner emits ordinary JSON actions instead of provider-native tool calls.",
        "key_points": [
            "Контракт action не зависит от конкретного LLM API.",
            "Provider adapter отвечает только за text completion и usage.",
            "Invalid JSON/actions проходят bounded repair loop и повторную validation.",
        ],
    },
}


def build_knowledge_server() -> FastMCP:
    """Build the isolated deterministic knowledge server."""

    server = FastMCP("AI Advent Orchestration Knowledge")

    @server.tool(structured_output=True)
    def get_mcp_day_context(
        day: Annotated[McpDay, Field(description="Week 04 day id: day-18, day-19 or day-20.")],
    ) -> KnowledgePayload:
        """Return deterministic learning context for one Week 04 MCP day."""

        return DAY_CONTEXTS[day]

    @server.tool(structured_output=True)
    def get_best_practice_note(
        topic: Annotated[
            BestPracticeTopic,
            Field(
                description=(
                    "Practice topic: multi-server-orchestration or model-agnostic-planning."
                )
            ),
        ],
    ) -> KnowledgePayload:
        """Return a deterministic best-practice note for orchestration planning."""

        return BEST_PRACTICES[topic]

    return server


mcp = build_knowledge_server()

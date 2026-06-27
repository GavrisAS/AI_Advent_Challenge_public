"""Provider-neutral JSON action planners for Day 20 orchestration."""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from ai_advent_agent.config import DEFAULT_API_URL, DEFAULT_MODEL
from ai_advent_agent.env import load_env_file

Message = dict[str, str]

PlannerMode = Literal["llm-json", "scripted"]


class PlannerError(RuntimeError):
    """Raised when a planner response cannot be produced or validated."""


@dataclass(frozen=True, slots=True)
class PlannerAction:
    """Validated provider-neutral action emitted by a planner."""

    action: Literal["call_tool", "final_response"]
    server: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    reason: str | None = None
    answer: str | None = None


@dataclass(frozen=True, slots=True)
class PlannerTurn:
    """Raw text and normalized usage returned by one planner call."""

    content: str
    usage: dict[str, Any]


class JsonActionPlanner(Protocol):
    mode: PlannerMode
    model: str

    async def next_action(
        self,
        *,
        goal: str,
        tools_registry: list[dict[str, Any]],
        flow_state: dict[str, Any],
        history: list[dict[str, Any]],
        validation_errors: list[str],
    ) -> PlannerTurn:
        """Return one JSON action as plain assistant text."""


class ScriptedJsonPlanner:
    """Deterministic offline planner exercising the same JSON contract and router."""

    mode: PlannerMode = "scripted"
    model = "scripted-deterministic"

    async def next_action(
        self,
        *,
        goal: str,
        tools_registry: list[dict[str, Any]],
        flow_state: dict[str, Any],
        history: list[dict[str, Any]],
        validation_errors: list[str],
    ) -> PlannerTurn:
        del goal, history, validation_errors
        tracker = cast(dict[str, Any], flow_state.get("tracker", {}))
        knowledge = cast(dict[str, Any], flow_state.get("knowledge", {}))
        report = cast(dict[str, Any], flow_state.get("report", {}))
        storage = cast(dict[str, Any], flow_state.get("storage", {}))

        action: dict[str, Any]
        if "search_done" not in tracker:
            action = _call(
                "tracker",
                "search_tracker_issues",
                {"status": "done", "tag": "mcp", "limit": 10},
            )
        elif "search_planned" not in tracker:
            action = _call(
                "tracker",
                "search_tracker_issues",
                {"status": "planned", "tag": "mcp", "limit": 10},
            )
        elif "day-18" not in knowledge:
            action = _call("knowledge", "get_mcp_day_context", {"day": "day-18"})
        elif "day-19" not in knowledge:
            action = _call("knowledge", "get_mcp_day_context", {"day": "day-19"})
        elif "day-20" not in knowledge:
            action = _call("knowledge", "get_mcp_day_context", {"day": "day-20"})
        elif "multi-server-orchestration" not in knowledge:
            action = _call(
                "knowledge",
                "get_best_practice_note",
                {"topic": "multi-server-orchestration"},
            )
        elif "model-agnostic-planning" not in knowledge:
            action = _call(
                "knowledge",
                "get_best_practice_note",
                {"topic": "model-agnostic-planning"},
            )
        elif "orchestration_report" not in report:
            action = _call(
                "report",
                "build_orchestration_report",
                {
                    "tracker_data": tracker,
                    "knowledge_context": knowledge,
                    "flow_summary": {
                        "registered_servers": sorted(
                            {str(item["server_id"]) for item in tools_registry}
                        ),
                        "data_source_servers_used_before_report": flow_state.get(
                            "servers_used", []
                        ),
                        "report_server": "report",
                        "storage_server": "storage",
                        "flow_stage": "report_generation",
                        "tool_calls_total_before_report": flow_state.get("tool_calls_total", 0),
                    },
                    "report_title": "Week 04 MCP orchestration report",
                },
            )
        elif "next_steps" not in report:
            action = _call(
                "report",
                "build_next_steps",
                {
                    "tracker_data": tracker,
                    "knowledge_context": knowledge,
                    "report_summary": report_summary_for_planner(report["orchestration_report"]),
                },
            )
        elif "final-orchestration-report.md" not in storage:
            action = _call(
                "storage",
                "save_markdown_file",
                {
                    "filename": "final-orchestration-report.md",
                    "content": report["orchestration_report"]["markdown"],
                },
            )
        elif "saved-flow-state.json" not in storage:
            action = _call(
                "storage",
                "save_json_file",
                {
                    "filename": "saved-flow-state.json",
                    "data": project_saved_state_for_storage(flow_state),
                },
            )
        else:
            action = {
                "action": "final_response",
                "answer": (
                    "Готово: использованы 4 MCP-сервера, выполнен длинный flow, "
                    "отчёт и JSON state сохранены через storage server."
                ),
            }
        return PlannerTurn(content=json.dumps(action, ensure_ascii=False), usage={})


class DeepSeekCompatibleJsonPlanner:
    """Text-completion adapter that requests ordinary JSON, never native tool calls."""

    mode: PlannerMode = "llm-json"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        api_url: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DEEPSEEK_API_KEY не должен быть пустым")
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    async def next_action(
        self,
        *,
        goal: str,
        tools_registry: list[dict[str, Any]],
        flow_state: dict[str, Any],
        history: list[dict[str, Any]],
        validation_errors: list[str],
    ) -> PlannerTurn:
        messages = build_planner_messages(
            goal=goal,
            tools_registry=tools_registry,
            flow_state=flow_state,
            history=history,
            validation_errors=validation_errors,
        )
        return await asyncio.to_thread(self._request, messages)

    def _request(self, messages: list[Message]) -> PlannerTurn:
        payload = self._build_payload(messages)
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise PlannerError(f"Planner API вернул HTTP {error.code}: {body[:500]}") from error
        except urllib.error.URLError as error:
            raise PlannerError(f"Не удалось подключиться к planner API: {error}") from error
        elapsed = time.perf_counter() - started
        try:
            data = json.loads(response_body)
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise PlannerError(f"Malformed planner API response: {response_body[:500]}") from error
        if not isinstance(content, str) or not content.strip():
            raise PlannerError("Planner API returned empty JSON content")
        usage = dict(data.get("usage") or {})
        usage.update({"elapsed_seconds": elapsed, "model": self.model})
        return PlannerTurn(content=content, usage=usage)

    def _build_payload(self, messages: list[Message]) -> dict[str, Any]:
        """Build an ordinary JSON-completion request without native function calling."""

        return {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }


def build_llm_json_planner_from_env(
    *,
    model: str | None,
    api_url: str | None,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> DeepSeekCompatibleJsonPlanner:
    """Create the online planner explicitly; never fall back to scripted mode."""

    load_env_file()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise PlannerError(
            "DEEPSEEK_API_KEY не найден. Для --planner llm-json задайте ключ; "
            "автоматический fallback на scripted запрещён."
        )
    return DeepSeekCompatibleJsonPlanner(
        api_key=api_key,
        model=model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
        api_url=api_url or os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )


def parse_planner_action(content: str, tools_registry: list[dict[str, Any]]) -> PlannerAction:
    """Parse and validate a neutral JSON action against discovered tools."""

    candidate = _strip_json_fence(content)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise PlannerError(f"Planner response is not valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise PlannerError("Planner action must be a JSON object")

    action = payload.get("action")
    if action == "final_response":
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise PlannerError("final_response.answer must be a non-empty string")
        return PlannerAction(action="final_response", answer=answer.strip())
    if action != "call_tool":
        raise PlannerError("action must be call_tool or final_response")

    server = payload.get("server")
    tool = payload.get("tool")
    arguments = payload.get("arguments")
    reason = payload.get("reason")
    if not isinstance(server, str) or not server:
        raise PlannerError("call_tool.server must be a non-empty string")
    if not isinstance(tool, str) or not tool:
        raise PlannerError("call_tool.tool must be a non-empty string")
    if not isinstance(arguments, dict):
        raise PlannerError("call_tool.arguments must be a JSON object")
    servers = {entry["server_id"] for entry in tools_registry}
    if server not in servers:
        raise PlannerError(f"Unknown server: {server}")
    matching = [
        entry for entry in tools_registry if entry["server_id"] == server and entry["name"] == tool
    ]
    if not matching:
        owners = sorted(entry["server_id"] for entry in tools_registry if entry["name"] == tool)
        if owners:
            raise PlannerError(f"Tool {tool} belongs to {owners}, not {server}")
        raise PlannerError(f"Unknown tool {tool} on server {server}")
    return PlannerAction(
        action="call_tool",
        server=server,
        tool=tool,
        arguments=cast(dict[str, Any], arguments),
        reason=reason if isinstance(reason, str) else None,
    )


def build_planner_messages(
    *,
    goal: str,
    tools_registry: list[dict[str, Any]],
    flow_state: dict[str, Any],
    history: list[dict[str, Any]],
    validation_errors: list[str],
) -> list[Message]:
    """Build the portable text prompt containing registry, state and JSON contract."""

    system = """Ты model-agnostic planner для нескольких MCP servers. Верни ровно один JSON object.
Не используй provider-native function-calling protocol. Доступны только два action contracts:
{"action":"call_tool","server":"...","tool":"...","arguments":{},"reason":"..."}
{"action":"final_response","answer":"..."}
Выбирай только server/tool из normalized registry и передавай JSON object в arguments.
Сначала собери done/planned Tracker data, затем Day 18/19/20 context и ОБЕ practice notes:
multi-server-orchestration и model-agnostic-planning,
после этого вызови report builder, next steps, storage markdown и storage JSON. Не завершай flow,
пока final-orchestration-report.md и saved-flow-state.json не сохранены storage server.
Используй compact flow_state.available_state_references для крупных arguments: tracker_data,
knowledge_context, report_summary, final_report_markdown и saved_flow_state. Передай соответствующий
JSON reference object как значение argument; host разрешит ссылку из полного internal state перед
MCP call. Не копируй эти крупные значения в action. Например:
tracker_data={"$state":"tracker"}, knowledge_context={"$state":"knowledge"},
report_summary={"$projection":"report_summary"},
content={"$state":"report.orchestration_report.markdown"},
data={"$projection":"saved_flow_state"}.
Разрешены дополнительные/retry calls, но соблюдай причинный порядок. JSON state для save_json_file
должен содержать tracker, knowledge, report_summary, saved_files, counts_by_server, counts_by_tool,
servers_used и final_success_flags. Для build_orchestration_report.flow_summary передай:
registered_servers из registry, data_source_servers_used_before_report из текущего state,
report_server=`report`, storage_server=`storage`, flow_stage=`report_generation` и
tool_calls_total_before_report. Используй обычный JSON action; provider-native function-calling
protocol не является частью orchestration contract. Ответ должен быть валидным JSON."""
    state_payload = {
        "goal": goal,
        "normalized_tools_registry": tools_registry,
        "flow_state": compact_flow_state_for_planner(flow_state),
        "recent_history": history[-8:],
        "validation_errors": validation_errors[-3:],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(state_payload, ensure_ascii=False)},
    ]


def compact_flow_state_for_planner(flow_state: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact planner-facing state without mutating the full internal state."""

    tracker = _compact_tracker(flow_state.get("tracker"))
    knowledge = _compact_knowledge(flow_state.get("knowledge"))
    report = _compact_report(flow_state.get("report"))
    storage = _compact_storage(flow_state.get("storage"))
    compact: dict[str, Any] = {
        "tracker": tracker,
        "knowledge": knowledge,
        "report": report,
        "storage": storage,
        "counts_by_server": _compact_json_value(flow_state.get("counts_by_server", {})),
        "counts_by_tool": _compact_json_value(flow_state.get("counts_by_tool", {})),
        "servers_used": _compact_json_value(flow_state.get("servers_used", [])),
        "tool_calls_total": flow_state.get("tool_calls_total", 0),
        "completed_steps": _compact_completed_steps(flow_state.get("completed_steps")),
        "final_success_flags": _compact_json_value(flow_state.get("final_success_flags", {})),
        "validation_errors": _compact_json_value(flow_state.get("validation_errors", [])),
        "report_built": "orchestration_report" in report,
        "storage_completed": {
            "markdown": "final-orchestration-report.md" in storage,
            "json": "saved-flow-state.json" in storage,
        },
    }
    references: dict[str, dict[str, str]] = {
        "tracker_data": {"$state": "tracker"},
        "knowledge_context": {"$state": "knowledge"},
    }
    if "orchestration_report" in report:
        references.update(
            {
                "final_report_markdown": {"$state": "report.orchestration_report.markdown"},
                "report_summary": {"$projection": "report_summary"},
                "saved_flow_state": {"$projection": "saved_flow_state"},
            }
        )
    compact["available_state_references"] = references
    return cast(dict[str, Any], _compact_json_value(compact))


def compact_text(value: str, *, limit: int = 500) -> str:
    """Return text capped to the requested total length with a truncation marker."""

    if limit < 1:
        raise ValueError("limit must be positive")
    if len(value) <= limit:
        return value
    marker = "…[truncated]"
    if limit <= len(marker):
        return value[:limit]
    return value[: limit - len(marker)] + marker


def _compact_tracker(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, payload in value.items():
        if not isinstance(payload, Mapping):
            result[str(key)] = _compact_json_value(payload)
            continue
        issues = []
        raw_issues = payload.get("issues", [])
        if isinstance(raw_issues, list):
            for issue in raw_issues:
                if not isinstance(issue, Mapping):
                    continue
                issues.append(
                    {
                        field: compact_text(str(issue[field]), limit=240)
                        for field in (
                            "issue_key",
                            "title",
                            "status",
                            "priority",
                            "summary",
                        )
                        if field in issue
                    }
                )
        result[str(key)] = {
            "query": _compact_json_value(payload.get("query", {})),
            "issue_count": payload.get("issue_count", len(issues)),
            "issues": issues,
        }
    return result


def _compact_knowledge(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, payload in value.items():
        if not isinstance(payload, Mapping):
            result[str(key)] = _compact_json_value(payload)
            continue
        result[str(key)] = {
            field: compact_text(str(payload[field]), limit=300)
            for field in ("id", "title", "summary")
            if field in payload
        }
    return result


def _compact_report(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, payload in value.items():
        if not isinstance(payload, Mapping):
            result[str(key)] = _compact_json_value(payload)
            continue
        item = {
            str(field): _compact_json_value(field_value)
            for field, field_value in payload.items()
            if field != "markdown"
        }
        markdown = payload.get("markdown")
        if isinstance(markdown, str):
            item["markdown_chars"] = len(markdown)
            item["markdown_preview"] = compact_text(markdown, limit=400)
        result[str(key)] = item
    return result


def _compact_storage(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = {"saved", "path", "bytes_written", "sha256"}
    return {
        str(key): {
            str(field): _compact_json_value(field_value)
            for field, field_value in payload.items()
            if field in allowed
        }
        for key, payload in value.items()
        if isinstance(payload, Mapping)
    }


def _compact_completed_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                field: _compact_json_value(item[field])
                for field in ("step", "server", "tool", "success", "error")
                if field in item
            }
        )
    return result


def _compact_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return compact_text(value)
    if isinstance(value, Mapping):
        return {str(key): _compact_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_compact_json_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return compact_text(str(value))


def _call(server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "call_tool",
        "server": server,
        "tool": tool,
        "arguments": arguments,
        "reason": f"Continue the goal with {server}.{tool}.",
    }


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def report_summary_for_planner(value: Any) -> dict[str, Any]:
    """Return report metadata without the full Markdown body."""

    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if key != "markdown"}


def project_saved_state_for_storage(flow_state: dict[str, Any]) -> dict[str, Any]:
    """Build the complete JSON object persisted through the Storage MCP server."""

    return {
        "tracker": flow_state.get("tracker", {}),
        "knowledge": flow_state.get("knowledge", {}),
        "report_summary": {
            "orchestration_report": report_summary_for_planner(
                cast(dict[str, Any], flow_state.get("report", {})).get("orchestration_report", {})
            ),
            "next_steps": cast(dict[str, Any], flow_state.get("report", {})).get("next_steps", {}),
        },
        "saved_files": flow_state.get("storage", {}),
        "counts_by_server": flow_state.get("counts_by_server", {}),
        "counts_by_tool": flow_state.get("counts_by_tool", {}),
        "servers_used": flow_state.get("servers_used", []),
        "tool_calls_total_before_json_save": flow_state.get("tool_calls_total", 0),
        "final_success_flags": {
            "all_servers_used": True,
            "minimum_tool_calls_reached": True,
            "required_chain_found": True,
            "final_report_saved_via_storage": True,
            "flow_state_saved_via_storage": True,
        },
    }

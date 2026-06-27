"""Multi-session MCP discovery, validation, routing and evidence for Day 20."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from anyio import fail_after
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent, Tool

from ai_advent_agent.mcp_orchestration_planner import (
    JsonActionPlanner,
    PlannerAction,
    PlannerError,
    parse_planner_action,
    project_saved_state_for_storage,
    report_summary_for_planner,
)
from ai_advent_agent.mcp_orchestration_servers import SERVER_BUILDERS
from ai_advent_agent.mcp_orchestration_storage import ORCHESTRATION_OUTPUT_DIR_ENV

DEFAULT_MCP_ORCHESTRATION_TIMEOUT_SECONDS = 360.0
DEFAULT_MCP_ORCHESTRATION_MAX_STEPS = 15
DEFAULT_MCP_ORCHESTRATION_GOAL = (
    "Собери большой итоговый отчёт по MCP Week 04: найди выполненные и планируемые MCP-задачи, "
    "получи контекст Day 18, Day 19 и Day 20, добавь best practices по multi-server "
    "orchestration и model-agnostic planning, собери отчёт и сохрани Markdown и JSON состояние "
    "через storage MCP server."
)
SERVER_IDS = tuple(SERVER_BUILDERS)
REQUIRED_KNOWLEDGE_IDS = {
    "day-18",
    "day-19",
    "day-20",
    "multi-server-orchestration",
    "model-agnostic-planning",
}
REQUIRED_SAVED_STATE_KEYS = {
    "tracker",
    "knowledge",
    "report_summary",
    "saved_files",
    "counts_by_server",
    "counts_by_tool",
    "servers_used",
    "final_success_flags",
}


class McpOrchestrationError(RuntimeError):
    """Raised when the multi-server flow cannot complete safely."""


@dataclass(slots=True)
class OrchestrationResult:
    planner: str
    model: str
    goal: str
    server_registry: list[dict[str, Any]]
    tools_registry: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    routing_decisions: list[dict[str, Any]]
    flow_state: dict[str, Any]
    final_answer: str
    usage: dict[str, Any]
    completed: bool
    required_chain_found: bool

    def trace_dict(self) -> dict[str, Any]:
        servers_used = self.flow_state.get("servers_used", [])
        return {
            "planner": self.planner,
            "model": self.model,
            "model_specific_tool_calling": False,
            "hardcoded_pipeline": False,
            "servers_registered": [item["server_id"] for item in self.server_registry],
            "servers_used": servers_used,
            "tool_calls_total": len(self.steps),
            "required_chain_found": self.required_chain_found,
            "completed": self.completed,
            "steps": self.steps,
            "usage": self.usage,
            "generated_at": utc_timestamp(),
        }


async def run_orchestration_via_mcp(
    *,
    planner: JsonActionPlanner,
    output_dir: Path,
    goal: str = DEFAULT_MCP_ORCHESTRATION_GOAL,
    timeout_seconds: float = DEFAULT_MCP_ORCHESTRATION_TIMEOUT_SECONDS,
    max_steps: int = DEFAULT_MCP_ORCHESTRATION_MAX_STEPS,
) -> OrchestrationResult:
    """Discover four servers and execute planner-selected actions through a generic router."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")

    server_registry: list[dict[str, Any]] = []
    tools_registry: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    routing_decisions: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    usage = empty_usage()
    flow_state = initial_flow_state()
    final_answer = ""

    try:
        with fail_after(timeout_seconds):
            async with AsyncExitStack() as stack:
                sessions: dict[str, ClientSession] = {}
                for server_id in SERVER_IDS:
                    parameters = StdioServerParameters(
                        command=sys.executable,
                        args=["-m", "ai_advent_agent.mcp_orchestration_servers", server_id],
                        env=server_environment(output_dir),
                    )
                    read_stream, write_stream = await stack.enter_async_context(
                        stdio_client(parameters)
                    )
                    session = await stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )
                    initialization = await session.initialize()
                    sessions[server_id] = session
                    tools_result = await session.list_tools()
                    normalized = [normalize_tool(server_id, tool) for tool in tools_result.tools]
                    tools_registry.extend(normalized)
                    server_registry.append(
                        {
                            "server_id": server_id,
                            "transport": "stdio",
                            "command": "python",
                            "module": "ai_advent_agent.mcp_orchestration_servers",
                            "module_argument": server_id,
                            "status": "initialized",
                            "protocol_version": str(initialization.protocolVersion),
                            "server_name": initialization.serverInfo.name,
                            "server_version": initialization.serverInfo.version,
                            "tool_count": len(normalized),
                        }
                    )

                validate_discovered_registry(server_registry, tools_registry)
                tools_registry.sort(key=lambda item: (item["server_id"], item["name"]))

                for planner_turn in range(1, max_steps + 1):
                    try:
                        turn = await planner.next_action(
                            goal=goal,
                            tools_registry=tools_registry,
                            flow_state=flow_state,
                            history=history,
                            validation_errors=validation_errors,
                        )
                    except PlannerError as error:
                        message = f"Planner turn {planner_turn}: {error}"
                        validation_errors.append(message)
                        history.append({"planner_error": message})
                        continue
                    merge_usage(usage, turn.usage, planner.mode)
                    try:
                        action = parse_planner_action(turn.content, tools_registry)
                        action = resolve_action_state_references(action, flow_state)
                        validate_action_preconditions(action, flow_state, steps)
                    except PlannerError as error:
                        message = f"Planner turn {planner_turn}: {error}"
                        validation_errors.append(message)
                        history.append({"planner_error": message})
                        continue
                    if action.action == "final_response":
                        final_answer = action.answer or ""
                        break
                    await execute_routed_action(
                        action=action,
                        chosen_by="llm" if planner.mode == "llm-json" else "scripted",
                        sessions=sessions,
                        flow_state=flow_state,
                        history=history,
                        steps=steps,
                        routing_decisions=routing_decisions,
                    )
                else:
                    validation_errors.append(f"Planner exceeded max_steps={max_steps}")
    except TimeoutError as error:
        raise McpOrchestrationError(
            f"MCP orchestration timed out after {timeout_seconds:g} seconds"
        ) from error

    required_chain_found = has_required_ordered_chain(steps)
    completed = evaluate_completion(
        steps=steps,
        flow_state=flow_state,
        final_answer=final_answer,
        required_chain_found=required_chain_found,
    )
    flow_state["final_success_flags"] = {
        "all_servers_used": set(flow_state["servers_used"]) == set(SERVER_IDS),
        "minimum_tool_calls_reached": len(steps) >= 8,
        "required_chain_found": required_chain_found,
        "final_report_saved_via_storage": _storage_saved(
            flow_state, "final-orchestration-report.md"
        ),
        "flow_state_saved_via_storage": _storage_saved(flow_state, "saved-flow-state.json"),
        "completed": completed,
    }
    flow_state["validation_errors"] = validation_errors
    return OrchestrationResult(
        planner=planner.mode,
        model=planner.model,
        goal=goal,
        server_registry=server_registry,
        tools_registry=tools_registry,
        steps=steps,
        routing_decisions=routing_decisions,
        flow_state=flow_state,
        final_answer=final_answer,
        usage=usage,
        completed=completed,
        required_chain_found=required_chain_found,
    )


async def execute_routed_action(
    *,
    action: PlannerAction,
    chosen_by: str,
    sessions: dict[str, ClientSession],
    flow_state: dict[str, Any],
    history: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    routing_decisions: list[dict[str, Any]],
) -> None:
    """Resolve the session generically, call the tool and propagate its structured result."""

    assert action.server is not None
    assert action.tool is not None
    assert action.arguments is not None
    step = len(steps) + 1
    session = sessions[action.server]
    routing_decisions.append(
        {
            "step": step,
            "requested_server": action.server,
            "requested_tool": action.tool,
            "resolved_session": action.server,
            "valid": True,
        }
    )
    call_result = await session.call_tool(action.tool, action.arguments)
    if call_result.isError:
        raise McpOrchestrationError(
            f"MCP tool failed: {action.server}.{action.tool}: {extract_error_text(call_result)}"
        )
    payload = extract_tool_payload(call_result, action.tool)
    record_flow_result(flow_state, action.server, action.tool, payload)
    result_summary = summarize_result(action.server, action.tool, payload)
    step_entry = {
        "step": step,
        "chosen_by": chosen_by,
        "server": action.server,
        "tool": action.tool,
        "arguments": sanitize_arguments(action.arguments),
        "reason": action.reason,
        "routed_to_session": action.server,
        "result_summary": result_summary,
    }
    steps.append(step_entry)
    history.append(
        {
            "action": {
                "server": action.server,
                "tool": action.tool,
                "arguments": sanitize_arguments(action.arguments),
            },
            "result": result_summary,
        }
    )


def normalize_tool(server_id: str, tool: Tool) -> dict[str, Any]:
    """Normalize an MCP Tool into the provider-independent routing registry."""

    is_write = server_id == "storage"
    return {
        "server_id": server_id,
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": json_compatible(tool.inputSchema),
        "read_only": not is_write,
        "write": is_write,
        "destructive": False,
        "routing_target": server_id,
    }


def validate_discovered_registry(
    server_registry: list[dict[str, Any]], tools_registry: list[dict[str, Any]]
) -> None:
    server_ids = {entry["server_id"] for entry in server_registry}
    if server_ids != set(SERVER_IDS):
        raise McpOrchestrationError(f"Unexpected server registry: {sorted(server_ids)}")
    expected = {
        "tracker": {"search_tracker_issues", "get_tracker_issue"},
        "knowledge": {"get_mcp_day_context", "get_best_practice_note"},
        "report": {"build_orchestration_report", "build_next_steps"},
        "storage": {"save_markdown_file", "save_json_file"},
    }
    actual = {
        server_id: {item["name"] for item in tools_registry if item["server_id"] == server_id}
        for server_id in SERVER_IDS
    }
    if actual != expected:
        raise McpOrchestrationError(f"Unexpected tools registry: {actual}")


def resolve_action_state_references(
    action: PlannerAction, flow_state: dict[str, Any]
) -> PlannerAction:
    """Resolve neutral planner references against the full internal flow state."""

    if action.arguments is None:
        return action
    resolved = _resolve_state_value(action.arguments, flow_state)
    if not isinstance(resolved, dict):
        raise PlannerError("Resolved call_tool.arguments must remain a JSON object")
    return replace(action, arguments=resolved)


def _resolve_state_value(value: Any, flow_state: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$state"}:
            path = value["$state"]
            if not isinstance(path, str) or not path:
                raise PlannerError("$state reference must be a non-empty dotted path")
            return _lookup_state_path(flow_state, path)
        if set(value) == {"$projection"}:
            projection = value["$projection"]
            if projection == "saved_flow_state":
                return project_saved_state_for_storage(flow_state)
            if projection == "report_summary":
                report = flow_state.get("report", {}).get("orchestration_report", {})
                return report_summary_for_planner(report)
            raise PlannerError(f"Unknown $projection reference: {projection}")
        return {key: _resolve_state_value(item, flow_state) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_state_value(item, flow_state) for item in value]
    return value


def _lookup_state_path(flow_state: dict[str, Any], path: str) -> Any:
    current: Any = flow_state
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise PlannerError(f"Unknown $state reference: {path}")
        current = current[part]
    return current


def validate_action_preconditions(
    action: PlannerAction, flow_state: dict[str, Any], steps: list[dict[str, Any]]
) -> None:
    """Reject premature phase transitions without choosing the next tool for the planner."""

    tracker = flow_state["tracker"]
    knowledge = flow_state["knowledge"]
    report = flow_state["report"]
    storage = flow_state["storage"]
    gather_missing = []
    if not {"search_done", "search_planned"}.issubset(tracker):
        gather_missing.append("tracker searches for done and planned")
    missing_knowledge = sorted(REQUIRED_KNOWLEDGE_IDS - set(knowledge))
    if missing_knowledge:
        gather_missing.append("knowledge ids: " + ", ".join(missing_knowledge))

    if action.action == "final_response":
        final_missing = list(gather_missing)
        if "orchestration_report" not in report:
            final_missing.append("orchestration report")
        if "next_steps" not in report:
            final_missing.append("next steps")
        if not {"final-orchestration-report.md", "saved-flow-state.json"}.issubset(storage):
            final_missing.append("both storage files")
        if len(steps) < 8 or not has_required_ordered_chain(steps):
            final_missing.append("minimum ordered tool chain")
        if final_missing:
            raise PlannerError("final_response is premature; missing " + "; ".join(final_missing))
        return

    assert action.tool is not None
    assert action.arguments is not None
    if action.tool == "build_orchestration_report":
        if gather_missing:
            raise PlannerError("report is premature; missing " + "; ".join(gather_missing))
        tracker_argument = action.arguments.get("tracker_data")
        knowledge_argument = action.arguments.get("knowledge_context")
        if not isinstance(tracker_argument, dict) or not {
            "search_done",
            "search_planned",
        }.issubset(tracker_argument):
            raise PlannerError("report.tracker_data must include done and planned searches")
        if not isinstance(knowledge_argument, dict) or not REQUIRED_KNOWLEDGE_IDS.issubset(
            knowledge_argument
        ):
            raise PlannerError("report.knowledge_context must include all required knowledge ids")
        flow_summary = action.arguments.get("flow_summary")
        if not isinstance(flow_summary, dict):
            raise PlannerError("report.flow_summary must be a JSON object")
        registered_servers = flow_summary.get("registered_servers")
        if not isinstance(registered_servers, list) or set(registered_servers) != set(SERVER_IDS):
            raise PlannerError("report.flow_summary must include all registered servers")
        data_source_servers = flow_summary.get("data_source_servers_used_before_report")
        if not isinstance(data_source_servers, list) or set(data_source_servers) != {
            "tracker",
            "knowledge",
        }:
            raise PlannerError("report.flow_summary must identify tracker and knowledge sources")
        expected_topology = {
            "report_server": "report",
            "storage_server": "storage",
            "flow_stage": "report_generation",
        }
        if any(flow_summary.get(key) != value for key, value in expected_topology.items()):
            raise PlannerError("report.flow_summary contains invalid topology metadata")
        if flow_summary.get("tool_calls_total_before_report") != len(steps):
            raise PlannerError("report.flow_summary contains an invalid pre-report call count")
    elif action.tool == "build_next_steps" and "orchestration_report" not in report:
        raise PlannerError("build_next_steps requires orchestration_report first")
    elif action.tool == "save_markdown_file":
        report_payload = report.get("orchestration_report", {})
        if "next_steps" not in report or action.arguments.get("content") != report_payload.get(
            "markdown"
        ):
            raise PlannerError("save_markdown_file requires next_steps and exact report markdown")
    elif action.tool == "save_json_file":
        if "final-orchestration-report.md" not in storage:
            raise PlannerError("save_json_file requires final Markdown saved first")
        data = action.arguments.get("data")
        if not isinstance(data, dict) or not REQUIRED_SAVED_STATE_KEYS.issubset(data):
            raise PlannerError(
                "save_json_file.data must include: " + ", ".join(sorted(REQUIRED_SAVED_STATE_KEYS))
            )


def record_flow_result(
    flow_state: dict[str, Any], server_id: str, tool_name: str, payload: dict[str, Any]
) -> None:
    """Accumulate results without determining which tool should be called next."""

    if server_id == "tracker":
        if tool_name == "search_tracker_issues":
            query = payload.get("query", {})
            status = query.get("status") if isinstance(query, dict) else "all"
            key = f"search_{status or 'all'}"
        else:
            key = str(payload.get("issue_key", tool_name))
        flow_state["tracker"][key] = payload
    elif server_id == "knowledge":
        flow_state["knowledge"][str(payload.get("id", tool_name))] = payload
    elif server_id == "report":
        key = "orchestration_report" if tool_name == "build_orchestration_report" else "next_steps"
        flow_state["report"][key] = payload
    elif server_id == "storage":
        flow_state["storage"][str(payload.get("path", tool_name))] = payload

    flow_state["tool_calls_total"] += 1
    flow_state["counts_by_server"][server_id] = flow_state["counts_by_server"].get(server_id, 0) + 1
    qualified_name = f"{server_id}.{tool_name}"
    flow_state["counts_by_tool"][qualified_name] = (
        flow_state["counts_by_tool"].get(qualified_name, 0) + 1
    )
    if server_id not in flow_state["servers_used"]:
        flow_state["servers_used"].append(server_id)
    flow_state["completed_steps"].append(
        {
            "step": flow_state["tool_calls_total"],
            "server": server_id,
            "tool": tool_name,
            "success": True,
        }
    )


def has_required_ordered_chain(steps: list[dict[str, Any]]) -> bool:
    """Accept retries/extras while requiring causal phase order."""

    phases: list[str] = []
    for step in steps:
        server = step["server"]
        tool = step["tool"]
        if server == "tracker":
            phases.append("tracker")
        elif server == "knowledge":
            phases.append("knowledge")
        elif (server, tool) == ("report", "build_orchestration_report"):
            phases.append("report")
        elif (server, tool) == ("report", "build_next_steps"):
            phases.append("next_steps")
        elif (server, tool) == ("storage", "save_markdown_file"):
            phases.append("save_markdown")
        elif (server, tool) == ("storage", "save_json_file"):
            phases.append("save_json")
    return ordered_subsequence(
        phases,
        ("tracker", "knowledge", "report", "next_steps", "save_markdown", "save_json"),
    )


def ordered_subsequence(sequence: list[str], required: tuple[str, ...]) -> bool:
    start = 0
    for item in required:
        try:
            start = sequence.index(item, start) + 1
        except ValueError:
            return False
    return True


def evaluate_completion(
    *,
    steps: list[dict[str, Any]],
    flow_state: dict[str, Any],
    final_answer: str,
    required_chain_found: bool,
) -> bool:
    return all(
        (
            bool(final_answer),
            len(steps) >= 8,
            set(flow_state["servers_used"]) == set(SERVER_IDS),
            required_chain_found,
            required_content_complete(flow_state, steps),
            _storage_saved(flow_state, "final-orchestration-report.md"),
            _storage_saved(flow_state, "saved-flow-state.json"),
        )
    )


def required_content_complete(flow_state: dict[str, Any], steps: list[dict[str, Any]]) -> bool:
    tracker = flow_state["tracker"]
    knowledge = flow_state["knowledge"]
    report = flow_state["report"].get("orchestration_report", {})
    save_json_step = next(
        (
            step
            for step in reversed(steps)
            if step["server"] == "storage" and step["tool"] == "save_json_file"
        ),
        None,
    )
    saved_keys = (
        set(save_json_step["arguments"].get("data", {}).get("keys", []))
        if save_json_step
        else set()
    )
    return all(
        (
            {"search_done", "search_planned"}.issubset(tracker),
            REQUIRED_KNOWLEDGE_IDS.issubset(knowledge),
            isinstance(report, dict) and report.get("knowledge_items", 0) >= 5,
            REQUIRED_SAVED_STATE_KEYS.issubset(saved_keys),
        )
    )


def _storage_saved(flow_state: dict[str, Any], filename: str) -> bool:
    payload = flow_state.get("storage", {}).get(filename, {})
    return isinstance(payload, dict) and payload.get("saved") is True


def extract_tool_payload(call_result: CallToolResult, tool_name: str) -> dict[str, Any]:
    if call_result.structuredContent is not None:
        value = json_compatible(call_result.structuredContent)
        if isinstance(value, dict):
            return value
    for block in call_result.content:
        if isinstance(block, TextContent):
            try:
                value = json.loads(block.text)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return cast(dict[str, Any], value)
    raise McpOrchestrationError(f"Tool {tool_name} returned no structured JSON object")


def extract_error_text(call_result: CallToolResult) -> str:
    return " ".join(block.text for block in call_result.content if isinstance(block, TextContent))


def summarize_result(server: str, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    if server == "tracker":
        return {
            "issue_count": payload.get("issue_count", 1 if payload.get("issue_key") else 0),
            "issue_keys": [
                item.get("issue_key")
                for item in payload.get("issues", [])
                if isinstance(item, dict)
            ]
            or ([payload.get("issue_key")] if payload.get("issue_key") else []),
        }
    if server == "knowledge":
        return {"id": payload.get("id"), "title": payload.get("title")}
    if server == "report":
        return {
            "title": payload.get("title") or payload.get("report_title"),
            "issue_count": payload.get("issue_count") or payload.get("source_issue_count"),
            "next_steps_count": len(payload.get("next_steps", [])),
            "markdown_bytes": len(str(payload.get("markdown", "")).encode()),
        }
    if server == "storage":
        return {
            "saved": payload.get("saved"),
            "path": payload.get("path"),
            "bytes_written": payload.get("bytes_written"),
            "sha256": payload.get("sha256"),
        }
    return {"keys": sorted(payload), "tool": tool}


def sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Keep action evidence compact without storing large report/state bodies."""

    result: dict[str, Any] = {}
    for key, value in arguments.items():
        if key == "content" and isinstance(value, str):
            result[key] = {"bytes": len(value.encode()), "sha256": sha256_text(value)}
        elif key in {"tracker_data", "knowledge_context", "data"} and isinstance(value, dict):
            serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
            result[key] = {
                "keys": sorted(value),
                "bytes": len(serialized.encode()),
                "sha256": sha256_text(serialized),
            }
        elif key in {"flow_summary", "report_summary"} and isinstance(value, dict):
            result[key] = value
        else:
            result[key] = value
    return cast(dict[str, Any], json_compatible(result))


def initial_flow_state() -> dict[str, Any]:
    return {
        "tracker": {},
        "knowledge": {},
        "report": {},
        "storage": {},
        "counts_by_server": {},
        "counts_by_tool": {},
        "servers_used": [],
        "tool_calls_total": 0,
        "completed_steps": [],
        "final_success_flags": {},
    }


def server_environment(output_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    source_dir = str(Path(__file__).resolve().parents[1])
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_dir if not current_pythonpath else os.pathsep.join((source_dir, current_pythonpath))
    )
    env[ORCHESTRATION_OUTPUT_DIR_ENV] = str(output_dir.resolve())
    return env


def write_orchestration_outputs(
    result: OrchestrationResult, output_dir: Path, results_file: Path
) -> tuple[Path, ...]:
    """Write process evidence; final report/state already came from Storage MCP."""

    output_dir.mkdir(parents=True, exist_ok=True)
    results_file.parent.mkdir(parents=True, exist_ok=True)
    payloads = {
        "server-registry.json": {"servers": result.server_registry},
        "tools-registry.json": {"tools": result.tools_registry},
        "orchestration-trace.json": result.trace_dict(),
        "routing-decisions.json": {"decisions": result.routing_decisions},
        "flow-state.json": result.flow_state,
    }
    paths: list[Path] = []
    for filename, payload in payloads.items():
        path = output_dir / filename
        write_json(path, payload)
        paths.append(path)
    final_answer_path = output_dir / "final-agent-answer.md"
    final_answer_path.write_text(result.final_answer + "\n", encoding="utf-8")
    paths.append(final_answer_path)
    results_file.write_text(build_results_markdown(result), encoding="utf-8")
    paths.append(results_file)
    return tuple(paths)


def build_results_markdown(result: OrchestrationResult) -> str:
    server_rows = "\n".join(
        f"| `{item['server_id']}` | `{item['transport']}` | {item['tool_count']} | "
        f"`{item['status']}` |"
        for item in result.server_registry
    )
    tool_rows = "\n".join(
        f"| `{item['server_id']}` | `{item['name']}` | "
        f"{'write' if item['write'] else 'read/process'} |"
        for item in result.tools_registry
    )
    timeline_rows = "\n".join(
        f"| {item['step']} | `{item['chosen_by']}` | `{item['server']}` | `{item['tool']}` | "
        f"`{json.dumps(item['result_summary'], ensure_ascii=False)}` |"
        for item in result.steps
    )
    artifacts = [
        "server-registry.json",
        "tools-registry.json",
        "orchestration-trace.json",
        "routing-decisions.json",
        "flow-state.json",
        "final-orchestration-report.md",
        "final-agent-answer.md",
        "saved-flow-state.json",
    ]
    artifact_rows = "\n".join(f"- `{name}`" for name in artifacts)
    servers_used = ", ".join(f"`{item}`" for item in result.flow_state["servers_used"])
    return f"""# Day 20 — Orchestration MCP

Статус: `{"✅ done" if result.completed and result.planner == "llm-json" else "⏳ planned"}`.

## Цель

Проверить модель-агностичную оркестрацию нескольких MCP servers: discovery, normalized registry,
neutral JSON planning, validation, routing в правильную stdio session и длинный flow до safe save.

## Архитектурные свойства

- Planner mode: `{result.planner}`
- Model: `{result.model}`
- `model_specific_tool_calling=false`
- `hardcoded_pipeline=false`
- Tool calls: `{len(result.steps)}`
- Servers used: {servers_used}
- Required ordered chain found: `{str(result.required_chain_found).lower()}`
- Completed: `{str(result.completed).lower()}`
- LLM API calls: `{result.usage.get("llm_api_calls", 0)}`

Несколько servers используются как отдельные boundaries ответственности: Tracker выдаёт mock
issues, Knowledge — локальный учебный контекст, Report — deterministic processing, Storage —
единственная точка записи финальных flow artifacts.

## Registered servers

| Server | Transport | Tools | Status |
|---|---|---:|---|
{server_rows}

## Tools by server

| Server | Tool | Behavior |
|---|---|---|
{tool_rows}

## Routing timeline

Каждый action проверен против registry, затем разрешён через `sessions[action.server]`. Таблица
показывает фактический порядок; success допускает дополнительные/retry calls, но требует ordered
subsequence `tracker -> knowledge -> report -> next_steps -> save_markdown -> save_json`.

| Step | Chosen by | Server | Tool | Result summary |
|---:|---|---|---|---|
{timeline_rows}

## Saved artifacts

{artifact_rows}

`final-orchestration-report.md` и `saved-flow-state.json` сохранены соответствующими Storage MCP
tools. Registry, trace, routing decisions, compact flow state и final answer являются служебными
evidence-файлами host/orchestrator.

## Проверка выбора и порядка

- server/tool validation запрещает неизвестный server, tool и несовпадающую принадлежность;
- routing decision фиксирует requested server/tool и resolved session для каждого вызова;
- success требует все четыре server, минимум восемь calls и причинный ordered subsequence;
- exact sequence equality не используется, поэтому допустимы LLM retry/extra calls;
- scripted planner предназначен только для offline tests и не заменяет этот online result.
"""


def empty_usage() -> dict[str, Any]:
    return {
        "planner_calls": 0,
        "llm_api_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def merge_usage(accumulator: dict[str, Any], usage: dict[str, Any], mode: str) -> None:
    accumulator["planner_calls"] += 1
    if mode == "llm-json":
        accumulator["llm_api_calls"] += 1
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if isinstance(usage.get(key), int):
            accumulator[key] += usage[key]
    if usage.get("model"):
        accumulator["model"] = usage["model"]


def json_compatible(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

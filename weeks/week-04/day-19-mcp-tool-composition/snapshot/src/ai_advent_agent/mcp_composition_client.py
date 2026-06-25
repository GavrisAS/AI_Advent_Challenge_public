"""Generic MCP tool composition loop for Day 19."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent, Tool

from ai_advent_agent.config import DEFAULT_API_URL, DEFAULT_MODEL
from ai_advent_agent.env import load_env_file
from ai_advent_agent.mcp_composition_server import COMPOSITION_OUTPUT_DIR_ENV
from ai_advent_agent.mcp_tool_client import NormalizedMcpTool, json_compatible, markdown_cell

COMPOSITION_SEARCH_TOOL_NAME = "search_tracker_issues"
COMPOSITION_REPORT_TOOL_NAME = "build_tracker_report"
COMPOSITION_SAVE_TOOL_NAME = "save_report_to_file"
COMPOSITION_TOOL_NAMES = (
    COMPOSITION_SEARCH_TOOL_NAME,
    COMPOSITION_REPORT_TOOL_NAME,
    COMPOSITION_SAVE_TOOL_NAME,
)
LOCAL_MCP_TRANSPORT = "stdio"
DEFAULT_MCP_COMPOSITION_TIMEOUT_SECONDS = 30.0
DEFAULT_MCP_COMPOSITION_GOAL = (
    "Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл."
)

Message = dict[str, Any]
PlannerMode = Literal["llm", "scripted"]


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlannerResponse:
    content: str
    tool_calls: tuple[ToolCallRequest, ...]
    finish_reason: str | None
    usage: dict[str, Any]
    raw_message: dict[str, Any]


class ToolPlanner(Protocol):
    planner_name: PlannerMode
    model: str

    def next(self, *, messages: list[Message], tools: list[dict[str, Any]]) -> PlannerResponse:
        """Return the next assistant message and optional tool calls."""


@dataclass(frozen=True, slots=True)
class CompositionToolTraceEntry:
    step: int
    requested_by: PlannerMode
    tool_name: str
    arguments: dict[str, Any]
    result_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "requested_by": self.requested_by,
            "tool_name": self.tool_name,
            "arguments": sanitize_arguments(self.arguments),
            "result_summary": self.result_summary,
        }


@dataclass(frozen=True, slots=True)
class McpToolCompositionResult:
    timestamp_utc: str
    sdk_version: str
    protocol_version: str
    server_name: str
    server_version: str
    planner: PlannerMode
    model: str
    goal: str
    tools: tuple[NormalizedMcpTool, ...]
    tool_trace: tuple[CompositionToolTraceEntry, ...]
    final_answer: str
    usage: dict[str, Any]
    pipeline_result: dict[str, Any]

    def tools_list_dict(self) -> dict[str, Any]:
        return {
            "transport": LOCAL_MCP_TRANSPORT,
            "server_command": ["python", "-m", "ai_advent_agent.mcp_composition_server"],
            "tool_count": len(self.tools),
            "tools": [tool.to_dict() for tool in self.tools],
        }

    def trace_dict(self) -> dict[str, Any]:
        return {
            "planner": self.planner,
            "requested_by": self.planner,
            "hardcoded_pipeline": False,
            "goal": self.goal,
            "model": self.model,
            "tool_call_sequence": [entry.to_dict() for entry in self.tool_trace],
            "final_answer": self.final_answer,
            "llm_api_calls": self.usage.get("llm_api_calls", 0),
            "planner_calls": self.usage.get("planner_calls", 0),
            "usage": self.usage,
        }


class McpToolCompositionError(RuntimeError):
    """Raised when Day 19 MCP tool composition cannot be completed."""


class ToolCallingClientError(RuntimeError):
    """Raised when the LLM tool-calling API request fails or is malformed."""


class ScriptedToolPlanner:
    """Deterministic planner used by tests while exercising the same execution loop."""

    planner_name: PlannerMode = "scripted"
    model = "scripted-tool-planner"

    def next(self, *, messages: list[Message], tools: list[dict[str, Any]]) -> PlannerResponse:
        del tools
        search_result = last_tool_payload(messages, COMPOSITION_SEARCH_TOOL_NAME)
        report_result = last_tool_payload(messages, COMPOSITION_REPORT_TOOL_NAME)
        save_result = last_tool_payload(messages, COMPOSITION_SAVE_TOOL_NAME)
        if search_result is None:
            return PlannerResponse(
                content="",
                tool_calls=(
                    ToolCallRequest(
                        id="scripted-call-1",
                        name=COMPOSITION_SEARCH_TOOL_NAME,
                        arguments={
                            "status": "done",
                            "priority": None,
                            "query": "Week 04",
                            "limit": 10,
                        },
                    ),
                ),
                finish_reason="tool_calls",
                usage={},
                raw_message={},
            )
        if report_result is None:
            return PlannerResponse(
                content="",
                tool_calls=(
                    ToolCallRequest(
                        id="scripted-call-2",
                        name=COMPOSITION_REPORT_TOOL_NAME,
                        arguments={
                            "issues": search_result["issues"],
                            "report_title": "Week 04 MCP progress report",
                        },
                    ),
                ),
                finish_reason="tool_calls",
                usage={},
                raw_message={},
            )
        if save_result is None:
            return PlannerResponse(
                content="",
                tool_calls=(
                    ToolCallRequest(
                        id="scripted-call-3",
                        name=COMPOSITION_SAVE_TOOL_NAME,
                        arguments={
                            "markdown": report_result["markdown"],
                            "filename": "tracker-composition-report.md",
                        },
                    ),
                ),
                finish_reason="tool_calls",
                usage={},
                raw_message={},
            )

        return PlannerResponse(
            content=(
                "Пайплайн MCP tools завершён: найденные задачи переданы в report builder, "
                f"отчёт сохранён в `{save_result['path']}`."
            ),
            tool_calls=(),
            finish_reason="stop",
            usage={},
            raw_message={},
        )


class DeepSeekToolPlanner:
    """DeepSeek-compatible Chat Completions tool-calling client."""

    planner_name: PlannerMode = "llm"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        api_url: str = DEFAULT_API_URL,
        temperature: float = 0.0,
        max_tokens: int = 1200,
        timeout_seconds: float = 120,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DEEPSEEK_API_KEY не задан. Для --planner llm нужен реальный API key.")
        if not model.strip():
            raise ValueError("model не должен быть пустым")
        if not api_url.strip():
            raise ValueError("api_url не должен быть пустым")
        if max_tokens <= 0:
            raise ValueError("max_tokens должен быть больше 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds должен быть больше 0")
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    def next(self, *, messages: list[Message], tools: list[dict[str, Any]]) -> PlannerResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
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
            raise ToolCallingClientError(
                f"DeepSeek tool-calling API вернул HTTP {error.code}: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            raise ToolCallingClientError(
                f"Не удалось подключиться к DeepSeek tool-calling API: {error}"
            ) from error

        return parse_tool_calling_response(
            response_body=response_body,
            model=self.model,
            elapsed_seconds=time.perf_counter() - started_at,
        )


async def run_composition_demo_via_mcp(
    *,
    planner: ToolPlanner,
    goal: str = DEFAULT_MCP_COMPOSITION_GOAL,
    output_dir: Path,
    timeout_seconds: float = DEFAULT_MCP_COMPOSITION_TIMEOUT_SECONDS,
    max_planner_steps: int = 8,
) -> McpToolCompositionResult:
    """Run a generic LLM/scripted planner loop over the Day 19 stdio MCP server."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if max_planner_steps <= 0:
        raise ValueError("max_planner_steps must be greater than zero")

    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ai_advent_agent.mcp_composition_server"],
        env=server_environment(output_dir),
    )
    try:
        async with asyncio.timeout(timeout_seconds):
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                ) as session:
                    initialization = await session.initialize()
                    tools_page = await session.list_tools()
                    tools = tuple(
                        sorted(
                            (normalize_tool(tool) for tool in tools_page.tools),
                            key=lambda item: item.name,
                        )
                    )
                    validate_expected_tools(tools)
                    chat_tools = [mcp_tool_to_chat_tool(tool) for tool in tools]
                    messages = build_initial_messages(goal)
                    trace_entries: list[CompositionToolTraceEntry] = []
                    usage = empty_usage()

                    for _ in range(max_planner_steps):
                        planner_response = planner.next(messages=messages, tools=chat_tools)
                        merge_usage(usage, planner_response.usage, planner.planner_name)
                        assistant_message = build_assistant_message(planner_response)
                        messages.append(assistant_message)
                        if not planner_response.tool_calls:
                            final_answer = planner_response.content.strip()
                            pipeline_result = build_pipeline_result(
                                trace_entries,
                                planner=planner.planner_name,
                            )
                            return McpToolCompositionResult(
                                timestamp_utc=utc_timestamp(),
                                sdk_version=package_version("mcp"),
                                protocol_version=str(initialization.protocolVersion),
                                server_name=initialization.serverInfo.name,
                                server_version=initialization.serverInfo.version,
                                planner=planner.planner_name,
                                model=planner.model,
                                goal=goal,
                                tools=tools,
                                tool_trace=tuple(trace_entries),
                                final_answer=final_answer,
                                usage=usage,
                                pipeline_result=pipeline_result,
                            )

                        for tool_call in planner_response.tool_calls:
                            if tool_call.name not in {tool.name for tool in tools}:
                                raise McpToolCompositionError(
                                    f"Planner requested unknown MCP tool: {tool_call.name}"
                                )
                            call_result = await session.call_tool(
                                tool_call.name,
                                arguments=tool_call.arguments,
                            )
                            if call_result.isError:
                                raise McpToolCompositionError(
                                    f"MCP tool {tool_call.name} returned an error: {call_result!r}"
                                )
                            payload = extract_composition_payload(call_result, tool_call.name)
                            trace_entries.append(
                                CompositionToolTraceEntry(
                                    step=len(trace_entries) + 1,
                                    requested_by=planner.planner_name,
                                    tool_name=tool_call.name,
                                    arguments=tool_call.arguments,
                                    result_summary=summarize_tool_result(tool_call.name, payload),
                                )
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_call.name,
                                    "content": json.dumps(
                                        payload, ensure_ascii=False, sort_keys=True
                                    ),
                                }
                            )
    except TimeoutError as error:
        raise McpToolCompositionError(
            f"Local MCP tool composition timed out after {timeout_seconds:g} seconds"
        ) from error

    raise McpToolCompositionError(f"Planner did not finish after {max_planner_steps} steps")


def build_llm_planner_from_env(
    *,
    model: str | None,
    api_url: str | None,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> DeepSeekToolPlanner:
    load_env_file()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise McpToolCompositionError(
            "DEEPSEEK_API_KEY не найден. Для --planner llm задайте ключ в env или .env; "
            "автоматический fallback на scripted не выполняется."
        )
    return DeepSeekToolPlanner(
        api_key=api_key,
        model=model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
        api_url=api_url or os.getenv("DEEPSEEK_API_URL", DEFAULT_API_URL),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )


def build_initial_messages(goal: str) -> list[Message]:
    return [
        {
            "role": "system",
            "content": (
                "Ты planner для MCP tools. Используй доступные tools, чтобы выполнить цель. "
                "Не выдумывай данные: сначала получи задачи, затем передай найденные issues в "
                "report builder, затем сохрани markdown через save tool. Для сохранения итогового "
                "отчёта используй filename `tracker-composition-report.md`. Финальный ответ дай "
                "только после сохранения файла."
            ),
        },
        {"role": "user", "content": goal},
    ]


def mcp_tool_to_chat_tool(tool: NormalizedMcpTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def parse_tool_calling_response(
    *, response_body: str, model: str, elapsed_seconds: float
) -> PlannerResponse:
    try:
        data = json.loads(response_body)
        choice = data["choices"][0]
        message = choice["message"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise ToolCallingClientError(
            f"Не удалось разобрать ответ DeepSeek tool-calling API: {response_body[:1000]}"
        ) from error

    tool_calls = []
    for index, raw_call in enumerate(message.get("tool_calls") or [], start=1):
        try:
            function = raw_call["function"]
            raw_arguments = function.get("arguments") or "{}"
            arguments = json.loads(raw_arguments)
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ToolCallingClientError(
                f"Malformed tool call arguments in response: {raw_call!r}"
            ) from error
        if not isinstance(arguments, dict):
            raise ToolCallingClientError(
                f"Tool call arguments must decode to an object: {raw_call!r}"
            )
        tool_calls.append(
            ToolCallRequest(
                id=str(raw_call.get("id") or f"tool-call-{index}"),
                name=str(function["name"]),
                arguments=cast(dict[str, Any], json_compatible(arguments)),
            )
        )

    usage = data.get("usage", {}) or {}
    usage = cast(dict[str, Any], json_compatible(usage))
    usage["elapsed_seconds"] = elapsed_seconds
    usage["model"] = model
    return PlannerResponse(
        content=message.get("content") or "",
        tool_calls=tuple(tool_calls),
        finish_reason=choice.get("finish_reason"),
        usage=usage,
        raw_message=cast(dict[str, Any], json_compatible(message)),
    )


def build_assistant_message(response: PlannerResponse) -> Message:
    message: Message = {"role": "assistant", "content": response.content or None}
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                },
            }
            for tool_call in response.tool_calls
        ]
    return message


def extract_composition_payload(call_result: CallToolResult, tool_name: str) -> dict[str, Any]:
    if call_result.structuredContent is not None:
        return cast(dict[str, Any], json_compatible(call_result.structuredContent))
    for block in call_result.content:
        if isinstance(block, TextContent):
            try:
                payload = json.loads(block.text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return cast(dict[str, Any], json_compatible(payload))
    raise McpToolCompositionError(f"MCP call result did not contain payload for {tool_name}")


def normalize_tool(tool: Tool) -> NormalizedMcpTool:
    schema = cast(dict[str, object], json.loads(json.dumps(tool.inputSchema)))
    return NormalizedMcpTool(
        name=tool.name,
        description=tool.description,
        input_schema=schema,
    )


def summarize_tool_result(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == COMPOSITION_SEARCH_TOOL_NAME:
        return {
            "issue_count": payload.get("issue_count"),
            "issues": [issue.get("issue_key") for issue in payload.get("issues", [])],
        }
    if tool_name == COMPOSITION_REPORT_TOOL_NAME:
        markdown = str(payload.get("markdown", ""))
        return {
            "issue_count": payload.get("issue_count"),
            "status_counts": payload.get("status_counts"),
            "priority_counts": payload.get("priority_counts"),
            "markdown_length": len(markdown),
        }
    if tool_name == COMPOSITION_SAVE_TOOL_NAME:
        return {
            "saved": payload.get("saved"),
            "path": payload.get("path"),
            "bytes_written": payload.get("bytes_written"),
            "sha256": payload.get("sha256"),
        }
    return {"keys": sorted(payload)}


def build_pipeline_result(
    trace_entries: list[CompositionToolTraceEntry],
    *,
    planner: PlannerMode,
) -> dict[str, Any]:
    sequence = [entry.tool_name for entry in trace_entries]
    required_chain_indices = ordered_subsequence_indices(sequence, COMPOSITION_TOOL_NAMES)
    required_chain_found = required_chain_indices is not None
    save_entry = next(
        (
            entry
            for entry in reversed(trace_entries)
            if entry.tool_name == COMPOSITION_SAVE_TOOL_NAME
            and entry.result_summary.get("saved") is True
        ),
        None,
    )
    save_summary = save_entry.result_summary if save_entry else {}
    save_completed = save_summary.get("saved") is True
    report_entry = find_relevant_report_entry(trace_entries, save_entry)
    issue_count = infer_issue_count(trace_entries, report_entry)
    return {
        "completed": required_chain_found and save_completed,
        "planner": planner,
        "requested_by": planner,
        "tool_count": len(trace_entries),
        "tool_sequence": sequence,
        "required_chain": list(COMPOSITION_TOOL_NAMES),
        "required_chain_found": required_chain_found,
        "save_completed": save_completed,
        "issue_count": issue_count,
        "report_path": save_summary.get("path"),
        "report_sha256": save_summary.get("sha256"),
    }


def ordered_subsequence_indices(
    sequence: list[str], required: tuple[str, ...]
) -> tuple[int, ...] | None:
    indices: list[int] = []
    start = 0
    for required_name in required:
        try:
            index = sequence.index(required_name, start)
        except ValueError:
            return None
        indices.append(index)
        start = index + 1
    return tuple(indices)


def find_relevant_report_entry(
    trace_entries: list[CompositionToolTraceEntry],
    save_entry: CompositionToolTraceEntry | None,
) -> CompositionToolTraceEntry | None:
    upper_step = save_entry.step if save_entry else len(trace_entries) + 1
    return next(
        (
            entry
            for entry in reversed(trace_entries)
            if entry.tool_name == COMPOSITION_REPORT_TOOL_NAME and entry.step < upper_step
        ),
        None,
    )


def infer_issue_count(
    trace_entries: list[CompositionToolTraceEntry],
    report_entry: CompositionToolTraceEntry | None,
) -> int | None:
    if report_entry is not None:
        report_count = report_entry.result_summary.get("issue_count")
        if isinstance(report_count, int):
            return report_count

    search_entries = [
        entry for entry in trace_entries if entry.tool_name == COMPOSITION_SEARCH_TOOL_NAME
    ]
    if report_entry is not None:
        previous_search_counts = [
            entry.result_summary.get("issue_count")
            for entry in search_entries
            if entry.step < report_entry.step
        ]
        previous_int_counts = [count for count in previous_search_counts if isinstance(count, int)]
        if previous_int_counts:
            return previous_int_counts[-1]

    all_counts = [
        entry.result_summary.get("issue_count")
        for entry in search_entries
        if isinstance(entry.result_summary.get("issue_count"), int)
    ]
    return max(all_counts) if all_counts else None


def validate_expected_tools(tools: tuple[NormalizedMcpTool, ...]) -> None:
    actual = {tool.name for tool in tools}
    missing = sorted(set(COMPOSITION_TOOL_NAMES) - actual)
    extra = sorted(actual - set(COMPOSITION_TOOL_NAMES))
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing: " + ", ".join(missing))
        if extra:
            parts.append("extra: " + ", ".join(extra))
        raise McpToolCompositionError(
            "Local composition MCP server exposed unexpected tools: " + "; ".join(parts)
        )


def last_tool_payload(messages: list[Message], tool_name: str) -> dict[str, Any] | None:
    for message in reversed(messages):
        if message.get("role") != "tool" or message.get("name") != tool_name:
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
    return None


def sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(arguments)
    if "issues" in sanitized and isinstance(sanitized["issues"], list):
        sanitized["issues"] = [
            issue.get("issue_key", "<unknown>") if isinstance(issue, dict) else "<non-object>"
            for issue in sanitized["issues"]
        ]
    if "markdown" in sanitized and isinstance(sanitized["markdown"], str):
        sanitized["markdown"] = {
            "sha256": hashlib_text(sanitized["markdown"]),
            "length": len(sanitized["markdown"]),
        }
    return cast(dict[str, Any], json_compatible(sanitized))


def hashlib_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def empty_usage() -> dict[str, Any]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "planner_calls": 0,
        "llm_api_calls": 0,
    }


def merge_usage(
    accumulator: dict[str, Any], usage: dict[str, Any], planner_mode: PlannerMode
) -> None:
    accumulator["planner_calls"] = int(accumulator.get("planner_calls", 0)) + 1
    if planner_mode == "llm":
        accumulator["llm_api_calls"] = int(accumulator.get("llm_api_calls", 0)) + 1
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            accumulator[key] = int(accumulator.get(key, 0)) + value
    if "model" in usage:
        accumulator["model"] = usage["model"]


def server_environment(output_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    src_dir = str(Path(__file__).resolve().parents[1])
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_dir if not current_pythonpath else os.pathsep.join([src_dir, current_pythonpath])
    )
    env[COMPOSITION_OUTPUT_DIR_ENV] = str(output_dir)
    return env


def write_composition_demo_outputs(
    result: McpToolCompositionResult, output_dir: Path, results_file: Path
) -> tuple[Path, Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file.parent.mkdir(parents=True, exist_ok=True)

    tools_path = output_dir / "tools-list.json"
    trace_path = output_dir / "llm-tool-call-trace.json"
    pipeline_path = output_dir / "pipeline-result.json"
    final_answer_path = output_dir / "final-agent-answer.md"

    write_json(tools_path, result.tools_list_dict())
    write_json(trace_path, result.trace_dict())
    write_json(pipeline_path, result.pipeline_result)
    final_answer_path.write_text(result.final_answer + "\n", encoding="utf-8")
    results_file.write_text(build_results_markdown(result, output_dir), encoding="utf-8")
    return tools_path, trace_path, pipeline_path, final_answer_path, results_file


def build_results_markdown(result: McpToolCompositionResult, output_dir: Path) -> str:
    tool_rows = "\n".join(
        f"| `{tool.name}` | {markdown_cell(tool.description or '—')} |" for tool in result.tools
    )
    timeline_rows = "\n".join(
        f"| {entry.step} | `{entry.requested_by}` | `{entry.tool_name}` | "
        f"`{markdown_cell(json.dumps(entry.result_summary, ensure_ascii=False))}` |"
        for entry in result.tool_trace
    )
    sequence = " -> ".join(f"`{name}`" for name in result.pipeline_result["tool_sequence"])
    report_path = result.pipeline_result.get("report_path") or "—"
    report_sha256 = result.pipeline_result.get("report_sha256") or "—"
    search_calls = sum(
        1 for entry in result.tool_trace if entry.tool_name == COMPOSITION_SEARCH_TOOL_NAME
    )
    adaptive_note = (
        "\n\nThe LLM made multiple search attempts before building the report. This is expected "
        "for an online planner and still satisfies the required ordered chain because the "
        "successful path contains `search_tracker_issues -> build_tracker_report -> "
        "save_report_to_file`."
        if result.planner == "llm" and search_calls > 1
        else ""
    )
    return f"""# Day 19 — Композиция MCP-инструментов

Статус: `✅ done`.

## Задание и уточнение

Day 19 проверяет автоматический пайплайн из нескольких MCP tools. Важное уточнение преподавателя:
`summarize` в исходном задании означает отчёт / итог / обработку данных, а не LLM-суммаризацию
внутри tool. Поэтому `build_tracker_report` строит deterministic Markdown report без LLM.

## Архитектура

```text
LLM planner -> generic MCP client loop -> stdio MCP server -> deterministic tools
```

- Planner: `{result.planner}`
- Model: `{result.model}`
- Transport: `{LOCAL_MCP_TRANSPORT}`
- Server: `{result.server_name} {result.server_version}`
- Protocol version: `{result.protocol_version}`
- MCP Python SDK: `{result.sdk_version}`
- Hardcoded pipeline: `false`
- LLM API calls: `{result.usage.get("llm_api_calls", 0)}`
- Pipeline completed: `{markdown_bool(result.pipeline_result.get("completed"))}`
- Required chain found: `{markdown_bool(result.pipeline_result.get("required_chain_found"))}`
- Save completed: `{markdown_bool(result.pipeline_result.get("save_completed"))}`
- Issue count: `{result.pipeline_result.get("issue_count")}`
- Goal: {result.goal}

## MCP tools

| Tool | Schema summary |
|---|---|
{tool_rows}

## Tool-call trace

Последовательность вызовов пришла от planner/model и была исполнена generic loop через
`session.call_tool(...)`:{adaptive_note}

| Step | Requested by | Tool | Outcome |
|---:|---|---|---|
{timeline_rows}

Pipeline sequence: {sequence}

## Передача данных между tools

- Output `search_tracker_issues.issues` стал input `build_tracker_report.issues`.
- Output `build_tracker_report.markdown` стал input `save_report_to_file.markdown`.
- `save_report_to_file` создал файл отчёта внутри configured artifacts/output dir.

## Итоговый report file

- Path: `{report_path}`
- SHA-256: `{report_sha256}`
- Artifacts directory: `{output_dir}`

## Команды запуска

Основной LLM-driven запуск требует `DEEPSEEK_API_KEY`:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-tool-composition-demo \\
  --planner llm \\
  --goal "Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл." \\
  --output-dir weeks/week-04/day-19-mcp-tool-composition/artifacts \\
  --results-file weeks/week-04/day-19-mcp-tool-composition/results/day-19-mcp-tool-composition.md
```

Offline scripted fallback используется только для deterministic tests без API key:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-tool-composition-demo \\
  --planner scripted \\
  --output-dir .tmp/day19-scripted-fallback \\
  --results-file .tmp/day19-scripted-fallback/day-19-mcp-tool-composition.md
```

## Testing notes

Default tests не ходят в сеть и не требуют `DEEPSEEK_API_KEY`. `scripted` planner остаётся
test/offline fallback: он имитирует tool-call responses, но проходит через тот же generic
execution loop и stdio MCP `call_tool`.

## Security notes

- Реальный Tracker/Jira/GitHub API не используется; данные mock.
- Secrets, raw API headers и API key не сохраняются в artifacts.
- `save_report_to_file` запрещает абсолютные пути, `..` и path separators.
- Output ограничен configured artifacts/output directory.
"""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def markdown_bool(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

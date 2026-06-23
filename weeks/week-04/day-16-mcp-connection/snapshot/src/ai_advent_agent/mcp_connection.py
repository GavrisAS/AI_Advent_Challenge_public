"""Remote MCP connection and tool discovery helpers for Day 16."""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlsplit

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import PaginatedRequestParams, Tool

DEFAULT_MCP_SERVER_URL = "https://mcp.deepwiki.com/mcp"
DEFAULT_MCP_TIMEOUT_SECONDS = 30.0
MCP_TRANSPORT = "streamable-http"
EXPECTED_DEEPWIKI_TOOLS = frozenset({"ask_question", "read_wiki_contents", "read_wiki_structure"})

McpErrorKind = Literal["dns", "connectivity", "timeout", "protocol", "empty_tool_list"]


@dataclass(frozen=True, slots=True)
class NormalizedTool:
    """Stable JSON-friendly subset of MCP tool metadata."""

    name: str
    description: str | None
    input_schema: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass(frozen=True, slots=True)
class McpConnectionResult:
    """Normalized result of a successful MCP initialization and tools/list request."""

    server_url: str
    timestamp_utc: str
    sdk_version: str
    protocol_version: str
    server_name: str
    server_version: str
    tools: tuple[NormalizedTool, ...]
    expected_tools: tuple[str, ...]
    missing_expected_tools: tuple[str, ...]
    extra_tools: tuple[str, ...]

    @property
    def expected_tools_present(self) -> bool:
        return not self.missing_expected_tools

    def to_dict(self) -> dict[str, object]:
        return {
            "server_url": self.server_url,
            "transport": MCP_TRANSPORT,
            "connected": True,
            "initialized": True,
            "timestamp_utc": self.timestamp_utc,
            "sdk_package": "mcp",
            "sdk_version": self.sdk_version,
            "protocol_version": self.protocol_version,
            "server_info": {
                "name": self.server_name,
                "version": self.server_version,
            },
            "tool_count": len(self.tools),
            "expected_tools": list(self.expected_tools),
            "expected_tools_present": self.expected_tools_present,
            "missing_expected_tools": list(self.missing_expected_tools),
            "extra_tools": list(self.extra_tools),
            "tools": [tool.to_dict() for tool in self.tools],
        }

    def tools_list_dict(self) -> dict[str, object]:
        return {
            "server_url": self.server_url,
            "transport": MCP_TRANSPORT,
            "tool_count": len(self.tools),
            "tools": [tool.to_dict() for tool in self.tools],
        }


class McpConnectionError(RuntimeError):
    """Categorized failure that must not be reported as a successful MCP result."""

    def __init__(self, kind: McpErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def validate_server_url(server_url: str) -> str:
    """Validate the remote HTTP endpoint and reject embedded credentials."""

    parsed = urlsplit(server_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("MCP server URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("MCP server URL must not contain embedded credentials")
    return server_url


def normalize_tool(tool: Tool) -> NormalizedTool:
    """Convert SDK tool metadata to a deterministic serializable representation."""

    schema = cast(dict[str, object], json.loads(json.dumps(tool.inputSchema)))
    return NormalizedTool(
        name=tool.name,
        description=tool.description,
        input_schema=schema,
    )


def compare_expected_tools(
    tool_names: Collection[str], expected_tools: Collection[str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return missing expected tools and unexpected extra tools in stable order."""

    actual = set(tool_names)
    expected = set(expected_tools)
    return tuple(sorted(expected - actual)), tuple(sorted(actual - expected))


async def discover_mcp_tools(
    server_url: str = DEFAULT_MCP_SERVER_URL,
    timeout_seconds: float = DEFAULT_MCP_TIMEOUT_SECONDS,
    expected_tools: Collection[str] = EXPECTED_DEEPWIKI_TOOLS,
) -> McpConnectionResult:
    """Initialize a remote MCP session and discover tools without calling them."""

    validate_server_url(server_url)
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    try:
        async with asyncio.timeout(timeout_seconds):
            async with streamable_http_client(server_url) as (read_stream, write_stream, _):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                ) as session:
                    initialization = await session.initialize()
                    discovered: list[Tool] = []
                    cursor: str | None = None
                    seen_cursors: set[str] = set()

                    while True:
                        if cursor is None:
                            page = await session.list_tools()
                        else:
                            page = await session.list_tools(
                                params=PaginatedRequestParams(cursor=cursor)
                            )
                        discovered.extend(page.tools)
                        next_cursor = page.nextCursor
                        if not next_cursor:
                            break
                        if next_cursor in seen_cursors:
                            raise RuntimeError(
                                "MCP tools/list returned a repeated pagination cursor"
                            )
                        seen_cursors.add(next_cursor)
                        cursor = next_cursor
    except TimeoutError as error:
        raise McpConnectionError(
            "timeout", f"MCP connection timed out after {timeout_seconds:g} seconds"
        ) from error
    except Exception as error:
        kind = classify_mcp_error(error)
        raise McpConnectionError(kind, f"MCP {kind} error: {error}") from error

    tools = tuple(sorted((normalize_tool(tool) for tool in discovered), key=lambda tool: tool.name))
    if not tools:
        raise McpConnectionError("empty_tool_list", "MCP server returned an empty tool list")

    expected = tuple(sorted(set(expected_tools)))
    missing, extra = compare_expected_tools([tool.name for tool in tools], expected)
    return McpConnectionResult(
        server_url=server_url,
        timestamp_utc=utc_timestamp(),
        sdk_version=package_version("mcp"),
        protocol_version=str(initialization.protocolVersion),
        server_name=initialization.serverInfo.name,
        server_version=initialization.serverInfo.version,
        tools=tools,
        expected_tools=expected,
        missing_expected_tools=missing,
        extra_tools=extra,
    )


def classify_mcp_error(error: BaseException) -> McpErrorKind:
    """Classify nested transport and protocol failures into user-facing categories."""

    errors = tuple(iter_nested_errors(error))
    if any(isinstance(item, TimeoutError) for item in errors):
        return "timeout"
    if any(isinstance(item, socket.gaierror) for item in errors):
        return "dns"

    messages = " ".join(str(item).lower() for item in errors)
    if any(
        marker in messages
        for marker in ("name or service not known", "temporary failure in name resolution")
    ):
        return "dns"
    if any(isinstance(item, OSError) for item in errors) or any(
        marker in messages
        for marker in ("connect error", "connection refused", "network is unreachable")
    ):
        return "connectivity"
    return "protocol"


def iter_nested_errors(error: BaseException) -> Iterator[BaseException]:
    """Yield an exception and nested ExceptionGroup/cause/context failures."""

    yield error
    if isinstance(error, BaseExceptionGroup):
        for nested in error.exceptions:
            yield from iter_nested_errors(nested)
    if error.__cause__ is not None:
        yield from iter_nested_errors(error.__cause__)
    elif error.__context__ is not None:
        yield from iter_nested_errors(error.__context__)


def write_success_outputs(
    result: McpConnectionResult, output_dir: Path, results_file: Path
) -> tuple[Path, Path, Path]:
    """Persist the normalized JSON artifacts and Markdown report."""

    output_dir.mkdir(parents=True, exist_ok=True)
    results_file.parent.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "mcp-connection-result.json"
    tools_path = output_dir / "tools-list.json"
    write_json(result_path, result.to_dict())
    write_json(tools_path, result.tools_list_dict())
    results_file.write_text(build_results_markdown(result, output_dir), encoding="utf-8")
    return result_path, tools_path, results_file


def write_error_artifact(error: McpConnectionError, server_url: str, output_dir: Path) -> Path:
    """Persist a clearly unsuccessful runtime diagnostic outside final results."""

    output_dir.mkdir(parents=True, exist_ok=True)
    error_path = output_dir / "mcp-connection-error.json"
    write_json(
        error_path,
        {
            "server_url": server_url,
            "transport": MCP_TRANSPORT,
            "connected": False,
            "initialized": False,
            "timestamp_utc": utc_timestamp(),
            "error_kind": error.kind,
            "error": str(error),
        },
    )
    return error_path


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_results_markdown(result: McpConnectionResult, output_dir: Path) -> str:
    tool_rows = "\n".join(
        f"| `{tool.name}` | {markdown_cell(tool.description or '—')} |" for tool in result.tools
    )
    expected = ", ".join(f"`{name}`" for name in result.expected_tools)
    actual = ", ".join(f"`{tool.name}`" for tool in result.tools)
    missing = ", ".join(f"`{name}`" for name in result.missing_expected_tools) or "нет"
    extra = ", ".join(f"`{name}`" for name in result.extra_tools) or "нет"
    return f"""# Day 16 — MCP Connection

Выполнено реальное remote-подключение без API key и без LLM-вызовов.

## Соединение

- Server URL: `{result.server_url}`
- Transport: `{MCP_TRANSPORT}`
- Initialization: успешно
- Protocol version: `{result.protocol_version}`
- Server: `{result.server_name} {result.server_version}`
- MCP Python SDK: `{result.sdk_version}`
- Timestamp UTC: `{result.timestamp_utc}`
- Tools вызывались: нет, выполнен только discovery через `tools/list`

## Проверка tools

- Ожидаемые: {expected}
- Фактические: {actual}
- Все ожидаемые присутствуют: `{result.expected_tools_present}`
- Отсутствующие ожидаемые: {missing}
- Дополнительные: {extra}

| Tool | Description |
|---|---|
{tool_rows}

## Артефакты

JSON-файлы сформированы в `{output_dir}`:

- `mcp-connection-result.json`
- `tools-list.json`
"""


def markdown_cell(value: str) -> str:
    return " ".join(value.replace("|", "\\|").split())


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

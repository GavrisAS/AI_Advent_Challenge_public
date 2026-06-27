from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from ai_advent_agent.mcp_orchestration_client import (
    DEFAULT_MCP_ORCHESTRATION_GOAL,
    DEFAULT_MCP_ORCHESTRATION_TIMEOUT_SECONDS,
    SERVER_IDS,
    has_required_ordered_chain,
    resolve_action_state_references,
    run_orchestration_via_mcp,
    write_orchestration_outputs,
)
from ai_advent_agent.mcp_orchestration_planner import (
    DeepSeekCompatibleJsonPlanner,
    PlannerAction,
    PlannerError,
    PlannerTurn,
    ScriptedJsonPlanner,
    build_planner_messages,
    compact_flow_state_for_planner,
    parse_planner_action,
)
from ai_advent_agent.mcp_orchestration_servers import SERVER_BUILDERS
from ai_advent_agent.mcp_orchestration_storage import validate_storage_filename
from ai_advent_agent.scenarios import parse_args


class OneTransientFailurePlanner(ScriptedJsonPlanner):
    """Scripted planner that simulates one retryable provider response failure."""

    def __init__(self) -> None:
        self.turns = 0

    async def next_action(self, **kwargs: Any) -> PlannerTurn:
        self.turns += 1
        if self.turns == 1:
            raise PlannerError("transient empty JSON content")
        return await super().next_action(**kwargs)


def test_four_server_builders_expose_expected_tools() -> None:
    expected = {
        "tracker": {"search_tracker_issues", "get_tracker_issue"},
        "knowledge": {"get_mcp_day_context", "get_best_practice_note"},
        "report": {"build_orchestration_report", "build_next_steps"},
        "storage": {"save_markdown_file", "save_json_file"},
    }

    assert tuple(SERVER_BUILDERS) == SERVER_IDS
    for server_id, builder in SERVER_BUILDERS.items():
        tools = asyncio.run(builder().list_tools())
        assert {tool.name for tool in tools} == expected[server_id]


def test_cli_defaults_and_online_overrides(tmp_path: Path) -> None:
    defaults = parse_args(["mcp-orchestration-demo"])
    assert defaults.planner == "scripted"
    assert defaults.goal == DEFAULT_MCP_ORCHESTRATION_GOAL
    assert defaults.server_timeout_seconds == DEFAULT_MCP_ORCHESTRATION_TIMEOUT_SECONDS == 360.0
    assert defaults.max_steps == 15

    parsed = parse_args(
        [
            "mcp-orchestration-demo",
            "--planner",
            "llm-json",
            "--max-steps",
            "14",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--results-file",
            str(tmp_path / "result.md"),
        ]
    )
    assert parsed.planner == "llm-json"
    assert parsed.max_steps == 14
    assert parsed.output_dir == tmp_path / "artifacts"


def test_action_validation_rejects_invalid_server_tool_and_arguments() -> None:
    registry = [
        {"server_id": "tracker", "name": "search_tracker_issues"},
        {"server_id": "storage", "name": "save_json_file"},
    ]
    valid = parse_planner_action(
        json.dumps(
            {
                "action": "call_tool",
                "server": "tracker",
                "tool": "search_tracker_issues",
                "arguments": {},
            }
        ),
        registry,
    )
    assert valid.server == "tracker"

    invalid_payloads = [
        {"action": "call_tool", "server": "missing", "tool": "x", "arguments": {}},
        {
            "action": "call_tool",
            "server": "tracker",
            "tool": "save_json_file",
            "arguments": {},
        },
        {
            "action": "call_tool",
            "server": "tracker",
            "tool": "search_tracker_issues",
            "arguments": [],
        },
    ]
    for payload in invalid_payloads:
        with pytest.raises(PlannerError):
            parse_planner_action(json.dumps(payload), registry)


def test_online_planner_payload_uses_plain_json_completion_contract() -> None:
    planner = DeepSeekCompatibleJsonPlanner(
        api_key="test-key",
        model="test-model",
        api_url="https://example.com/chat/completions",
        temperature=0.0,
        max_tokens=500,
        timeout_seconds=5,
    )

    payload = planner._build_payload([{"role": "user", "content": "Return JSON."}])

    forbidden_fields = {"tools", "tool" + "_calls", "tool" + "_choice", "think" + "ing"}
    assert forbidden_fields.isdisjoint(payload)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"] == [{"role": "user", "content": "Return JSON."}]


def test_compact_flow_state_preserves_signals_without_mutating_full_state() -> None:
    markdown = "# Report\n\n" + "A" * 2_000
    full_state = {
        "tracker": {
            "search_done": {
                "query": {"status": "done"},
                "issue_count": 1,
                "issues": [
                    {
                        "issue_key": "AI-19",
                        "title": "Composition",
                        "status": "done",
                        "priority": "high",
                        "summary": "Completed MCP composition task.",
                    }
                ],
            }
        },
        "knowledge": {
            "day-20": {
                "id": "day-20",
                "title": "Orchestration MCP",
                "summary": "Four-server orchestration.",
                "key_points": ["large details are not needed by the planner"],
            }
        },
        "report": {
            "orchestration_report": {
                "title": "Week 04 report",
                "issue_count": 1,
                "status_counts": {"done": 1},
                "priority_counts": {"high": 1},
                "registered_servers": list(SERVER_IDS),
                "data_source_servers_used_before_report": ["tracker", "knowledge"],
                "markdown": markdown,
            }
        },
        "storage": {},
        "counts_by_server": {"tracker": 1, "knowledge": 1, "report": 1},
        "counts_by_tool": {"report.build_orchestration_report": 1},
        "servers_used": ["tracker", "knowledge", "report"],
        "tool_calls_total": 3,
        "completed_steps": [
            {
                "step": 3,
                "server": "report",
                "tool": "build_orchestration_report",
                "success": True,
            }
        ],
        "final_success_flags": {},
    }
    original = deepcopy(full_state)

    compact = compact_flow_state_for_planner(full_state)

    assert full_state == original
    compact_report = compact["report"]["orchestration_report"]
    assert "markdown" not in compact_report
    assert compact_report["markdown_chars"] == len(markdown)
    assert len(compact_report["markdown_preview"]) <= 400
    assert markdown not in json.dumps(compact, ensure_ascii=False)
    assert compact["servers_used"] == ["tracker", "knowledge", "report"]
    assert compact["counts_by_tool"] == {"report.build_orchestration_report": 1}
    assert compact["completed_steps"] == full_state["completed_steps"]
    assert compact["report_built"] is True
    assert compact["storage_completed"] == {"markdown": False, "json": False}
    assert compact["available_state_references"]["final_report_markdown"] == {
        "$state": "report.orchestration_report.markdown"
    }
    assert compact["available_state_references"]["tracker_data"] == {"$state": "tracker"}
    assert compact["available_state_references"]["knowledge_context"] == {"$state": "knowledge"}
    assert compact["available_state_references"]["report_summary"] == {
        "$projection": "report_summary"
    }
    assert compact["available_state_references"]["saved_flow_state"] == {
        "$projection": "saved_flow_state"
    }


def test_build_planner_messages_uses_compact_state() -> None:
    markdown = "private-large-markdown-" * 200
    flow_state = {
        "tracker": {},
        "knowledge": {},
        "report": {"orchestration_report": {"title": "Report", "markdown": markdown}},
        "storage": {},
        "counts_by_server": {},
        "counts_by_tool": {},
        "servers_used": ["report"],
        "tool_calls_total": 1,
        "completed_steps": [
            {"step": 1, "server": "report", "tool": "build_orchestration_report", "success": True}
        ],
        "final_success_flags": {},
    }

    messages = build_planner_messages(
        goal="test",
        tools_registry=[],
        flow_state=flow_state,
        history=[],
        validation_errors=[],
    )
    user_payload = json.loads(messages[1]["content"])

    assert markdown not in messages[1]["content"]
    assert user_payload["flow_state"]["report_built"] is True
    assert user_payload["flow_state"]["completed_steps"][0]["tool"] == (
        "build_orchestration_report"
    )


def test_state_reference_resolves_from_full_internal_state() -> None:
    action = PlannerAction(
        action="call_tool",
        server="storage",
        tool="save_markdown_file",
        arguments={
            "filename": "final-orchestration-report.md",
            "content": {"$state": "report.orchestration_report.markdown"},
        },
    )
    flow_state = {"report": {"orchestration_report": {"markdown": "# Full report"}}}

    resolved = resolve_action_state_references(action, flow_state)

    assert resolved.arguments == {
        "filename": "final-orchestration-report.md",
        "content": "# Full report",
    }


def test_saved_state_projection_is_hydrated_without_report_markdown() -> None:
    action = PlannerAction(
        action="call_tool",
        server="storage",
        tool="save_json_file",
        arguments={
            "filename": "saved-flow-state.json",
            "data": {"$projection": "saved_flow_state"},
        },
    )
    flow_state = {
        "tracker": {"search_done": {"issue_count": 1}},
        "knowledge": {"day-20": {"title": "Orchestration MCP"}},
        "report": {
            "orchestration_report": {"title": "Report", "markdown": "# Full report"},
            "next_steps": {"steps": ["publish evidence"]},
        },
        "storage": {"final-orchestration-report.md": {"saved": True}},
        "counts_by_server": {"storage": 1},
        "counts_by_tool": {"storage.save_markdown_file": 1},
        "servers_used": ["tracker", "knowledge", "report", "storage"],
        "tool_calls_total": 10,
    }

    resolved = resolve_action_state_references(action, flow_state)

    assert resolved.arguments is not None
    saved_state = resolved.arguments["data"]
    assert {
        "tracker",
        "knowledge",
        "report_summary",
        "saved_files",
        "counts_by_server",
        "counts_by_tool",
        "servers_used",
        "final_success_flags",
    }.issubset(saved_state)
    assert "markdown" not in saved_state["report_summary"]["orchestration_report"]
    assert saved_state["report_summary"]["orchestration_report"]["title"] == "Report"
    assert saved_state["saved_files"] == flow_state["storage"]


def test_storage_path_safety() -> None:
    assert validate_storage_filename("report.md", suffix=".md") == "report.md"
    assert validate_storage_filename("state.json", suffix=".json") == "state.json"
    for filename in ("/tmp/report.md", "../report.md", "nested/report.md", ".", ""):
        with pytest.raises(ValueError):
            validate_storage_filename(filename, suffix=".md")
    with pytest.raises(ValueError, match="suffix"):
        validate_storage_filename("report.txt", suffix=".md")


def test_ordered_chain_accepts_valid_extra_calls() -> None:
    steps = [
        {"server": "tracker", "tool": "search_tracker_issues"},
        {"server": "tracker", "tool": "get_tracker_issue"},
        {"server": "knowledge", "tool": "get_mcp_day_context"},
        {"server": "tracker", "tool": "search_tracker_issues"},
        {"server": "report", "tool": "build_orchestration_report"},
        {"server": "report", "tool": "build_next_steps"},
        {"server": "storage", "tool": "save_markdown_file"},
        {"server": "storage", "tool": "save_json_file"},
    ]
    assert has_required_ordered_chain(steps)


def test_scripted_planner_routes_long_flow_and_writes_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    result = asyncio.run(
        run_orchestration_via_mcp(
            planner=ScriptedJsonPlanner(),
            output_dir=output_dir,
            timeout_seconds=30,
            max_steps=15,
        )
    )

    assert result.completed is True
    assert len(result.steps) == 11
    assert result.flow_state["servers_used"] == list(SERVER_IDS)
    assert result.required_chain_found is True
    assert all(item["valid"] is True for item in result.routing_decisions)
    assert all(
        item["requested_server"] == item["resolved_session"] for item in result.routing_decisions
    )
    assert (output_dir / "final-orchestration-report.md").exists()
    assert (output_dir / "saved-flow-state.json").exists()
    report_markdown = (output_dir / "final-orchestration-report.md").read_text(encoding="utf-8")
    assert "Registered servers: `knowledge`, `report`, `storage`, `tracker`" in report_markdown
    assert "Data sources used before report generation: `tracker`, `knowledge`" in report_markdown
    assert "generated by the `report` MCP server" in report_markdown
    assert "persisted through the `storage` MCP server" in report_markdown
    storage_steps = [step for step in result.steps if step["server"] == "storage"]
    assert [step["tool"] for step in storage_steps] == [
        "save_markdown_file",
        "save_json_file",
    ]

    results_file = tmp_path / "results" / "day-20-mcp-orchestration.md"
    write_orchestration_outputs(result, output_dir, results_file)
    trace = json.loads((output_dir / "orchestration-trace.json").read_text())
    routing = json.loads((output_dir / "routing-decisions.json").read_text())
    tools = json.loads((output_dir / "tools-registry.json").read_text())
    assert trace["model_specific_tool_calling"] is False
    assert trace["hardcoded_pipeline"] is False
    assert trace["tool_calls_total"] == 11
    assert trace["servers_used"] == list(SERVER_IDS)
    assert len(routing["decisions"]) == 11
    assert {item["server_id"] for item in tools["tools"]} == set(SERVER_IDS)
    assert "scripted planner" in results_file.read_text(encoding="utf-8")


def test_planner_response_failure_is_repaired_within_bounded_loop(tmp_path: Path) -> None:
    planner = OneTransientFailurePlanner()

    result = asyncio.run(
        run_orchestration_via_mcp(
            planner=planner,
            output_dir=tmp_path / "artifacts",
            timeout_seconds=30,
            max_steps=18,
        )
    )

    assert result.completed is True
    assert len(result.steps) == 11
    assert planner.turns == 13
    assert result.flow_state["validation_errors"] == [
        "Planner turn 1: transient empty JSON content"
    ]

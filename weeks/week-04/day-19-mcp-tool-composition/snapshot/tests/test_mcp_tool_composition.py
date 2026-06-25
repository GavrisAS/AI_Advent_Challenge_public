from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest

from ai_advent_agent.mcp_composition_client import (
    COMPOSITION_REPORT_TOOL_NAME,
    COMPOSITION_SAVE_TOOL_NAME,
    COMPOSITION_SEARCH_TOOL_NAME,
    COMPOSITION_TOOL_NAMES,
    DEFAULT_MCP_COMPOSITION_GOAL,
    CompositionToolTraceEntry,
    ScriptedToolPlanner,
    build_llm_planner_from_env,
    build_pipeline_result,
    parse_tool_calling_response,
    run_composition_demo_via_mcp,
)
from ai_advent_agent.mcp_composition_server import (
    build_tracker_report,
    search_tracker_issues,
    validate_safe_filename,
)
from ai_advent_agent.scenarios import parse_args, scenario_mcp_tool_composition_demo


def test_search_tracker_issues_returns_filtered_mock_issues() -> None:
    result = search_tracker_issues(status="done", priority=None, query="Week 04", limit=10)

    assert result["query"] == {
        "status": "done",
        "priority": None,
        "query": "Week 04",
        "limit": 10,
    }
    assert result["issue_count"] == 3
    assert [issue["issue_key"] for issue in result["issues"]] == ["AI-16", "AI-17", "AI-18"]


def test_build_tracker_report_counts_and_markdown() -> None:
    search_result = search_tracker_issues(status="done", priority=None, query="Week 04", limit=10)

    report = build_tracker_report(
        issues=search_result["issues"],
        report_title="Week 04 MCP progress report",
    )

    assert report["title"] == "Week 04 MCP progress report"
    assert report["issue_count"] == 3
    assert report["status_counts"] == {"done": 3}
    assert report["priority_counts"] == {"high": 1, "medium": 2}
    assert "# Week 04 MCP progress report" in report["markdown"]
    assert "`AI-17`" in report["markdown"]
    assert "## Итог" in report["markdown"]


def test_save_report_filename_guard_rejects_unsafe_paths() -> None:
    assert validate_safe_filename("tracker-composition-report.md") == (
        "tracker-composition-report.md"
    )

    for filename in ["../report.md", "/tmp/report.md", "nested/report.md", "", "."]:
        with pytest.raises(ValueError):
            validate_safe_filename(filename)


def test_cli_mcp_tool_composition_defaults_and_overrides(tmp_path: Path) -> None:
    defaults = parse_args(["mcp-tool-composition-demo"])
    assert defaults.planner == "scripted"
    assert defaults.goal == DEFAULT_MCP_COMPOSITION_GOAL
    assert defaults.server_timeout_seconds == 30.0
    assert defaults.max_planner_steps == 8

    parsed = parse_args(
        [
            "mcp-tool-composition-demo",
            "--planner",
            "llm",
            "--goal",
            "custom goal",
            "--server-timeout-seconds",
            "12",
            "--max-planner-steps",
            "4",
            "--model",
            "deepseek-test",
            "--api-url",
            "https://example.com/chat/completions",
            "--temperature",
            "0.2",
            "--max-tokens",
            "500",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--results-file",
            str(tmp_path / "result.md"),
        ]
    )
    assert parsed.planner == "llm"
    assert parsed.goal == "custom goal"
    assert parsed.server_timeout_seconds == 12
    assert parsed.max_planner_steps == 4
    assert parsed.model == "deepseek-test"
    assert parsed.api_url == "https://example.com/chat/completions"
    assert parsed.temperature == 0.2
    assert parsed.max_tokens == 500
    assert parsed.output_dir == tmp_path / "artifacts"
    assert parsed.results_file == tmp_path / "result.md"


def test_mcp_composition_server_exposes_exact_tools_and_schemas(tmp_path: Path) -> None:
    result = asyncio.run(
        run_composition_demo_via_mcp(
            planner=ScriptedToolPlanner(),
            output_dir=tmp_path / "artifacts",
            timeout_seconds=10,
        )
    )

    tools = {tool.name: tool for tool in result.tools}
    assert tuple(sorted(tools)) == tuple(sorted(COMPOSITION_TOOL_NAMES))

    search_schema = tools[COMPOSITION_SEARCH_TOOL_NAME].input_schema
    assert search_schema["type"] == "object"
    search_properties = cast(dict[str, dict[str, Any]], search_schema["properties"])
    assert {"status", "priority", "query", "limit"}.issubset(search_properties)
    assert search_properties["limit"]["default"] == 10

    report_schema = tools[COMPOSITION_REPORT_TOOL_NAME].input_schema
    report_properties = cast(dict[str, dict[str, Any]], report_schema["properties"])
    assert report_schema["required"] == ["issues"]
    assert {"issues", "report_title"}.issubset(report_properties)

    save_schema = tools[COMPOSITION_SAVE_TOOL_NAME].input_schema
    save_properties = cast(dict[str, dict[str, Any]], save_schema["properties"])
    assert save_schema["required"] == ["markdown"]
    assert {"markdown", "filename"}.issubset(save_properties)


def test_scripted_planner_uses_generic_loop_and_produces_expected_sequence(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"

    result = asyncio.run(
        run_composition_demo_via_mcp(
            planner=ScriptedToolPlanner(),
            output_dir=output_dir,
            timeout_seconds=10,
        )
    )

    assert [entry.tool_name for entry in result.tool_trace] == list(COMPOSITION_TOOL_NAMES)
    assert result.trace_dict()["hardcoded_pipeline"] is False
    assert result.trace_dict()["planner"] == "scripted"
    assert result.pipeline_result["completed"] is True
    assert result.pipeline_result["required_chain_found"] is True
    assert result.pipeline_result["save_completed"] is True
    assert result.pipeline_result["tool_count"] == 3
    assert result.pipeline_result["issue_count"] == 3
    assert result.pipeline_result["report_sha256"]
    report_path = Path(cast(str, result.pipeline_result["report_path"]))
    assert report_path.parent == output_dir
    assert report_path.name == "tracker-composition-report.md"
    assert report_path.exists()
    assert "# Week 04 MCP progress report" in report_path.read_text(encoding="utf-8")


def test_scenario_creates_required_artifacts_and_results(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    results_file = tmp_path / "results" / "day-19-mcp-tool-composition.md"

    scenario_mcp_tool_composition_demo(
        planner_mode="scripted",
        goal=DEFAULT_MCP_COMPOSITION_GOAL,
        output_dir=output_dir,
        results_file=results_file,
        server_timeout_seconds=10,
        max_planner_steps=8,
        model="deepseek-v4-flash",
        api_url="https://example.com/chat/completions",
        temperature=0.0,
        max_tokens=1200,
    )

    tools_payload = json.loads((output_dir / "tools-list.json").read_text(encoding="utf-8"))
    trace_payload = json.loads(
        (output_dir / "llm-tool-call-trace.json").read_text(encoding="utf-8")
    )
    pipeline_payload = json.loads((output_dir / "pipeline-result.json").read_text(encoding="utf-8"))
    report_markdown = (output_dir / "tracker-composition-report.md").read_text(encoding="utf-8")
    final_answer = (output_dir / "final-agent-answer.md").read_text(encoding="utf-8")
    results_markdown = results_file.read_text(encoding="utf-8")

    assert [tool["name"] for tool in tools_payload["tools"]] == [
        COMPOSITION_REPORT_TOOL_NAME,
        COMPOSITION_SAVE_TOOL_NAME,
        COMPOSITION_SEARCH_TOOL_NAME,
    ]
    assert trace_payload["hardcoded_pipeline"] is False
    assert [step["tool_name"] for step in trace_payload["tool_call_sequence"]] == list(
        COMPOSITION_TOOL_NAMES
    )
    assert trace_payload["tool_call_sequence"][1]["arguments"]["issues"] == [
        "AI-16",
        "AI-17",
        "AI-18",
    ]
    assert pipeline_payload["completed"] is True
    assert pipeline_payload["planner"] == "scripted"
    assert pipeline_payload["required_chain_found"] is True
    assert pipeline_payload["save_completed"] is True
    assert pipeline_payload["tool_sequence"] == list(COMPOSITION_TOOL_NAMES)
    assert "AI-17" in report_markdown
    assert "Пайплайн MCP tools завершён" in final_answer
    assert "Передача данных между tools" in results_markdown
    assert "save_report_to_file" in results_markdown


def test_pipeline_result_accepts_adaptive_llm_search_attempts() -> None:
    trace_entries = [
        CompositionToolTraceEntry(
            step=1,
            requested_by="llm",
            tool_name=COMPOSITION_SEARCH_TOOL_NAME,
            arguments={"status": "done", "query": "nonexistent", "limit": 10},
            result_summary={"issue_count": 0, "issues": []},
        ),
        CompositionToolTraceEntry(
            step=2,
            requested_by="llm",
            tool_name=COMPOSITION_SEARCH_TOOL_NAME,
            arguments={"status": "done", "query": "MCP", "limit": 10},
            result_summary={"issue_count": 3, "issues": ["AI-16", "AI-17", "AI-18"]},
        ),
        CompositionToolTraceEntry(
            step=3,
            requested_by="llm",
            tool_name=COMPOSITION_REPORT_TOOL_NAME,
            arguments={"issues": ["AI-16", "AI-17", "AI-18"]},
            result_summary={
                "issue_count": 3,
                "status_counts": {"done": 3},
                "priority_counts": {"high": 1, "medium": 2},
                "markdown_length": 700,
            },
        ),
        CompositionToolTraceEntry(
            step=4,
            requested_by="llm",
            tool_name=COMPOSITION_SAVE_TOOL_NAME,
            arguments={"filename": "tracker-composition-report.md"},
            result_summary={
                "saved": True,
                "path": "artifacts/tracker-composition-report.md",
                "bytes_written": 900,
                "sha256": "abc",
            },
        ),
    ]

    result = build_pipeline_result(trace_entries, planner="llm")

    assert result["completed"] is True
    assert result["planner"] == "llm"
    assert result["requested_by"] == "llm"
    assert result["required_chain_found"] is True
    assert result["save_completed"] is True
    assert result["issue_count"] == 3
    assert result["tool_sequence"] == [
        COMPOSITION_SEARCH_TOOL_NAME,
        COMPOSITION_SEARCH_TOOL_NAME,
        COMPOSITION_REPORT_TOOL_NAME,
        COMPOSITION_SAVE_TOOL_NAME,
    ]


def test_llm_planner_missing_key_is_explicit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    with pytest.raises(Exception, match="DEEPSEEK_API_KEY"):
        build_llm_planner_from_env(
            model="deepseek-v4-flash",
            api_url="https://example.com/chat/completions",
            temperature=0.0,
            max_tokens=100,
            timeout_seconds=5,
        )


def test_tool_calling_response_parser_accepts_deepseek_compatible_shape() -> None:
    response = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": COMPOSITION_SEARCH_TOOL_NAME,
                                "arguments": json.dumps(
                                    {"status": "done", "query": "Week 04", "limit": 10}
                                ),
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    parsed = parse_tool_calling_response(
        response_body=json.dumps(response),
        model="deepseek-v4-flash",
        elapsed_seconds=0.1,
    )

    assert parsed.finish_reason == "tool_calls"
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == COMPOSITION_SEARCH_TOOL_NAME
    assert parsed.tool_calls[0].arguments["query"] == "Week 04"
    assert parsed.usage["total_tokens"] == 15

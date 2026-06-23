# Day 17 — Первый MCP Tool

Сценарий выполнен локально через stdio MCP server, без внешней сети, API key и LLM API.

## MCP server и tool

- Server: `AI Advent Mock Tracker 1.28.0`
- Transport: `stdio`
- Protocol version: `2025-11-25`
- MCP Python SDK: `1.28.0`
- Tool: `get_tracker_issue`
- Arguments: `issue_key=AI-17`, `include_comments=True`
- Timestamp UTC: `2026-06-23T12:56:14Z`

| Tool | Description |
|---|---|
| `get_tracker_issue` | Return a mock tracker issue by key. Args: issue_key: Issue key, for example AI-17. include_comments: Whether to include issue comments in the result. |

## Полученный результат

- Key: `AI-17`
- Title: Подключить первый MCP tool
- Status: `in_progress`
- Priority: `high`
- Assignee: `student`
- Comments returned: `2`

## Как агент использовал результат

Агентский слой сформировал Markdown-резюме задачи, выделил статус, приоритет, исполнителя и
следующее действие. Итог сохранён в `agent-used-tool-result.md`.

Next action: keep the local stdio MCP tool integration read-only, documented, and ready for extension in Day 18.

## Артефакты

JSON и Markdown outputs сформированы в `weeks/week-04/day-17-first-mcp-tool/artifacts`:

- `tools-list.json`
- `mcp-tool-call-result.json`
- `agent-used-tool-result.md`

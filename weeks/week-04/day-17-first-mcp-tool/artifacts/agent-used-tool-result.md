# MCP Tool Result Used by Agent

Agent called `get_tracker_issue` for `AI-17` through the local MCP server.

## Issue

- Key: AI-17
- Title: Подключить первый MCP tool
- Status: in_progress
- Priority: high
- Assignee: student

## Summary

Реализовать локальный stdio MCP server поверх mock Tracker API и вызвать его из агента.

## Comments

- mentor: Сфокусироваться на registration, input schema и call_tool без реального внешнего API.
- student: Использовать read-only tool и сохранить воспроизводимые artifacts.

## Agent conclusion

The next action is to keep the local stdio MCP tool integration read-only, documented, and ready for extension in Day 18.

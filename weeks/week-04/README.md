# Week 04 — MCP

## Статус

🚧 in_progress

## Ключевая тема недели

Четвёртая неделя посвящена Model Context Protocol: стандартному слою между AI host и внешними
сервисами. Основные вопросы — устройство MCP client/server, tools и schemas, JSON-RPC, transports,
безопасность, token overhead и выбор между MCP и Skill + CLI.

## Цели недели

- Познакомиться с архитектурой и назначением MCP.
- Научиться подключать MCP для публичных tools.
- Разобраться в оркестрации нескольких MCP tools внутри собственного агента.
- Проверить применение MCP в реальной рабочей задаче.
- Сравнить MCP со Skill + CLI по стоимости контекста и удобству эксплуатации.

## Что важно проверить на практике

- Remote MCP client с initialization и tool discovery через Streamable HTTP.
- Локальный MCP server со stdio transport и небольшим read-only tool в следующих заданиях.
- Корректность tool schema, validation и обработки ошибок.
- Разницу между JSON-RPC и transport.
- Token flow: sampling calls, schema weight, tool results, idle overhead и batching.
- Ограничение прав, подтверждение критических операций и защиту от prompt injection.
- Один и тот же сценарий через MCP и Skill + CLI.

## Связь с предыдущими неделями

Week 01 дала основы prompting и LLM API. Week 02 добавила tools, persistence, token accounting и
управление контекстом. Week 03 собрала memory layers, user profile, task state и invariants.
Week 04 переносит эти механизмы на взаимодействие агента с внешними системами и делает стоимость
tool orchestration отдельным объектом измерения.

## Задания недели

| День | Тема | Статус | Папка |
|---|---|---|---|
| day-16 | MCP Connection | ✅ done | [day-16-mcp-connection](day-16-mcp-connection/) |
| day-17 | First MCP Tool | ✅ done | [day-17-first-mcp-tool](day-17-first-mcp-tool/) |

Day 16 реализован через публичный DeepWiki MCP: Streamable HTTP, initialization и `tools/list` без
API key, LLM и вызова tools. Day 17 реализован как локальный stdio MCP server поверх mock Tracker
API: зарегистрирован read-only tool `get_tracker_issue`, приложение получает `tools/list`,
вызывает `call_tool` и использует structured result в Markdown artifact. Задания Day 18–20 пока не
выданы.

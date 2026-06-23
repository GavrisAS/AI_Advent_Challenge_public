# Day 16 — MCP Connection

Выполнено реальное remote-подключение без API key и без LLM-вызовов.

## Соединение

- Server URL: `https://mcp.deepwiki.com/mcp`
- Transport: `streamable-http`
- Initialization: успешно
- Protocol version: `2025-11-25`
- Server: `DeepWiki 2.14.3`
- MCP Python SDK: `1.28.0`
- Timestamp UTC: `2026-06-23T04:47:18Z`
- Tools вызывались: нет, выполнен только discovery через `tools/list`

## Проверка tools

- Ожидаемые: `ask_question`, `read_wiki_contents`, `read_wiki_structure`
- Фактические: `ask_question`, `read_wiki_contents`, `read_wiki_structure`
- Все ожидаемые присутствуют: `True`
- Отсутствующие ожидаемые: нет
- Дополнительные: нет

| Tool | Description |
|---|---|
| `ask_question` | Ask any question about a GitHub repository and get an AI-powered, context-grounded response. Args: repoName: GitHub repository or list of repositories (max 10) in owner/repo format question: The question to ask about the repository |
| `read_wiki_contents` | View documentation about a GitHub repository. Args: repoName: GitHub repository in owner/repo format (e.g. "facebook/react") |
| `read_wiki_structure` | Get a list of documentation topics for a GitHub repository. Args: repoName: GitHub repository in owner/repo format (e.g. "facebook/react") |

## Артефакты

JSON-файлы сформированы в `../artifacts/snapshot-run`:

- `mcp-connection-result.json`
- `tools-list.json`

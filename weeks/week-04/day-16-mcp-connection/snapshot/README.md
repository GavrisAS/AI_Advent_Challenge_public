# Snapshot Day 16 — MCP Connection

Самодостаточная версия remote MCP-клиента Day 16. Snapshot подключается к DeepWiki MCP через
Streamable HTTP, выполняет initialization и `tools/list`, но не вызывает tools и LLM API.

API key не требуется. Для online-сценария нужен доступ к интернету.

## Offline-проверки

```bash
uv run pytest
uv run ruff check .
uv run ty check
```

Remote integration test по умолчанию пропущен. Явный запуск:

```bash
AI_ADVENT_RUN_MCP_INTEGRATION=1 uv run pytest tests/test_mcp_connection.py
```

## Online-сценарий

Из каталога `snapshot/`:

```bash
uv run ai-advent-scenarios mcp-connection-demo \
  --server-url https://mcp.deepwiki.com/mcp \
  --output-dir ../artifacts/snapshot-run \
  --results-file ../results/day-16-mcp-connection-snapshot.md
```

Runtime-файлы сохраняются вне snapshot.

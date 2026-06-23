# Snapshot Day 17 — First MCP Tool

Самодостаточная версия Day 17. Snapshot запускает локальный stdio MCP server, публикует
read-only tool `get_tracker_issue`, вызывает его через MCP client и сохраняет artifacts/results
за пределами `snapshot/`.

API key, LLM API и интернет не требуются.

## Проверки

```bash
uv sync
uv run python -m pytest -q
uv run ruff check .
uv run ty check
```

## Offline-сценарий

Из каталога `snapshot/`:

```bash
uv run ai-advent-scenarios mcp-tool-demo \
  --issue-key AI-17 \
  --include-comments \
  --output-dir ../artifacts \
  --results-file ../results/day-17-first-mcp-tool.md
```

Runtime-файлы сохраняются вне `snapshot/`.

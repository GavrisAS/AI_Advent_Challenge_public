# Day 19 Snapshot — MCP Tool Composition

Самодостаточный snapshot кода Day 19. Он показывает LLM-driven composition pattern через
generic MCP tool-calling loop и локальный stdio MCP server с deterministic tools.

## Offline запуск

API key и интернет не требуются:

```bash
uv sync
uv run python -m pytest -q
uv run ai-advent-scenarios mcp-tool-composition-demo \
  --planner scripted \
  --output-dir .tmp/day19-scripted-fallback/artifacts \
  --results-file .tmp/day19-scripted-fallback/day-19-mcp-tool-composition.md
```

## LLM-driven запуск

Требуется `DEEPSEEK_API_KEY` в env или `.env`:

```bash
uv run ai-advent-scenarios mcp-tool-composition-demo \
  --planner llm \
  --goal "Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл." \
  --output-dir ../artifacts \
  --results-file ../results/day-19-mcp-tool-composition.md
```

## Состав

```text
src/ai_advent_agent/
├── config.py
├── env.py
├── mcp_composition_client.py
├── mcp_composition_server.py
├── mcp_mock_api.py
├── mcp_tool_client.py
└── scenarios.py
tests/
└── test_mcp_tool_composition.py
```

`save_report_to_file` сохраняет файлы только в configured output directory и запрещает unsafe
filename: абсолютные пути, `..` и path separators.

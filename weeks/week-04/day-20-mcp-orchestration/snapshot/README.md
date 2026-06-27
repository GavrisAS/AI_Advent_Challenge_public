# Snapshot Day 20 — Orchestration MCP

Самодостаточная версия четырёх локальных stdio MCP servers, neutral JSON planner, registry/router,
evidence writer и offline tests на момент сдачи Day 20.

## Offline

API key и сеть не нужны. Scripted outputs пишутся только в локальную `.tmp/` snapshot-а и не
заменяют основные Day 20 artifacts/results.

```bash
cd weeks/week-04/day-20-mcp-orchestration/snapshot
uv sync --locked --all-groups
uv run pytest -q
uv run ai-advent-scenarios mcp-orchestration-demo \
  --planner scripted \
  --output-dir .tmp/day20-scripted-fallback/artifacts \
  --results-file .tmp/day20-scripted-fallback/day-20-mcp-orchestration.md
```

## Online llm-json

Требуется `DEEPSEEK_API_KEY`. Это full scenario для видео: он намеренно записывает основные Day 20
artifacts/results в каталоги рядом со snapshot. Planner получает MCP registry как текст и
возвращает обычный JSON action; provider-native function calling не используется как control plane.
JSON response mode остаётся adapter-level удобством и не меняет переносимый planner/router contract.
Planner-facing state компактируется, а крупные значения передаются нейтральными
`$state`/`$projection` references и разворачиваются host-ом перед MCP call; full evidence при этом
не сокращается.

```bash
cd weeks/week-04/day-20-mcp-orchestration/snapshot
uv sync --locked --all-groups
uv run ai-advent-scenarios mcp-orchestration-demo \
  --planner llm-json \
  --goal "Собери большой итоговый отчёт по MCP Week 04: найди выполненные и планируемые MCP-задачи, получи контекст Day 18, Day 19 и Day 20, добавь best practices по multi-server orchestration и model-agnostic planning, собери отчёт и сохрани Markdown и JSON состояние через storage MCP server." \
  --output-dir ../artifacts \
  --results-file ../results/day-20-mcp-orchestration.md \
  --server-timeout-seconds 360 \
  --max-steps 18
```

`--server-timeout-seconds` ограничивает весь orchestration lifecycle: MCP startup, planner loop и
tool calls. Это не только timeout запуска server subprocess.

Этой командой получен финальный evidence: 11 MCP tool calls через четыре server-а,
`required_chain_found=true`, `completed=true`.

Другие online-пробные запуски направляйте в `.tmp/`; основные paths выше используйте только для
явного финального video run. Snapshot не содержит committed `.venv`, caches, secrets и generated
artifacts/results.

# Day 19 — Композиция MCP-инструментов

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1kn6FuQ6hhccJEjwA2RtJe93IGpV2HlHk)

## Исходное условие

🔥 День 19. Композиция MCP-инструментов

Создайте несколько MCP-инструментов, например:

👉 search
👉 summarize
👉 saveToFile

Реализуйте пайплайн:

👉 первый инструмент получает данные
👉 второй — обрабатывает
👉 третий — сохраняет результат

Проверьте:

👉 автоматическое выполнение цепочки
👉 корректность передачи данных между инструментами

Результат:

Автоматический пайплайн из нескольких MCP-инструментов

Формат:

Видео + Код

## Цель задания

Показать не просто последовательный вызов трёх функций, а LLM-driven composition: host получает
schemas MCP tools, отдаёт их planner/model, исполняет только возвращённые model tool calls через
`session.call_tool(...)` и сохраняет trace, доказывающий, что основной сценарий не содержит
захардкоженного fixed pipeline.

Важное уточнение преподавателя: `summarize` здесь означает отчёт / итог / обработку данных, а не
LLM-суммаризацию внутри MCP tool. Поэтому второй tool называется `build_tracker_report` и строит
детерминированный Markdown report без вызова модели.

## Реализация

Статус: `✅ done`.

Day 19 добавляет отдельный локальный stdio MCP server `AI Advent MCP Tool Composition` с тремя
deterministic tools:

- `search_tracker_issues` — ищет задачи в mock Tracker API по `status`, `priority`, `query` и
  `limit`;
- `build_tracker_report` — принимает `issues`, считает статусы/приоритеты и строит Markdown report;
- `save_report_to_file` — принимает Markdown и безопасное имя файла, сохраняет отчёт внутри
  configured artifacts/output directory и возвращает `bytes_written` плюс `sha256`.

Архитектурный flow:

```text
LLM planner -> generic MCP client loop -> stdio MCP server -> deterministic tools
```

Основной client loop делает `initialize()`, `list_tools()`, конвертирует MCP `inputSchema` в
Chat Completions `tools`, получает `tool_calls` от planner-а, исполняет их через
`session.call_tool(...)`, возвращает tool result обратно в conversation и повторяет цикл до
финального ответа без новых tool calls.

Основной production/demo режим `--planner llm` использует DeepSeek-compatible Chat Completions API
и не подменяется на scripted при отсутствии `DEEPSEEK_API_KEY`. Режим `--planner scripted` оставлен
только как deterministic test/offline fallback и проходит через тот же generic execution loop.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios mcp-tool-composition-demo` | Запустить локальный stdio MCP server и generic planner loop для композиции tools |
| `--planner {llm,scripted}` | Выбрать LLM planner или deterministic scripted planner |
| `--goal TEXT` | Natural-language цель planner-а |
| `--output-dir PATH` | Каталог artifacts и output directory для `save_report_to_file` |
| `--results-file PATH` | Markdown result report |
| `--server-timeout-seconds N` | Общий timeout startup, planner loop и MCP tool calls |
| `--max-planner-steps N` | Лимит planner turns, default `8` |
| `--model NAME` | Model для `--planner llm`, default из `DEEPSEEK_MODEL` или проекта |
| `--api-url URL` | DeepSeek-compatible Chat Completions endpoint |
| `--temperature N` | Температура planner-а, default `0.0` |
| `--max-tokens N` | Лимит completion tokens для planner-а |

Новых slash-команд интерактивного агента нет.

## Структура файлов

```text
weeks/week-04/day-19-mcp-tool-composition/
├── README.md
├── artifacts/
│   ├── final-agent-answer.md
│   ├── llm-tool-call-trace.json
│   ├── pipeline-result.json
│   ├── tools-list.json
│   └── tracker-composition-report.md
├── results/
│   └── day-19-mcp-tool-composition.md
└── snapshot/
    ├── .env.example
    ├── README.md
    ├── pyproject.toml
    ├── uv.lock
    ├── src/ai_advent_agent/
    │   ├── __init__.py
    │   ├── config.py
    │   ├── env.py
    │   ├── mcp_composition_client.py
    │   ├── mcp_composition_server.py
    │   ├── mcp_mock_api.py
    │   ├── mcp_tool_client.py
    │   └── scenarios.py
    └── tests/test_mcp_tool_composition.py
```

Актуальный код находится в `packages/ai_advent_agent/src/ai_advent_agent/`:

- `mcp_composition_server.py`;
- `mcp_composition_client.py`;
- routing в `scenarios.py`;
- tests в `packages/ai_advent_agent/tests/test_mcp_tool_composition.py`.

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Offline fallback не требует интернета, API key, реального Tracker API или LLM API. Он нужен для
tests/local checks и не является основным evidence Day 19. Чтобы не перезаписывать online artifacts,
сохраняйте scripted output в `.tmp/...`.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-tool-composition-demo \
  --planner scripted \
  --output-dir .tmp/day19-scripted-fallback \
  --results-file .tmp/day19-scripted-fallback/day-19-mcp-tool-composition.md
```

Тесты Day 19:

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_tool_composition.py -q
```

#### Online/interactive агент

Основной LLM-driven demo требует `DEEPSEEK_API_KEY` в env или `.env`. Именно этот запуск создаёт
final Day 19 artifacts/results.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-tool-composition-demo \
  --planner llm \
  --goal "Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл." \
  --output-dir weeks/week-04/day-19-mcp-tool-composition/artifacts \
  --results-file weeks/week-04/day-19-mcp-tool-composition/results/day-19-mcp-tool-composition.md
```

### Snapshot Day 19

#### Offline-сценарий

```bash
cd weeks/week-04/day-19-mcp-tool-composition/snapshot
uv sync
uv run python -m pytest -q
uv run ai-advent-scenarios mcp-tool-composition-demo \
  --planner scripted \
  --output-dir ../artifacts \
  --results-file ../results/day-19-mcp-tool-composition.md
```

API key и интернет не требуются. Runtime-файлы сохраняются вне `snapshot/`.

#### Online/interactive агент

LLM-driven snapshot запуск требует `DEEPSEEK_API_KEY`:

```bash
cd weeks/week-04/day-19-mcp-tool-composition/snapshot
mkdir -p ../artifacts/llm-demo

uv run ai-advent-scenarios mcp-tool-composition-demo \
  --planner llm \
  --goal "Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл." \
  --output-dir ../artifacts/llm-demo \
  --results-file ../artifacts/llm-demo/day-19-mcp-tool-composition.md
```

## Сценарий демонстрации для видео

1. Показать цель Day 19: LLM-driven composition of MCP tools, где LLM выбирает tool calls, а host
   только исполняет их через MCP session.
2. Открыть `mcp_composition_server.py` и показать MCP tools `search_tracker_issues`,
   `build_tracker_report`, `save_report_to_file`.
3. Показать, что `build_tracker_report` строит deterministic report и не вызывает LLM.
4. Открыть `mcp_composition_client.py`: показать generic loop `initialize -> list_tools -> planner
   tool_calls -> session.call_tool -> tool result -> planner`.
5. Показать, что agent scenario не содержит hardcoded `search -> build -> save` sequence из прямых
   `await call_tool(...)`.
6. Показать наличие `DEEPSEEK_API_KEY` без вывода значения ключа, например только статусом
   `env-present` или `dotenv-present`.
7. Запустить online scenario:

   ```bash
   uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-tool-composition-demo \
     --planner llm \
     --goal "Найди завершённые MCP-задачи Week 04, собери итоговый отчёт и сохрани его в файл." \
     --output-dir weeks/week-04/day-19-mcp-tool-composition/artifacts \
     --results-file weeks/week-04/day-19-mcp-tool-composition/results/day-19-mcp-tool-composition.md
   ```

8. Открыть `artifacts/llm-tool-call-trace.json` и показать `planner=llm`, `requested_by=llm`,
   `llm_api_calls > 0`, `hardcoded_pipeline=false` и последовательность MCP tool calls.
9. Открыть `artifacts/pipeline-result.json` и показать `completed=true`,
   `required_chain_found=true`, `issue_count=3` и `report_path`.
10. Открыть `artifacts/tracker-composition-report.md`: файл создан через MCP tool
    `save_report_to_file`.
11. Открыть `results/day-19-mcp-tool-composition.md`: показать итоговый online LLM-run report,
    timeline и доказательство передачи данных между tools.
12. Кратко сказать, что `--planner scripted` используется только для offline tests/local checks без
    API key.
13. Перейти в `snapshot/`, выполнить `uv sync`, `uv run python -m pytest -q` и snapshot scripted
    fallback, сохраняя runtime output вне `snapshot/`.

## Результаты

Фактический online LLM-run 2026-06-25 создал локальный stdio MCP server, получил tools через
`list_tools`, передал schemas LLM planner-у, исполнил requested MCP tool calls и сохранил report
file. LLM выбрала последовательность `search_tracker_issues -> build_tracker_report ->
save_report_to_file`; trace содержит `planner=llm`, `requested_by=llm`, `llm_api_calls=4`,
`required_chain_found=true`, `save_completed=true` и `issue_count=3`.

Проверенные файлы:

- [tools-list.json](artifacts/tools-list.json);
- [llm-tool-call-trace.json](artifacts/llm-tool-call-trace.json);
- [pipeline-result.json](artifacts/pipeline-result.json);
- [tracker-composition-report.md](artifacts/tracker-composition-report.md);
- [final-agent-answer.md](artifacts/final-agent-answer.md);
- [day-19-mcp-tool-composition.md](results/day-19-mcp-tool-composition.md).

## Выводы

Композиция MCP tools должна жить в planner/host loop, а не в одном giant tool и не в фиксированной
цепочке внутри сценария. MCP server остаётся deterministic executor-ом с маленькими tools и
понятными schemas, а host отвечает за discovery, LLM tool-calling loop, audit trace, timeouts и
безопасное исполнение requested tool calls.

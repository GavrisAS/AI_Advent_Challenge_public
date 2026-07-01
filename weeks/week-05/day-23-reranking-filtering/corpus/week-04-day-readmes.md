# Public README документов Week 04

Стабильная копия public-safe README завершённых дней для corpus Day 21.

<!-- source: weeks/week-04/day-16-mcp-connection/README.md -->

# Day 16 — Подключение MCP

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1nXpqM14I2XWKTjUzDJ35TkWR-d1hQVG6)

## Исходное условие

🔥 День 16. Подключение MCP

Установите MCP SDK / клиент (или поднимите MCP-сервер, если используете локальный вариант)

Сделайте минимальный код, который:

👉 устанавливает MCP-соединение
👉 получает от MCP список доступных инструментов

Проверьте:

👉 соединение устанавливается
👉 список инструментов корректно возвращается

Результат:

Код, который подключается к MCP и выводит список доступных инструментов

Формат:

Видео + Код

## Цель задания

Научиться подключать Python-клиент к публичному remote MCP server, выполнять protocol
initialization и получать список tools через discovery. Day 16 проверяет только транспорт и
`tools/list`: инструменты не вызываются, LLM API не используется, собственный MCP server не
создаётся.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-16-mcp-connection.md)

## Реализация

Статус: `✅ done`.

Для задания выбран публичный [DeepWiki MCP](https://docs.devin.ai/work-with-devin/deepwiki-mcp):

- endpoint: `https://mcp.deepwiki.com/mcp`;
- transport: Streamable HTTP;
- authentication и API key: не требуются;
- MCP Python SDK: `1.28.0`, dependency constraint `mcp>=1.28,<2`;
- ожидаемые tools: `ask_question`, `read_wiki_contents`, `read_wiki_structure`.

Модуль `mcp_connection.py` открывает Streamable HTTP transport, создаёт `ClientSession`, выполняет
`initialize()` и получает все страницы `list_tools()`. Метаданные каждого tool нормализуются в
стабильные поля `name`, `description`, `input_schema`, сортируются по имени и сохраняются в JSON.
Результат дополнительно содержит protocol/server/SDK versions, UTC timestamp и сравнение с
ожидаемым набором DeepWiki tools.

Ошибки DNS, connectivity, timeout, protocol и пустой список tools различаются. Неуспешный запуск
завершается с ненулевым exit code и создаёт только диагностический `mcp-connection-error.json` с
`connected=false`, а не успешный result report.

Собственный server, FastMCP, stdio transport, fake server, tool calls и LLM calls в реализации
отсутствуют.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios mcp-connection-demo` | Подключиться к remote MCP, выполнить initialization и вывести `tools/list` |
| `--server-url URL` | Переопределить Streamable HTTP endpoint |
| `--timeout-seconds N` | Задать общий timeout подключения и discovery; default `30` |
| `--output-dir PATH` | Выбрать каталог JSON-артефактов |
| `--results-file PATH` | Выбрать Markdown result report |

Новых slash-команд интерактивного агента нет.

## Структура файлов

```text
weeks/week-04/day-16-mcp-connection/
├── README.md
├── codex-log.md
├── snapshot/
│   ├── README.md
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/ai_advent_agent/
│   │   ├── __init__.py
│   │   ├── mcp_connection.py
│   │   └── scenarios.py
│   └── tests/test_mcp_connection.py
├── results/
│   ├── day-16-mcp-connection.md
│   └── day-16-mcp-connection-snapshot.md
└── artifacts/
    ├── mcp-connection-result.json
    ├── tools-list.json
    └── snapshot-run/
        ├── mcp-connection-result.json
        └── tools-list.json
```

Актуальный код находится в
`packages/ai_advent_agent/src/ai_advent_agent/mcp_connection.py`, CLI routing — в
`packages/ai_advent_agent/src/ai_advent_agent/scenarios.py`, тесты — в
`packages/ai_advent_agent/tests/test_mcp_connection.py`.

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Unit tests не требуют интернета, API key или LLM API. Day-specific CLI удалён из актуального
package; remote integration test по умолчанию пропускается.

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_connection.py
```

#### Online-сценарий

Отдельный online runner в актуальном package не предоставляется. Для исторического запуска
используйте `Snapshot Day 16`; direct remote API остаётся в `discover_mcp_tools(...)`.

Опциональный integration test:

```bash
AI_ADVENT_RUN_MCP_INTEGRATION=1 \
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_connection.py
```

### Snapshot Day 16

#### Offline-сценарий

```bash
cd weeks/week-04/day-16-mcp-connection/snapshot
uv run pytest
uv run ruff check .
uv run ty check
```

Remote test пропускается. API key и интернет для offline-проверок не требуются.

#### Online-сценарий

```bash
cd weeks/week-04/day-16-mcp-connection/snapshot
uv run ai-advent-scenarios mcp-connection-demo \
  --server-url https://mcp.deepwiki.com/mcp \
  --output-dir ../artifacts/snapshot-run \
  --results-file ../results/day-16-mcp-connection-snapshot.md
```

Runtime-файлы сохраняются за пределами `snapshot/`. Нужен интернет, API key не нужен.

## Сценарий демонстрации для видео

1. Показать `mcp_connection.py`, отсутствие server/FastMCP/tool-call/LLM-кода и dependency
   `mcp>=1.28,<2`.
2. Показать historical CLI help и параметры `mcp-connection-demo` внутри `Snapshot Day 16`.
3. Запустить offline unit tests; отметить пропущенный opt-in integration test.
4. Выполнить online-сценарий из `Snapshot Day 16` с output в `../artifacts/snapshot-run`.
5. Показать в терминале успешные initialization, protocol version, tool count и три имени tools.
6. Открыть `mcp-connection-result.json`, `tools-list.json` и Markdown report; подтвердить
   `connected=true`, отсутствие missing/extra tools и отсутствие tool calls.
7. Показать `make clean`, `make clean-venv`, `make clean-all`; для обычной очистки использовать
   только `make clean`, который не удаляет `.venv`.
8. После записи при необходимости удалить только временный `.tmp/day16-mcp-connection`; итоговые
   проверенные artifacts/results дня сохранить.

## Результаты

Реальный запуск 2026-06-23 установил соединение с `DeepWiki 2.14.3` по protocol version
`2025-11-25` через MCP Python SDK `1.28.0`. Получены ровно три ожидаемых tools:

- `ask_question`;
- `read_wiki_contents`;
- `read_wiki_structure`.

`missing_expected_tools` и `extra_tools` пусты. Инструменты не вызывались. LLM API calls: `0`.

Проверенные файлы:

- [полный connection result](artifacts/mcp-connection-result.json);
- [нормализованный tools list](artifacts/tools-list.json);
- [Markdown-отчёт](results/day-16-mcp-connection.md);
- [snapshot report](results/day-16-mcp-connection-snapshot.md).

## Выводы

Минимальный MCP-клиент может проверить совместимость remote server без LLM и без выполнения
инструментов: достаточно корректно пройти initialization и `tools/list`. Streamable HTTP endpoint
DeepWiki доступен без авторизации и возвращает документированный набор tools. Нормализация
метаданных и явная обработка ошибок делают результат воспроизводимым и пригодным для следующих
дней, где появятся собственный MCP server и вызовы tools.

<!-- source: weeks/week-04/day-17-first-mcp-tool/README.md -->

# Day 17 — Первый инструмент MCP

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1D68IeW-oiJxcMzp02rqsTBN2U7QzzaPa)

## Исходное условие

🔥 День 17. Первый инструмент MCP

Реализуйте свой MCP-сервер вокруг любого API (например: Яндекс.Трекер, Git, CRM, mock API)

Сделайте:

👉 регистрацию инструмента
👉 описание входных параметров
👉 возврат результата

Подключите инструмент к своему агенту и:

👉 вызовите его из приложения
👉 получите и используйте результат

Результат:

Агент делает вызов к MCP-инструменту и получает результат

Формат:

Видео + Код

## Цель задания

Отработать первый полный локальный MCP flow: собственный server, регистрация tool, публикация
input schema, запуск server-а как stdio subprocess, discovery через `list_tools`, вызов через
`call_tool` и использование результата в маленьком агентском сценарии.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-17-first-mcp-tool.md)

## Реализация

Статус: `✅ done`.

Day 17 продолжает Day 16, но меняет предмет проверки. Day 16 подключался к публичному remote
DeepWiki MCP и только получал список tools. Day 17 создаёт собственный локальный MCP server,
публикует один read-only tool и вызывает его из приложения.

Выбран mock Tracker API, а не реальный Яндекс.Трекер, Jira, GitHub или CRM. Это убирает OAuth,
secrets, rate limits, внешнюю сеть и нестабильность интеграции. Backend полностью deterministic:
в памяти есть задачи `AI-16`, `AI-17` и `AI-18`, ключи нормализуются к uppercase, неизвестный ключ
даёт контролируемую ошибку.

Transport выбран `stdio`, потому что server запускается как subprocess, не требует порта, не
нуждается в HTTP lifecycle и хорошо подходит для самодостаточного snapshot. Server не пишет обычные
сообщения в stdout: stdout занят MCP JSON-RPC protocol.

MCP server реализован через официальный Python SDK:

- `FastMCP("AI Advent Mock Tracker")`;
- tool `get_tracker_issue`;
- входные параметры `issue_key: str` и `include_comments: bool = False`;
- structured output с карточкой mock Tracker issue.

Агентский слой не просто сохраняет raw result. Он формирует Markdown-резюме задачи, выделяет
status, priority, assignee, comments и next action.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios mcp-tool-demo` | Запустить локальный stdio MCP server, получить `tools/list`, вызвать `get_tracker_issue` и сохранить artifacts/results |
| `--issue-key KEY` | Выбрать ключ mock Tracker issue; default `AI-17` |
| `--include-comments` | Включить comments в результат tool |
| `--timeout-seconds N` | Ограничить startup, discovery и tool call; default `15` |
| `--output-dir PATH` | Выбрать каталог JSON/Markdown artifacts |
| `--results-file PATH` | Выбрать Markdown result report |

Новых slash-команд интерактивного агента нет.

## Структура файлов

```text
weeks/week-04/day-17-first-mcp-tool/
├── README.md
├── codex-log.md
├── artifacts/
│   ├── agent-used-tool-result.md
│   ├── mcp-tool-call-result.json
│   └── tools-list.json
├── results/
│   └── day-17-first-mcp-tool.md
└── snapshot/
    ├── .env.example
    ├── README.md
    ├── pyproject.toml
    ├── src/ai_advent_agent/
    │   ├── __init__.py
    │   ├── mcp_mock_api.py
    │   ├── mcp_tool_client.py
    │   ├── mcp_tool_server.py
    │   └── scenarios.py
    └── tests/test_mcp_tool_demo.py
```

Актуальный код находится в `packages/ai_advent_agent/src/ai_advent_agent/`:

- `mcp_mock_api.py`;
- `mcp_tool_server.py`;
- `mcp_tool_client.py`;
- historical runner в `snapshot/`; в актуальном package scenario layer удалён;
- tests в `packages/ai_advent_agent/tests/test_mcp_tool_demo.py`.

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Day-specific runner удалён из актуального package. Core MCP client и output helpers проверяются
локальными tests без интернета, API key, внешнего Tracker API или LLM API.

Тесты Day 17:

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_tool_demo.py -q
```

#### Online/interactive агент

Online/interactive запуск не предусмотрен. Day 17 намеренно не использует LLM API, реальные внешние
API, API keys или сеть.

### Snapshot Day 17

#### Offline-сценарий

```bash
cd weeks/week-04/day-17-first-mcp-tool/snapshot
uv sync
uv run python -m pytest -q
uv run ai-advent-scenarios mcp-tool-demo \
  --issue-key AI-17 \
  --include-comments \
  --output-dir ../artifacts \
  --results-file ../results/day-17-first-mcp-tool.md
```

API key и интернет не требуются. Runtime-файлы сохраняются вне `snapshot/`.

#### Online/interactive агент

Online/interactive запуск snapshot-а не предусмотрен.

## Сценарий демонстрации для видео

1. Показать исходное условие Day 17 и объяснить отличие от Day 16: было remote discovery без
   tool calls, стало локальное создание server-а и вызов собственного tool.
2. Открыть `mcp_mock_api.py`: показать deterministic mock Tracker issues `AI-16`, `AI-17`,
   `AI-18`, нормализацию ключа и controlled unknown issue error.
3. Открыть `mcp_tool_server.py`: показать `FastMCP`, `@mcp.tool(structured_output=True)`,
   `get_tracker_issue`, type hints, docstring и `mcp.run(transport="stdio")`.
4. Запустить `pytest packages/ai_advent_agent/tests/test_mcp_tool_demo.py -q`.
5. Выполнить основной scenario `mcp-tool-demo` с `--issue-key AI-17 --include-comments`.
6. Открыть `artifacts/tools-list.json` и показать, что tool реально получен через `list_tools`,
   а schema содержит `issue_key` и `include_comments`.
7. Открыть `artifacts/mcp-tool-call-result.json` и показать фактический `call_tool` result.
8. Открыть `artifacts/agent-used-tool-result.md`: показать title/status/priority/assignee и next action.
9. Открыть `results/day-17-first-mcp-tool.md` как итоговый отчёт.
10. Перейти в `snapshot/`, выполнить `uv sync`, `uv run python -m pytest -q` и
    `uv run ai-advent-scenarios mcp-tool-demo`.

## Результаты

Фактический запуск 2026-06-23 создал локальный stdio MCP server `AI Advent Mock Tracker`, получил
один tool `get_tracker_issue`, вызвал его с аргументами `issue_key=AI-17` и
`include_comments=True`, получил structured result mock Tracker issue и сформировал Markdown,
где агент использовал результат.

Проверенные файлы:

- [tools-list.json](artifacts/tools-list.json);
- [mcp-tool-call-result.json](artifacts/mcp-tool-call-result.json);
- [agent-used-tool-result.md](artifacts/agent-used-tool-result.md);
- [day-17-first-mcp-tool.md](results/day-17-first-mcp-tool.md).

## Выводы

Первый собственный MCP tool лучше делать read-only, локальным и deterministic. Такой сценарий
позволяет проверить все важные механики MCP без внешних интеграционных рисков: registration,
input schema, `list_tools`, `call_tool`, structured result и использование ответа агентским слоем.

<!-- source: weeks/week-04/day-18-scheduler-background-tasks/README.md -->

# Day 18 — Планировщик и фоновые задачи через MCP tools

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1UOJ3nmCv4EId9F2351txPnpuTewAqGzq)

## Исходное условие

🔥 День 18. Планировщик и фоновые задачи

Сделайте MCP-инструмент с отложенным или периодическим выполнением.

Пример:

👉 reminder
👉 периодический сбор данных
👉 регулярный summary

Инструмент должен:

👉 сохранять данные (JSON / SQLite)
👉 выполняться по расписанию
👉 возвращать агрегированный результат

Результат:

Агент, который работает 24/7 и периодически выдаёт сводку

Формат:

Видео + Код

## Цель задания

Проверить, как MCP tool может быть не только разовым read-only вызовом, но и интерфейсом управления
scheduled/background workflow: агент запускает периодический сбор данных через MCP, server сохраняет
snapshots в SQLite, а второй MCP tool возвращает агрегированную summary.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-18-scheduler-background-tasks.md)

## Реализация

Статус: `✅ done`.

Day 18 продолжает Day 17. Day 17 публиковал один read-only tool `get_tracker_issue` поверх mock
Tracker API. Day 18 добавляет отдельный локальный stdio MCP server `AI Advent Tracker Scheduler`,
который публикует три scheduler-aware tools:

- `schedule_tracker_summary` — запускает bounded scheduled collection для mock Tracker issues,
  сохраняет каждый run в SQLite и возвращает structured job result;
- `get_scheduler_run_log` — читает SQLite и возвращает ordered timeline scheduled runs без нового
  collection и без изменения состояния;
- `get_tracker_summary` — читает SQLite, агрегирует snapshots по окну времени и возвращает
  structured summary для агентского отчёта.

Архитектурный flow:

```text
Agent -> MCP client -> stdio MCP server -> scheduler/service layer -> mock Tracker API -> SQLite
```

Сценарий демонстрации bounded: `interval_seconds=5.0`, `max_runs=3`. Это показывает 24/7-паттерн,
но не оставляет тесты и видео в бесконечном процессе. Внутренний service layer поддерживает
`max_runs=None` как режим "работать до отмены", но CLI и artifacts используют только bounded demo.

SQLite schema создаётся автоматически и содержит:

- `jobs` — зарегистрированные scheduled jobs;
- `runs` — отдельные итерации collection;
- `issue_snapshots` — снимки карточек задач на каждом run.

CLI scenario перед bounded demo пересоздаёт свой файл `tracker-summary.sqlite3`, чтобы повторный
запуск команды давал воспроизводимые 3 runs и 9 snapshots. Сами MCP tools и service layer остаются
append-only и могут накапливать историю в существующей SQLite базе.

Server не пишет обычные сообщения в stdout. stdout занят MCP protocol messages; диагностические
сообщения SDK идут в stderr.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios mcp-scheduler-demo` | Запустить локальный stdio MCP server, вызвать scheduler tools и сохранить SQLite/JSON/Markdown artifacts |
| `--issue-keys KEY ...` | Список mock Tracker issue keys; default `AI-16 AI-17 AI-18` |
| `--interval-seconds N` | Интервал между scheduled runs; для video/demo `5`, для тестов можно `0` |
| `--max-runs N` | Ограничение числа runs; default `3` |
| `--window-minutes N` | Окно агрегации для summary; default `60` |
| `--timeout-seconds N` | Общий timeout startup, scheduled collection и summary; default `30` |
| `--output-dir PATH` | Каталог artifacts |
| `--results-file PATH` | Markdown result report |

Новых slash-команд интерактивного агента нет.

## Структура файлов

```text
weeks/week-04/day-18-scheduler-background-tasks/
├── README.md
├── codex-log.md
├── artifacts/
│   ├── agent-periodic-summary.md
│   ├── aggregated-summary.json
│   ├── scheduler-job-result.json
│   ├── scheduler-run-log.json
│   ├── tools-list.json
│   └── tracker-summary.sqlite3
├── results/
│   └── day-18-scheduler-background-tasks.md
└── snapshot/
    ├── .env.example
    ├── README.md
    ├── pyproject.toml
    ├── uv.lock
    ├── src/ai_advent_agent/
    │   ├── __init__.py
    │   ├── mcp_mock_api.py
    │   ├── mcp_scheduler_client.py
    │   ├── mcp_scheduler_server.py
    │   ├── mcp_scheduler_service.py
    │   ├── mcp_scheduler_store.py
    │   ├── mcp_tool_client.py
    │   └── scenarios.py
    └── tests/test_mcp_scheduler_demo.py
```

Актуальный код находится в `packages/ai_advent_agent/src/ai_advent_agent/`:

- `mcp_scheduler_store.py`;
- `mcp_scheduler_service.py`;
- `mcp_scheduler_server.py`;
- `mcp_scheduler_client.py`;
- historical runner в `snapshot/`; в актуальном package scenario layer удалён;
- tests в `packages/ai_advent_agent/tests/test_mcp_scheduler_demo.py`.

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Day-specific runner удалён из актуального package. Core scheduler client, service, SQLite store и
output helpers проверяются локальными tests без сети, API key, VPS или cron/systemd.

Тесты Day 18:

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_scheduler_demo.py -q
```

#### Online/interactive агент

Online/interactive запуск не предусмотрен. Day 18 намеренно не использует LLM API, реальные внешние
API, API keys, сеть или бесконечный daemon в default scenario.

### Snapshot Day 18

#### Offline-сценарий

```bash
cd weeks/week-04/day-18-scheduler-background-tasks/snapshot
uv sync
uv run python -m pytest -q
uv run ai-advent-scenarios mcp-scheduler-demo \
  --issue-keys AI-16 AI-17 AI-18 \
  --interval-seconds 5 \
  --max-runs 3 \
  --output-dir ../artifacts \
  --results-file ../results/day-18-scheduler-background-tasks.md
```

API key и интернет не требуются. Runtime-файлы сохраняются вне `snapshot/`.

#### Online/interactive агент

Online/interactive запуск snapshot-а не предусмотрен.

## Сценарий демонстрации для видео

1. Показать исходное условие Day 18 и уточнение преподавателя: фокус на MCP tool, VPS не нужен.
2. Показать отличие от Day 17: теперь agent не вызывает mock API напрямую, а управляет scheduled
   workflow через MCP tools.
3. Открыть `mcp_scheduler_server.py`: показать `FastMCP`, tools `schedule_tracker_summary`,
   `get_scheduler_run_log` и `get_tracker_summary`, structured output и `mcp.run(transport="stdio")`.
4. Открыть `mcp_scheduler_service.py`: показать bounded loop, `max_runs`, `interval_seconds`,
   `asyncio.sleep` и сбор mock issues.
5. Открыть `mcp_scheduler_store.py`: показать SQLite schema `jobs`, `runs`, `issue_snapshots` и
   aggregation по latest issues.
6. Запустить `pytest packages/ai_advent_agent/tests/test_mcp_scheduler_demo.py -q`.
7. Выполнить основной scenario `mcp-scheduler-demo` с `interval_seconds=5`, `max_runs=3`.
8. Открыть `artifacts/tools-list.json`: показать, что tools получены через `list_tools`.
9. Открыть `artifacts/scheduler-job-result.json`: показать job id, status и runs completed.
10. Открыть `artifacts/scheduler-run-log.json`: показать три scheduled runs с timestamps и issue keys.
11. Открыть `artifacts/aggregated-summary.json`: показать counts и latest issues.
12. Открыть `artifacts/agent-periodic-summary.md`: показать, как агент использовал timeline и summary.
13. Открыть `results/day-18-scheduler-background-tasks.md` как итоговый отчёт с timeline-таблицей.
14. Перейти в `snapshot/`, выполнить `uv sync`, `uv run python -m pytest -q` и snapshot scenario.

## Результаты

Фактический запуск 2026-06-24 создал локальный stdio MCP server `AI Advent Tracker Scheduler`,
получил tools `schedule_tracker_summary`, `get_scheduler_run_log` и `get_tracker_summary`,
выполнил 3 scheduled runs по задачам `AI-16`, `AI-17`, `AI-18` с `interval_seconds=5.0`, сохранил
9 snapshots в SQLite, вернул timeline scheduled runs и aggregated summary.

Проверенные файлы:

- [tools-list.json](artifacts/tools-list.json);
- [scheduler-job-result.json](artifacts/scheduler-job-result.json);
- [scheduler-run-log.json](artifacts/scheduler-run-log.json);
- [aggregated-summary.json](artifacts/aggregated-summary.json);
- [agent-periodic-summary.md](artifacts/agent-periodic-summary.md);
- [day-18-scheduler-background-tasks.md](results/day-18-scheduler-background-tasks.md).

## Выводы

Scheduled/background workflow удобно выражать через MCP tools как control plane: агент запускает
работу и запрашивает summary через protocol boundary, а хранение, расписание и агрегация остаются
на стороне server/service layer. Для учебного и тестового сценария bounded schedule безопаснее
настоящего 24/7 daemon: он воспроизводим, не зависает и создаёт проверяемые artifacts.

<!-- source: weeks/week-04/day-19-mcp-tool-composition/README.md -->

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

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-19-mcp-tool-composition.md)

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
├── codex-log.md
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
- historical runner в `snapshot/`; в актуальном package scenario layer удалён;
- tests в `packages/ai_advent_agent/tests/test_mcp_tool_composition.py`.

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Day-specific runner удалён из актуального package. Scripted planner и generic composition loop
проверяются напрямую через core package tests без сети и API key.

Тесты Day 19:

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_tool_composition.py -q
```

#### Online/interactive агент

Новый online CLI для composition пока не спроектирован. Для воспроизведения LLM-driven demo с
`DEEPSEEK_API_KEY` используйте `Snapshot Day 19` ниже.

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
5. Показать в snapshot runner, что orchestration не содержит hardcoded `search -> build -> save`
   sequence из прямых `await call_tool(...)`.
6. Показать наличие `DEEPSEEK_API_KEY` без вывода значения ключа, например только статусом
   `env-present` или `dotenv-present`.
7. Запустить online scenario из `Snapshot Day 19` по команде раздела `Как запустить`.

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

<!-- source: weeks/week-04/day-20-mcp-orchestration/README.md -->

# Day 20 — Orchestration MCP

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1M5Z_uuYgyS5tuvzkxC5WLyFnjTvGbJGs)

## Исходное условие

🔥 День 20. Orchestration MCP

Зарегистрируйте несколько MCP-серверов.

Сделайте так, чтобы:
👉 агент выбирал нужный инструмент
👉 корректно маршрутизировал запросы
👉 выполнял длинный флоу взаимодействия

Проверьте:
👉 сценарий, в котором используются инструменты с разных серверов
👉 корректность выбора и порядка вызовов

Результат:
Длинный флоу взаимодействия с несколькими MCP-серверами и инструментами

Формат:
Видео + Код

## Цель задания

Реализовать модель-агностичный host/orchestrator, который обнаруживает tools четырёх независимых
stdio MCP servers, формирует normalized registry, получает от LLM следующий neutral JSON action,
валидирует его, маршрутизирует в правильную `ClientSession` и повторяет цикл до сохранения итогов.

DeepSeek используется только как text/JSON completion provider. Архитектура не использует
provider-native function calling как control plane и допускает замену LLM adapter-а.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-20-mcp-orchestration.md)

## Реализация

Статус реализации: `✅ done`. Финальные artifacts получены основным online запуском
`--planner llm-json`: 11 MCP tool calls через все четыре server-а, ordered chain найден,
`completed=true`.

Зарегистрированы четыре отдельных локальных server subprocess:

| Server | Tools | Ответственность |
|---|---|---|
| `tracker` | `search_tracker_issues`, `get_tracker_issue` | deterministic mock issue data |
| `knowledge` | `get_mcp_day_context`, `get_best_practice_note` | локальный учебный контекст Week 04 |
| `report` | `build_orchestration_report`, `build_next_steps` | deterministic processing без LLM |
| `storage` | `save_markdown_file`, `save_json_file` | path-safe запись только в configured output dir |

Основной flow:

```text
4 stdio servers
  -> initialize + tools/list per session
  -> server registry + normalized tools registry
  -> LLM returns one ordinary JSON action
  -> schema/ownership/phase validation
  -> sessions[action.server].call_tool(...)
  -> compact planner view + полный accumulated flow state
  -> repeat until final_response
```

Deterministic scripted test проходит 11 вызовов: два Tracker search, пять Knowledge reads, два
Report processing calls и два Storage writes. Policy проверяет обязательные inputs перед
report/save/final, но не выбирает tool за planner-а. Online LLM может добавить retry/extra calls;
success принимает их через ordered subsequence, а не требует точного равенства sequence.

Planner prompt получает отдельное компактное представление state: Markdown заменён длиной и
коротким preview, Storage results — metadata, completed calls — коротким timeline. Для крупных
аргументов planner возвращает нейтральные `$state`/`$projection` references, которые host разрешает
из полного internal state перед MCP call. Поэтому сохранённые artifacts не теряют данные, а поздние
LLM turns не обязаны повторно сериализовать отчёт и весь JSON state.

`final-orchestration-report.md` и `saved-flow-state.json` созданы только Storage MCP tools. Host
напрямую пишет только registry, trace, routing decisions, compact flow state, final answer и result
report — evidence самого процесса оркестрации.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios mcp-orchestration-demo` | Запустить orchestration flow через четыре stdio MCP servers |
| `--planner {llm-json,scripted}` | Выбрать основной online JSON planner или offline test fallback |
| `--goal TEXT` | Передать цель model-agnostic planner-у |
| `--output-dir PATH` | Задать output/artifacts boundary Storage server-а |
| `--results-file PATH` | Сохранить Markdown result report |
| `--server-timeout-seconds N` | Ограничить весь orchestration lifecycle: MCP startup, planner loop и tool calls; default `360` |
| `--max-steps N` | Ограничить planner turns, default `15` |
| `--model NAME` | Выбрать DeepSeek-compatible model для `llm-json` |
| `--api-url URL` | Задать compatible Chat Completions endpoint |
| `--temperature N` | Задать planner temperature, default `0.0` |
| `--max-tokens N` | Ограничить размер JSON completion |

Новых slash-команд интерактивного агента нет.

## Структура файлов

```text
weeks/week-04/day-20-mcp-orchestration/
├── README.md
├── codex-log.md
├── artifacts/
│   ├── server-registry.json
│   ├── tools-registry.json
│   ├── orchestration-trace.json
│   ├── routing-decisions.json
│   ├── flow-state.json
│   ├── final-orchestration-report.md
│   ├── final-agent-answer.md
│   └── saved-flow-state.json
├── results/
│   └── day-20-mcp-orchestration.md
└── snapshot/
    ├── .env.example
    ├── README.md
    ├── pyproject.toml
    ├── uv.lock
    ├── src/ai_advent_agent/
    └── tests/test_mcp_orchestration.py
```

Актуальный пакет разделяет server builders, planner, client/router и deterministic domains по
модулям `mcp_orchestration_*.py`. Tests находятся в `test_mcp_orchestration.py`.

## Как запустить

### Актуальный пакет

#### Online/interactive агент

Новый online CLI для orchestration пока не спроектирован. Для воспроизведения финального
LLM-driven evidence с `DEEPSEEK_API_KEY` используйте `Snapshot Day 20` ниже.

#### Offline-сценарий — только fallback/tests

Scripted planner, четыре MCP sessions, registry, validation и router проверяются напрямую через
package tests без сети или API key.

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_orchestration.py -q
```

### Snapshot Day 20

#### Online/interactive агент — альтернативный full run из snapshot

Требуется `DEEPSEEK_API_KEY`. Это явный full online run, поэтому он создаёт основные Day 20
artifacts/results рядом со snapshot. Запускайте его только когда намеренно обновляете финальный
video evidence:

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

#### Offline-сценарий

```bash
cd weeks/week-04/day-20-mcp-orchestration/snapshot
uv run pytest -q
uv run ai-advent-scenarios mcp-orchestration-demo \
  --planner scripted \
  --output-dir .tmp/day20-scripted-fallback/artifacts \
  --results-file .tmp/day20-scripted-fallback/day-20-mcp-orchestration.md
```

## Сценарий демонстрации для видео

### 1. Показать архитектуру multi-server MCP

Открыть `packages/ai_advent_agent/src/ai_advent_agent/mcp_orchestration_servers.py`.

Показать:

- `build_tracker_server`;
- `build_knowledge_server`;
- `build_report_server`;
- `build_storage_server`;
- четыре отдельных локальных stdio MCP server-а;
- отдельную ответственность каждого server-а: Tracker читает issue data, Knowledge отдаёт учебный
  контекст, Report строит deterministic отчёты, Storage пишет файлы в configured output boundary;
- что tools не вызывают LLM и остаются deterministic.

Смысл фрагмента: Day 20 проверяет не один большой server, а host, который работает с несколькими
независимыми MCP sessions и разными trust boundaries.

### 2. Показать orchestration client и routing layer

Открыть `packages/ai_advent_agent/src/ai_advent_agent/mcp_orchestration_client.py`.

Показать:

- discovery всех MCP servers;
- запись `server-registry.json`;
- запись normalized `tools-registry.json`;
- routing по `server_id` / `action.server`;
- вызов `session.call_tool(...)` на выбранной MCP session;
- отсутствие hardcoded pipeline вида `call tracker -> call knowledge -> call report -> call storage`.

Смысл фрагмента: порядок действий выбирает planner, а host валидирует ownership и маршрутизирует
validated action в нужную session.

### 3. Показать model-agnostic planner

Открыть `packages/ai_advent_agent/src/ai_advent_agent/mcp_orchestration_planner.py`.

Показать:

- neutral JSON action contract;
- action types `call_tool` и `final_response`;
- что DeepSeek используется только как LLM provider;
- что native `tools`, `tool_calls`, `tool_choice` не используются как orchestration protocol;
- что `model_specific_tool_calling=false` отражается в evidence;
- compact planner state и state/projection references для крупных payloads.

Смысл фрагмента: orchestration protocol принадлежит приложению, а не конкретному provider API.

### 4. Запустить online scenario

Показать команду из snapshot-каталога. Это основной сценарий для видео; он требует
`DEEPSEEK_API_KEY`, но значение ключа не показывать.

```bash
cd weeks/week-04/day-20-mcp-orchestration/snapshot

uv run ai-advent-scenarios mcp-orchestration-demo \
  --planner llm-json \
  --goal "Собери большой итоговый отчёт по MCP Week 04: найди выполненные и планируемые MCP-задачи, получи контекст Day 18, Day 19 и Day 20, добавь best practices по multi-server orchestration и model-agnostic planning, собери отчёт и сохрани Markdown и JSON состояние через storage MCP server." \
  --output-dir ../artifacts \
  --results-file ../results/day-20-mcp-orchestration.md \
  --server-timeout-seconds 360 \
  --max-steps 18
```

Пояснить:

- `--planner llm-json` — online LLM planner и финальный evidence mode;
- `--server-timeout-seconds 360` — общий timeout всего orchestration lifecycle: startup MCP
  servers, LLM planner turns, MCP tool calls и запись artifacts;
- `--max-steps 18` — safety limit, а фактический successful flow использует 11 tool calls.

### 5. Показать server registry

Открыть `weeks/week-04/day-20-mcp-orchestration/artifacts/server-registry.json`.

Показать:

- 4 registered servers: `tracker`, `knowledge`, `report`, `storage`;
- command/transport каждого server-а;
- что все servers initialized.

Смысл фрагмента: host реально зарегистрировал несколько MCP endpoints до planner loop.

### 6. Показать tools registry

Открыть `weeks/week-04/day-20-mcp-orchestration/artifacts/tools-registry.json`.

Показать:

- 8 tools;
- tool names;
- `server_id` / routing target;
- input schemas;
- что agent получает tools через MCP discovery, а не знает их заранее как Python-функции.

Смысл фрагмента: единое tool space собрано из нескольких servers с сохранением ownership.

### 7. Показать orchestration trace

Открыть `weeks/week-04/day-20-mcp-orchestration/artifacts/orchestration-trace.json`.

Показать верхние поля:

- `planner=llm-json`;
- `model=deepseek-v4-flash`;
- `model_specific_tool_calling=false`;
- `hardcoded_pipeline=false`;
- `servers_registered`;
- `servers_used`;
- `tool_calls_total=11`;
- `required_chain_found=true`;
- `completed=true`;
- `usage.llm_api_calls=12`;
- `usage.planner_calls=12`.

Потом показать `steps`:

- шаги 1-2: `tracker` server;
- шаги 3-7: `knowledge` server;
- шаги 8-9: `report` server;
- шаги 10-11: `storage` server.

Смысл фрагмента: trace доказывает длинный flow и использование tools с разных MCP servers в
правильном порядке.

### 8. Показать routing decisions

Открыть `weeks/week-04/day-20-mcp-orchestration/artifacts/routing-decisions.json`.

Показать:

- `requested_server`;
- `resolved_session`;
- `tool_name`;
- что requested server совпадает с фактической MCP session;
- что routing выполняется orchestration layer-ом.

Смысл фрагмента: evidence проверяет не только список calls, но и корректность маршрутизации.

### 9. Показать финальный Markdown report

Открыть `weeks/week-04/day-20-mcp-orchestration/artifacts/final-orchestration-report.md`.

Показать:

- итоговый отчёт;
- блок про MCP server topology;
- registered servers: `tracker`, `knowledge`, `report`, `storage`;
- что report собран через `report` MCP server, а не вручную в host.

### 10. Показать flow state и сохранение через storage server

Открыть `weeks/week-04/day-20-mcp-orchestration/artifacts/flow-state.json`.

Показать:

- раздел `storage`;
- `markdown_file`;
- `json_file`;
- `path`;
- `bytes_written`;
- `sha256`.

Открыть `weeks/week-04/day-20-mcp-orchestration/artifacts/saved-flow-state.json`.

Показать, что JSON state сохранён через `storage.save_json_file`.

Смысл фрагмента: финальные Markdown/JSON artifacts пишет Storage MCP server, а host сохраняет только
process evidence.

### 11. Показать result report

Открыть `weeks/week-04/day-20-mcp-orchestration/results/day-20-mcp-orchestration.md`.

Показать:

- registered servers table;
- tools table;
- routing timeline;
- success criteria;
- artifact list.

Смысл фрагмента: result report связывает machine-readable evidence с human-readable итогом дня.

### 12. Offline/test fallback

Пояснить, что scripted planner используется только для deterministic tests/local checks, не как
evidence для видео. Он пишет во временную `.tmp/` директорию и не заменяет финальные artifacts.

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_orchestration.py -q
```

### 13. Финальные проверки

```bash
make clean
make check
make safety
python scripts/export_public.py --dry-run
```

## Результаты

Финальный snapshot online run создал полный набор evidence. В trace зафиксированы
`planner=llm-json`, model `deepseek-v4-flash`, `model_specific_tool_calling=false`,
`hardcoded_pipeline=false`, 11 tool calls, 12 planner calls / 12 LLM API calls, четыре
registered/used server-а, `required_chain_found=true` и `completed=true`. Все 11 routing decisions
валидны и направлены в session запрошенного server-а.

`final-orchestration-report.md` и `saved-flow-state.json` сохранены Storage MCP tools; их byte count
и SHA-256 зафиксированы в `flow-state.json`. Generated report отдельно показывает все registered
servers, pre-report data sources и роли Report/Storage stages.

## Выводы

Multi-server MCP orchestration — это ответственность host-а: servers публикуют маленькие
deterministic capabilities, registry задаёт проверяемое пространство действий, planner выбирает
следующий neutral JSON action, validator охраняет границы, router вызывает правильную session, а
evidence позволяет доказать выбор и порядок. Такая граница переносима между моделями и harness-ами.

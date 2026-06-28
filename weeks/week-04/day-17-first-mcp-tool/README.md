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

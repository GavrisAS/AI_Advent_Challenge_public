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

Unit tests и CLI help не требуют интернета, API key или LLM API. Remote integration test по
умолчанию пропускается.

```bash
uv run --project packages/ai_advent_agent pytest \
  packages/ai_advent_agent/tests/test_mcp_connection.py

uv run --project packages/ai_advent_agent \
  ai-advent-scenarios mcp-connection-demo --help
```

#### Online-сценарий

Требуется доступ к интернету. API key и другие секреты не требуются.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-connection-demo \
  --server-url https://mcp.deepwiki.com/mcp \
  --output-dir .tmp/day16-mcp-connection \
  --results-file weeks/week-04/day-16-mcp-connection/results/day-16-mcp-connection.md
```

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
2. Показать CLI help и параметры `mcp-connection-demo`.
3. Запустить offline unit tests; отметить пропущенный opt-in integration test.
4. Выполнить online-команду актуального пакета с output в `.tmp/day16-mcp-connection`.
5. Показать в терминале успешные initialization, protocol version, tool count и три имени tools.
6. Открыть `mcp-connection-result.json`, `tools-list.json` и Markdown report; подтвердить
   `connected=true`, отсутствие missing/extra tools и отсутствие tool calls.
7. Из каталога `snapshot/` повторить online-сценарий с output в `../artifacts/snapshot-run`.
8. Показать `make clean`, `make clean-venv`, `make clean-all`; для обычной очистки использовать
   только `make clean`, который не удаляет `.venv`.
9. После записи при необходимости удалить только временный `.tmp/day16-mcp-connection`; итоговые
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

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

#### Online/interactive агент — основной сценарий для видео

Этот запуск идёт первым, потому что только `--planner llm-json` является финальным evidence Day 20.
Требуется `DEEPSEEK_API_KEY`; ключ, headers и raw environment в artifacts не сохраняются.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-orchestration-demo \
  --planner llm-json \
  --goal "Собери большой итоговый отчёт по MCP Week 04: найди выполненные и планируемые MCP-задачи, получи контекст Day 18, Day 19 и Day 20, добавь best practices по multi-server orchestration и model-agnostic planning, собери отчёт и сохрани Markdown и JSON состояние через storage MCP server." \
  --output-dir weeks/week-04/day-20-mcp-orchestration/artifacts \
  --results-file weeks/week-04/day-20-mcp-orchestration/results/day-20-mcp-orchestration.md \
  --server-timeout-seconds 360 \
  --max-steps 18
```

`--server-timeout-seconds` здесь означает общий timeout всего orchestration lifecycle: запуск и
initialization четырёх MCP servers, все planner turns и MCP tool calls. Это не только startup timeout.

#### Offline-сценарий — только fallback/tests

Scripted planner не требует сети или API key и проходит через те же четыре MCP sessions, registry,
validation и router. Его output хранится только в `.tmp/` и не заменяет online artifacts.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios mcp-orchestration-demo \
  --planner scripted \
  --output-dir .tmp/day20-scripted/artifacts \
  --results-file .tmp/day20-scripted/day-20-mcp-orchestration.md

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

Показать команду  из snapshot-каталога. Это основной сценарий для видео; он требует
`DEEPSEEK_API_KEY`, но значение ключа не показывать.

```bash
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

# CLI актуального harness

## Текущий entry point

Актуальный package устанавливает один пользовательский entry point:

```text
ai-advent-agent
```

Команда `ai-advent-scenarios` в `packages/` не поддерживается. Исторические day-specific runners
сохранены в `weeks/**/snapshot/**` и не определяют интерфейс текущего harness.

Document indexing доступен как Python API `ai_advent_agent.rag`; отдельный current-package
scenario CLI для Day 21 не добавлен. Historical demo запускается только из snapshot Day 21.

Практические безопасные сценарии запуска собраны в [`examples.md`](examples.md).

## Текущие режимы запуска

Запуск без дополнительных аргументов открывает интерактивную сессию. Ввод обычного текста
вызывает `SimpleAgent.ask()`, а ввод с `/` маршрутизируется в registry slash-команд.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent
```

По умолчанию для ввода используется `prompt_toolkit` с autocomplete. Флаг `--plain-input`
переключает сессию на обычный `input()`, но не делает запуск single-shot командой.

Явный alias запускает тот же interactive mode и принимает те же options:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent chat --plain-input
```

Single-shot automation command отправляет один prompt через тот же runtime pipeline
`SimpleAgent.ask()` и завершает процесс:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent ask "текст запроса"
echo "текст запроса" | uv run --project packages/ai_advent_agent ai-advent-agent ask --stdin
```

`ask` требует те же LLM credentials, что interactive mode, включая `DEEPSEEK_API_KEY`. При успехе
stdout содержит текст ответа assistant, а затем metadata, если не указан `--no-metadata`.
Стабильный stdin-интерфейс включается только явным `--stdin`; root invocation со stdin остаётся
interactive behavior, а не automation API.

## Read-only grouped CLI

Diagnostics читают runtime-файлы без создания `SimpleAgent`, LLM API call и
`DEEPSEEK_API_KEY`:

```text
ai-advent-agent context inspect
ai-advent-agent memory inspect
ai-advent-agent profile show
ai-advent-agent task show
ai-advent-agent invariant list
ai-advent-agent report tokens
```

Команды выводят человекочитаемый text report и ничего не записывают. Missing-файл считается
нормальным пустым состоянием и даёт exit code `0`; ошибка чтения или формата — exit code `1`;
ошибка CLI arguments обрабатывается `argparse` с exit code `2`. Нужные runtime paths можно
переопределить соответствующими `--*-file` options после leaf-команды.

## Cleanup grouped CLI

Cleanup/reset commands удаляют явно выбранные локальные runtime-файлы без API key:

```text
ai-advent-agent context clear --yes
ai-advent-agent memory clear --summary --yes
ai-advent-agent memory clear --facts --yes
ai-advent-agent memory clear --short-term --yes
ai-advent-agent memory clear --working --yes
ai-advent-agent memory clear --long-term --yes
ai-advent-agent memory clear --all --yes
ai-advent-agent profile reset --yes
ai-advent-agent task reset --yes
ai-advent-agent invariant clear --yes
ai-advent-agent report tokens clear --yes
```

Все cleanup commands требуют `--yes`; без него возвращается exit code `2`. Флаг `--dry-run`
показывает, что было бы удалено, но не меняет файлы. Missing-файл не является ошибкой.
Cleanup удаляет только выбранные runtime files и не трогает audit/event logs:
`memory_events.jsonl`, `profile_events.jsonl`, `task_events.jsonl`,
`invariant_events.jsonl`.

Этот слой не является semantic state editing: он не выполняет `memory set`, `profile set`,
`task transition`, `invariant add` и не вызывает MCP.

## Semantic memory write grouped CLI

Semantic memory commands управляют explicit memory layers без API key:

```text
ai-advent-agent memory note add "короткая заметка"
ai-advent-agent memory set working KEY VALUE
ai-advent-agent memory set long-term KEY VALUE
ai-advent-agent memory forget working KEY --yes
ai-advent-agent memory forget long-term KEY --yes
```

Команды работают напрямую с локальными runtime-файлами, не создают `SimpleAgent`, не требуют
`DEEPSEEK_API_KEY` и не вызывают LLM. Они управляют теми же explicit memory layers, которые видны
в interactive `/memory` командах:

- `note add` добавляет short-term note и пишет event `remember`/`short_term`;
- `set working` и `set long-term` записывают или перезаписывают key-value entry и пишут event
  `remember`;
- `forget working` и `forget long-term` удаляют key и пишут event `forget` только если key реально
  существовал.

Все memory write commands поддерживают `--dry-run`; этот режим читает и валидирует existing JSON,
но не создаёт и не меняет memory files или `memory_events.jsonl`. Forget-команды требуют `--yes`;
missing key возвращает exit code `0`, статус `missing` и не пишет event log. Empty text/key/value
возвращает exit code `2`; некорректный existing JSON — exit code `1`.

## Semantic profile grouped CLI

Semantic profile commands управляют user profiles без API key:

```text
ai-advent-agent profile list
ai-advent-agent profile active
ai-advent-agent profile create NAME
ai-advent-agent profile use NAME
ai-advent-agent profile set language VALUE
ai-advent-agent profile set style VALUE
ai-advent-agent profile set format VALUE
ai-advent-agent profile set audience VALUE
ai-advent-agent profile set preference KEY VALUE
ai-advent-agent profile set constraint KEY VALUE
ai-advent-agent profile clear active --yes
ai-advent-agent profile clear all --yes
```

Команды работают напрямую с `user_profiles.json` и `profile_events.jsonl`, не создают
`SimpleAgent`, не требуют `DEEPSEEK_API_KEY` и не вызывают LLM. `profile list` и `profile active`
являются read-only semantic views; missing profiles file возвращает exit code `0`.

Write/clear operations append profile event log только при real successful mutation. `--dry-run`
доступен для `create`, `use`, `set` и `clear`, читает и валидирует existing JSON, но не создаёт и
не меняет profiles file или event log. `profile clear active/all` требуют `--yes`.

`profile reset --yes` остаётся cleanup-командой: она удаляет profiles file. Semantic clear
использует отдельные команды `profile clear active --yes` и `profile clear all --yes`, которые не
удаляют profiles file.

Task/invariant semantic CLI описан ниже. MCP CLI описан отдельной группой ниже.

## Semantic task grouped CLI

Semantic task commands управляют task state machine без API key:

```text
ai-advent-agent task start TITLE
ai-advent-agent task set step TEXT
ai-advent-agent task set expected-action TEXT
ai-advent-agent task set metadata KEY VALUE
ai-advent-agent task approve-plan
ai-advent-agent task pass-validation
ai-advent-agent task transition planning|execution|validation|done
ai-advent-agent task advance
ai-advent-agent task pause
ai-advent-agent task resume
ai-advent-agent task complete
ai-advent-agent task clear active --yes
```

Команды работают напрямую с `task_state.json` и `task_events.jsonl`, не создают `SimpleAgent`, не
требуют `DEEPSEEK_API_KEY` и не вызывают LLM. Lifecycle transitions используют существующие
`validate_task_transition` и `apply_task_transition`, поэтому `planning -> execution` требует
`approve-plan`, а `validation -> done` требует `pass-validation`.

Real successful writes append `task_events.jsonl`. Rejected lifecycle transitions append
`invalid_transition` только при real non-dry-run запуске; state при этом не меняется.
`--dry-run` доступен для semantic write-команд, читает и валидирует existing JSON, но не создаёт и
не меняет task state или event log. `task clear active --yes` сохраняет пустой task state payload
в `task_state.json`, не удаляет файл и не удаляет event log.

`task reset --yes` остаётся cleanup-командой удаления task state file.

## Semantic invariant grouped CLI

Semantic invariant commands управляют state invariants без API key:

```text
ai-advent-agent invariant add CATEGORY TEXT
ai-advent-agent invariant enable ID
ai-advent-agent invariant disable ID
ai-advent-agent invariant remove ID --yes
ai-advent-agent invariant set rationale ID TEXT
ai-advent-agent invariant pattern add ID PATTERN
ai-advent-agent invariant pattern remove ID PATTERN --yes
ai-advent-agent invariant check TEXT
```

Команды работают напрямую с `invariants.json` и `invariant_events.jsonl`, не создают
`SimpleAgent`, не требуют `DEEPSEEK_API_KEY` и не вызывают LLM. Mutations используют существующие
`InvariantSet` и validation helpers. Real successful add/enable/disable/remove/set/pattern
operations append `invariant_events.jsonl`; `--dry-run` ничего не создаёт и не меняет.

`invariant remove` и `invariant pattern remove` требуют `--yes`. Missing pattern внутри existing
invariant возвращает success со статусом `missing` и не пишет event log. `invariant check` —
deterministic local read-only conflict check: он выводит conflict count и matched
invariants/patterns, но по умолчанию не пишет audit event.

`invariant clear --yes` остаётся cleanup-командой удаления invariants file.

## MCP grouped CLI

MCP grouped CLI работает поверх нейтрального Python API `ai_advent_agent.mcp.*`:

```text
ai-advent-agent mcp discover remote
ai-advent-agent mcp tracker issue ISSUE_KEY
ai-advent-agent mcp scheduler run
ai-advent-agent mcp compose run
ai-advent-agent mcp orchestrate run
```

Команды `mcp ...` не создают `SimpleAgent`, не используют `agent_factory.build_agent()` и не
возвращают scenario layer. Parser/help для root и non-MCP команд не импортирует MCP SDK; imports
MCP modules выполняются лениво только внутри MCP handlers.

Remote discovery использует `ai_advent_agent.mcp.discovery`:

```bash
ai-advent-agent mcp discover remote \
  --server-url https://mcp.deepwiki.com/mcp \
  --output-dir .agent_context/mcp/discovery
```

По умолчанию используются `DEFAULT_MCP_SERVER_URL` и `DEFAULT_MCP_TIMEOUT_SECONDS`. Команда может
требовать network. Invalid URL возвращает exit code `2`; known MCP connection errors пишут error
artifact и возвращают exit code `1`.

Local Tracker, scheduler, composition и orchestration workflows используют local stdio MCP servers:

```bash
ai-advent-agent mcp tracker issue AI-17 --include-comments
ai-advent-agent mcp scheduler run --issue-key AI-17 --issue-key AI-19 --window-minutes 60
ai-advent-agent mcp compose run --planner scripted --goal "Собери tracker report и сохрани его"
ai-advent-agent mcp orchestrate run --planner scripted --goal "Собери итоговый MCP report"
```

`tracker`, `scheduler` и `scripted` planner modes работают без `DEEPSEEK_API_KEY` и внешней сети.
`compose run --planner llm-json` использует existing composition env planner builder и требует
`DEEPSEEK_API_KEY`. `orchestrate run --planner llm-json` использует
`build_llm_json_planner_from_env(...)` и тоже требует `DEEPSEEK_API_KEY`.

Artifacts по умолчанию пишутся в `.agent_context/mcp/...`, то есть в runtime-зону актуального
harness, которая не коммитится.

## Внутренняя структура CLI

Пользовательский entry point не изменился: `ai-advent-agent` по-прежнему загружает
`ai_advent_agent.cli:main`. Внутри package CLI разделён по ответственности:

- `parser.py` — root parser и текущие interactive options;
- `runtime_paths.py` — defaults runtime-файлов и их env overrides;
- `agent_factory.py` — конфигурация `SimpleAgent`, LLM client и stores;
- `ask.py` — single-shot automation runner вокруг `SimpleAgent.ask()`;
- `cleanup.py` — API-key-free удаление явно выбранных runtime-файлов;
- `memory_write.py` — API-key-free semantic writes для explicit memory layers;
- `profile_write.py` — API-key-free semantic commands для user profiles;
- `task_write.py` — API-key-free semantic commands для task state machine;
- `invariant_write.py` — API-key-free semantic commands для state invariants;
- `mcp_commands.py` — lazy MCP command handlers вокруг `ai_advent_agent.mcp.*`;
- `interactive.py` — startup banner, input backend, slash-command routing и REPL;
- `subcommands.py` — только реализованные grouped parsers;
- `read_only.py` — side-effect-free runtime diagnostics;
- `main.py` — загрузка env и верхнеуровневая orchestration.

`build_parser()` регистрирует только фактически реализованные grouped commands. Запуск без
subcommand, interactive options, startup banner, EOF behavior и slash-команды остаются прежними.

Для построения агента требуется `DEEPSEEK_API_KEY`, в том числе если пользователь собирается
работать только с локальными slash-командами. `ask` тоже строит агента и требует ключ. Read-only,
cleanup, semantic memory/profile/task/invariant grouped commands ключ не требуют. MCP scripted
workflows ключ не требуют; MCP `llm-json` planner modes требуют `DEEPSEEK_API_KEY`.

## Текущие основные опции

| Группа | Опции | Назначение |
|---|---|---|
| Provider и модель | `--model`, `--api-url`, `--temperature`, `--max-tokens`, `--timeout` | Параметры LLM request и transport. |
| Стратегия ответа | `--strategy`, `--thinking`, `--reasoning-effort` | Response strategy и provider-facing reasoning options. |
| Context budget | `--context-window-tokens`, `--warn-context-ratio`, `--overflow-policy` | Оценка token budget и поведение при overflow. |
| Context management | `--context-strategy`, `--recent-messages-limit` | Sliding window, sticky facts или branching. |
| Summary memory | `--summary-mode`, `--summarize-every-messages`, `--summary-max-tokens` | Управление LLM summary-сжатием. |
| Token accounting | `--input-price-per-1m-tokens`, `--output-price-per-1m-tokens` | Локальная оценка стоимости без встроенных тарифов. |
| Runtime paths | `--context-file`, `--token-report-file`, `--summary-file`, `--facts-file`, `--branches-file` | Пути context subsystem. |
| Memory paths | `--short-term-memory-file`, `--working-memory-file`, `--long-term-memory-file`, `--memory-events-file` | Пути explicit memory layers. |
| State paths | `--user-profiles-file`, `--profile-events-file`, `--invariants-file`, `--invariant-events-file`, `--task-state-file`, `--task-events-file` | Пути profile, invariant и task state. |
| Session behavior | `--no-load-context`, `--no-persist`, `--no-token-report-log` | Управление загрузкой и сохранением runtime state. |
| Input/output | `--env-file`, `--no-metadata`, `--plain-input`, `--stdin`, `--dry-run`, `--yes` | Env-файл, metadata ответа, backend интерактивного ввода, явный stdin для `ask`, dry-run и confirmation для cleanup/destructive semantic operations. |

`--no-load-context` начинает сессию без загрузки существующей history, но не запрещает последующее
сохранение. `--no-persist` отключает основные JSON/JSONL stores, кроме token report log; для него
нужно отдельно указать `--no-token-report-log`.

## Runtime-файлы

По умолчанию runtime текущего harness находится в корневой `.agent_context/`. Эта директория не
коммитится и игнорируется правилом `/.agent_context/`.

| Файл | Содержимое |
|---|---|
| `.agent_context/messages.json` | Persistent dialog history. |
| `.agent_context/token_reports.jsonl` | Token reports запросов. |
| `.agent_context/summary.json` | Summary memory. |
| `.agent_context/facts.json` | Sticky facts. |
| `.agent_context/branches.json` | Branches и checkpoints. |
| `.agent_context/short_term_memory.json` | Short-term memory. |
| `.agent_context/working_memory.json` | Working key-value memory. |
| `.agent_context/long_term_memory.json` | Long-term key-value memory. |
| `.agent_context/memory_events.jsonl` | Audit log explicit memory operations. |
| `.agent_context/user_profiles.json` | Profiles и выбранный active profile. |
| `.agent_context/profile_events.jsonl` | Audit log profile operations. |
| `.agent_context/invariants.json` | Hard state invariants. |
| `.agent_context/invariant_events.jsonl` | Audit log invariant operations и checks. |
| `.agent_context/task_state.json` | Текущее task state. |
| `.agent_context/task_events.jsonl` | Audit log task transitions и mutations. |
| `.agent_context/mcp/` | Runtime artifacts MCP discovery/tool/scheduler/composition/orchestration CLI. |

Исторические runtime-файлы внутри snapshots и day artifacts не очищаются командами актуального
harness и не удаляются автоматически.

## Переменные окружения

| Группа | Переменные |
|---|---|
| Обязательная авторизация | `DEEPSEEK_API_KEY` |
| Provider и модель | `DEEPSEEK_MODEL`, `DEEPSEEK_API_URL`, `AGENT_TEMPERATURE`, `AGENT_MAX_TOKENS`, `AGENT_TIMEOUT_SECONDS` |
| Стратегия ответа | `AGENT_STRATEGY`, `AGENT_THINKING`, `AGENT_REASONING_EFFORT` |
| Context и summary | `CONTEXT_WINDOW_TOKENS`, `WARN_CONTEXT_RATIO`, `CONTEXT_OVERFLOW_POLICY`, `CONTEXT_STRATEGY`, `SUMMARY_MODE`, `RECENT_MESSAGES_LIMIT`, `SUMMARIZE_EVERY_MESSAGES`, `SUMMARY_MAX_TOKENS` |
| Стоимость | `INPUT_PRICE_PER_1M_TOKENS`, `OUTPUT_PRICE_PER_1M_TOKENS` |
| Context paths | `AI_ADVENT_CONTEXT_FILE`, `AI_ADVENT_TOKEN_REPORT_FILE`, `AI_ADVENT_SUMMARY_FILE`, `AI_ADVENT_FACTS_FILE`, `AI_ADVENT_BRANCHES_FILE` |
| Memory paths | `AI_ADVENT_SHORT_TERM_MEMORY_FILE`, `AI_ADVENT_WORKING_MEMORY_FILE`, `AI_ADVENT_LONG_TERM_MEMORY_FILE`, `AI_ADVENT_MEMORY_EVENTS_FILE` |
| State paths | `AI_ADVENT_USER_PROFILES_FILE`, `AI_ADVENT_PROFILE_EVENTS_FILE`, `AI_ADVENT_INVARIANTS_FILE`, `AI_ADVENT_INVARIANT_EVENTS_FILE`, `AI_ADVENT_TASK_STATE_FILE`, `AI_ADVENT_TASK_EVENTS_FILE` |

При старте harness ищет `.env` в текущем каталоге, его родителях и около package source. Уже
заданные process environment variables не перезаписываются, а явные CLI options имеют приоритет
над defaults из env.

Текущее ограничение: файл из `--env-file` загружается после `parse_args()`. Поэтому он подходит для
`DEEPSEEK_API_KEY`, который читается позже, но не меняет уже вычисленные parser defaults. Эту
последовательность нужно унифицировать при реорганизации CLI.

## Интерактивный режим и slash-команды

В колонке `current status` используются значения `active`, `group`, `compatibility` и `hidden`.
Колонка `target status` фиксирует ранее принятое migration-намерение для slash aliases:
`keep`, `rename`, `merge`, `remove` или `needs-docs`. Этот inventory не меняет текущий CLI
контракт и не добавляет новых команд.

### Help, status и config

| command | purpose | state changed? | runtime files affected? | current status | target status |
|---|---|---:|---|---|---|
| `/help [group]` | Показать root- или group-help. | нет | нет | active | `keep` |
| `/help legacy` | Показать deprecated aliases. | нет | нет | compatibility | `remove` |
| `/status` | Краткая диагностика session, memory и state. | нет | нет | active | `keep` |
| `/status config` | Показать ту же конфигурацию, что `/config show`. | нет | нет | active | `merge` → `/config show` |
| `/status context` | Показать context/state paths и текущие режимы. | нет | нет | active | `keep` |
| `/status tokens` | Показать estimated token breakdown history. | нет | нет | active | `keep` |
| `/status report` | Показать последний token report текущего процесса. | нет | нет | active | `keep` |
| `/status history` | Показать summary history. | нет | нет | active | `keep` |
| `/status history full` | Показать полную history. | нет | нет | active | `keep` |
| `/config` | Показать help namespace. | нет | нет | group | `keep` |
| `/config show` | Показать runtime configuration. | нет | нет | active | `keep` |
| `/config strategy direct\|step_by_step` | Изменить response strategy процесса. | да | нет, in-memory | active | `keep` |
| `/config summary off\|llm` | Изменить summary mode процесса. | да | нет, in-memory | active | `keep` |
| `/config overflow error\|no_trim\|sliding_window` | Изменить overflow policy процесса. | да | нет, in-memory | active | `keep` |

### Session и storage

| command | purpose | state changed? | runtime files affected? | current status | target status |
|---|---|---:|---|---|---|
| `/session` | Показать help namespace. | нет | нет | group | `keep` |
| `/session reset` | Начать новую session, сбросить session state и reports. | да | messages, summary, facts, short-term, task state, branches, token reports | active | `keep` |
| `/storage` | Показать help namespace. | нет | нет | group | `keep` |
| `/storage clear context` | Удалить context, summary, facts, short-term, task state, branches и reports. | да | соответствующие JSON/JSONL | active | `needs-docs` |
| `/storage clear reports` | Очистить token reports. | да | token reports | active | `keep` |
| `/storage clear all --yes` | Очистить context, explicit memory, task state и их event logs; profiles и invariants не очищаются. | да | context, memory, task и reports | active | `needs-docs` |

### Memory и profiles

| command | purpose | state changed? | runtime files affected? | current status | target status |
|---|---|---:|---|---|---|
| `/memory` | Показать сводку memory subsystem. | нет | нет | active | `keep` |
| `/memory short`, `/memory working`, `/memory long` | Показать выбранный explicit memory layer. | нет | нет | active | `keep` |
| `/memory summary`, `/memory facts` | Показать summary memory или sticky facts. | нет | нет | active | `keep` |
| `/memory summary clear` | Очистить summary memory. | да | summary | hidden | `rename` → `/memory reset summary` |
| `/memory add short <text>` | Добавить short-term note. | да | short-term, memory events | active | `keep` |
| `/memory set working <key>: <value>` | Записать working memory. | да | working, memory events | active | `keep` |
| `/memory set long <key>: <value>` | Записать long-term memory. | да | long-term, memory events | active | `keep` |
| `/memory forget working <key>`, `/memory forget long <key>` | Удалить key из выбранного layer. | да | выбранный layer, memory events | active | `keep` |
| `/memory reset working` | Очистить working memory. | да | working, memory events | active | `keep` |
| `/memory reset all --yes` | Очистить все explicit memory layers. | да | short-term, working, long-term, memory events | active | `keep` |
| `/profile` | Показать сводку profile subsystem. | нет | нет | active | `keep` |
| `/profile list` | Показать список profiles. | нет | нет | active | `keep` |
| `/profile active` | Показать active profile, как `/profile show` без имени. | нет | нет | active | `merge` → `/profile show` |
| `/profile show [name]` | Показать active или named profile. | нет | нет | active | `keep` |
| `/profile create <name>`, `/profile use <name>` | Создать/активировать profile. | да | user profiles, profile events | active | `keep` |
| `/profile set language\|style\|format\|audience <value>` | Изменить scalar field active profile. | да | user profiles, profile events | active | `keep` |
| `/profile set preference\|constraint <key>: <value>` | Изменить map field active profile. | да | user profiles, profile events | active | `keep` |
| `/profile reset active --yes`, `/profile reset all --yes` | Очистить active profile или все profiles. | да | user profiles, profile events | active | `keep` |

### Task и invariants

| command | purpose | state changed? | runtime files affected? | current status | target status |
|---|---|---:|---|---|---|
| `/task` | Показать task state. | нет | нет | active | `keep` |
| `/task status` | Показать ту же информацию, что `/task`. | нет | нет | active | `merge` → `/task` |
| `/task start <title>` | Создать задачу на stage `planning`. | да | task state, task events | active | `keep` |
| `/task transition <stage>` | Выполнить controlled transition. | да | task state и/или task events | active | `keep` |
| `/task stage <stage>` | Guarded compatibility alias для transition. | да | task state и/или task events | compatibility | `remove` |
| `/task approve-plan`, `/task pass-validation` | Установить lifecycle guard flags. | да | task state, task events | active | `keep` |
| `/task step <text>`, `/task expected-action <text>` | Обновить текущий шаг или ожидаемое действие. | да | task state, task events | active | `keep` |
| `/task next`, `/task complete` | Выполнить разрешённый lifecycle transition. | да | task state, task events | active | `keep` |
| `/task pause`, `/task resume` | Изменить pause flag без смены stage. | да | task state, task events | active | `keep` |
| `/task reset --yes` | Очистить task state, сохранив audit log. | да | task state, task events | active | `keep` |
| `/task metadata <key>: <value>` | Записать task metadata. | да | task state, task events | active | `keep` |
| `/invariant` | Показать список invariants. | нет | нет | active | `keep` |
| `/invariant list` | Показать тот же список, что `/invariant`. | нет | нет | active | `merge` → `/invariant` |
| `/invariant show <id>` | Показать invariant. | нет | нет | active | `keep` |
| `/invariant add <category>: <text>` | Добавить hard invariant. | да | invariants, invariant events | active | `keep` |
| `/invariant rationale <id>: <text>`, `/invariant pattern <id>: <pattern>` | Дополнить invariant metadata. | да | invariants, invariant events | active | `keep` |
| `/invariant check <text>` | Проверить конфликт локально и записать audit event. | да, audit | invariant events | active | `keep` |
| `/invariant enable <id>`, `/invariant disable <id>` | Изменить enabled flag. | да | invariants, invariant events | active | `keep` |
| `/invariant remove <id>`, `/invariant reset --yes` | Удалить один или все invariants. | да | invariants, invariant events | active | `keep` |

### Branches, files и exit

| command | purpose | state changed? | runtime files affected? | current status | target status |
|---|---|---:|---|---|---|
| `/branch` | Показать help namespace. | нет | нет | group | `keep` |
| `/branch list` | Показать branches и checkpoints. | нет | нет | active | `keep` |
| `/branch checkpoint <name>` | Сохранить checkpoint current history/facts. | да | branches | active | `keep` |
| `/branch create <name>` | Создать и активировать branch. | да | messages, facts, branches | active | `keep` |
| `/branch switch <name>` | Переключить active branch и восстановить state. | да | messages, facts, branches | active | `keep` |
| `/branch <name>` | Deprecated shortcut для `/branch create <name>`. | да | messages, facts, branches | hidden | `remove` |
| `/file` | Показать help namespace. | нет | нет | group | `keep` |
| `/file analyze <path>` | Построить dry-run token report без API call. | нет | нет | active | `keep` |
| `/file ask <path>` | Отправить содержимое файла через обычный ask pipeline. | да | context, summary/facts, short-term, branches, reports; возможен invariant audit | active | `keep` |
| `/exit` | Завершить interactive loop. | нет | нет | active | `keep` |

### Legacy aliases

Все legacy aliases сейчас маршрутизируются с предупреждением `Deprecated command`. Они не
показываются в root autocomplete и имеют общий target status `remove`.

| command | purpose | state changed? | runtime files affected? | current status | target status |
|---|---|---:|---|---|---|
| `/quit` → `/exit` | Старое имя выхода. | нет | нет | legacy alias | `remove` |
| `/context` → `/status context` | Старый context status. | нет | нет | legacy alias | `remove` |
| `/tokens` → `/status tokens` | Старый token breakdown. | нет | нет | legacy alias | `remove` |
| `/last-report` → `/status report` | Старый token report. | нет | нет | legacy alias | `remove` |
| `/history`, `/history full` → `/status history ...` | Старый history namespace. | нет | нет | legacy alias | `remove` |
| `/strategy` → `/config strategy` | Старое изменение strategy. | да | in-memory | legacy alias | `remove` |
| `/summary-mode` → `/config summary` | Старое изменение summary mode. | да | in-memory | legacy alias | `remove` |
| `/context-mode` → `/config overflow` | Старое изменение overflow policy. | да | in-memory | legacy alias | `remove` |
| `/reset` → `/session reset` | Старый session reset. | да | session runtime | legacy alias | `remove` |
| `/clear-context` → `/storage clear context` | Старая очистка context runtime. | да | context runtime | legacy alias | `remove` |
| `/summary`, `/facts` → `/memory summary\|facts` | Старые memory views. | нет | нет | legacy alias | `remove` |
| `/remember short` → `/memory add short` | Старая запись short-term note. | да | short-term, memory events | legacy alias | `remove` |
| `/remember working`, `/remember long` → `/memory set ...` | Старая запись key-value memory. | да | выбранный layer, memory events | legacy alias | `remove` |
| `/forget working`, `/forget long` → `/memory forget ...` | Старое удаление memory key. | да | выбранный layer, memory events | legacy alias | `remove` |
| `/branches` → `/branch list` | Старый branch list. | нет | нет | legacy alias | `remove` |
| `/checkpoint` → `/branch checkpoint` | Старое создание checkpoint. | да | branches | legacy alias | `remove` |
| `/switch` → `/branch switch` | Старое переключение branch. | да | messages, facts, branches | legacy alias | `remove` |
| `/analyze-file` → `/file analyze` | Старый file dry-run. | нет | нет | legacy alias | `remove` |
| `/ask-file` → `/file ask` | Старый file request. | да | ask pipeline runtime | legacy alias | `remove` |

## Реализованный CLI-контракт

Интерактивный запуск без subcommand остаётся основным UX для человека:

```text
ai-advent-agent
```

Slash-команды остаются интерфейсом действий внутри живой session. Grouped CLI предоставляет
single-shot запросы, diagnostics, cleanup/reset, semantic state commands и MCP workflows для
automation, CI и tests. Реализованный contract:

```text
ai-advent-agent chat
ai-advent-agent ask ...
ai-advent-agent context inspect
ai-advent-agent context clear
ai-advent-agent memory inspect
ai-advent-agent memory clear
ai-advent-agent memory note add ...
ai-advent-agent memory set working ...
ai-advent-agent memory set long-term ...
ai-advent-agent memory forget working ...
ai-advent-agent memory forget long-term ...
ai-advent-agent profile show
ai-advent-agent profile reset
ai-advent-agent profile list
ai-advent-agent profile active
ai-advent-agent profile create ...
ai-advent-agent profile use ...
ai-advent-agent profile set ...
ai-advent-agent profile clear active
ai-advent-agent profile clear all
ai-advent-agent task show
ai-advent-agent task reset
ai-advent-agent task start ...
ai-advent-agent task set ...
ai-advent-agent task approve-plan
ai-advent-agent task pass-validation
ai-advent-agent task transition ...
ai-advent-agent task advance
ai-advent-agent task pause
ai-advent-agent task resume
ai-advent-agent task complete
ai-advent-agent task clear active
ai-advent-agent invariant list
ai-advent-agent invariant clear
ai-advent-agent invariant add ...
ai-advent-agent invariant enable ...
ai-advent-agent invariant disable ...
ai-advent-agent invariant remove ...
ai-advent-agent invariant set rationale ...
ai-advent-agent invariant pattern add ...
ai-advent-agent invariant pattern remove ...
ai-advent-agent invariant check ...
ai-advent-agent report tokens
ai-advent-agent report tokens clear
ai-advent-agent mcp discover remote
ai-advent-agent mcp tracker issue ...
ai-advent-agent mcp scheduler run
ai-advent-agent mcp compose run
ai-advent-agent mcp orchestrate run
```

Scenario layer не восстанавливается. Текущая MCP-реализация доступна как Python API в
`ai_advent_agent.mcp.*`; старые top-level `ai_advent_agent.mcp_*` modules существуют только как
compatibility wrappers.

## Что больше не поддерживается

- console entry point `ai-advent-scenarios`;
- импорт `ai_advent_agent.scenarios`;
- day-specific commands актуального package;
- предположение, что интерфейс любого snapshot обязан существовать в `packages/`;
- undocumented compatibility aliases как бессрочный публичный contract.

Исторические команды и runners доступны в соответствующих `weeks/**/snapshot/**`.

## Правила обратной совместимости

Текущий canonical contract определяется этим документом, `ai-advent-agent --help` и `/help`.
Legacy aliases поддерживаются временно и уже выводят deprecation warning.

При реорганизации интерфейса функциональная возможность должна сохраниться, получить
документированную замену либо быть явно снята с поддержки. Для rename/merge нужно обновить help,
документацию и offline tests. Compatibility со snapshots не требуется: snapshots остаются
самодостаточной immutable history.

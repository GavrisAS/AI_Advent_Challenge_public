# ai_advent_agent

Актуальная развивающаяся версия AI harness.

Пакет сохраняет persistent context, token accounting, context strategies, summary memory,
memory layers, user profiles, task state, hard invariants и controlled transitions. MCP-часть
содержит clients, stdio servers, tool calls, scheduler persistence, tool composition и
multi-server orchestration.

RAG-часть содержит загрузку документов, fixed-size и structure-aware chunking, локальные Ollama
и deterministic hash embeddings, JSON/SQLite indexes и cosine retrieval без генеративного слоя.

Runtime-1 выделил request preparation, prompt assembly, overflow handling и preflight token report
construction в `ai_advent_agent.runtime`. Runtime-2 добавил туда store wiring, in-memory runtime
state loading, path/save helpers и optional event append wrappers. Runtime-3 вынес domain services
для memory/profile/task/invariant. Runtime-4 вынес summary/facts/branch/token/response helpers.
Public behavior `SimpleAgent`, constructor signature, interactive/chat/ask CLI, MCP grouped
commands и event payload formats не менялись.

Правила развития описаны в
[`packages/docs/development-rules.md`](../docs/development-rules.md).

Текущий CLI-контракт, runtime-файлы и slash-команды описаны в
[`packages/docs/cli.md`](../docs/cli.md).

Безопасные examples для CLI и MCP workflows собраны в
[`packages/docs/examples.md`](../docs/examples.md).

## Архитектура

| Subpackage/module | Ответственность |
|---|---|
| `ai_advent_agent.agent` | `SimpleAgent` как public facade над runtime services. |
| `ai_advent_agent.cli` | Parser, interactive/chat, `ask`, diagnostics, cleanup/reset, semantic CLI и MCP CLI. |
| `ai_advent_agent.runtime` | Request preparation, prompt assembly, overflow, state/stores/events, memory/profile/task/invariant services, summary/facts/branch/token/response helpers. |
| `ai_advent_agent.mcp` | Discovery, Tracker tool server/client, scheduler, composition и orchestration. |
| `ai_advent_agent.mcp_*` | Thin compatibility wrappers для старых imports; новая разработка использует `ai_advent_agent.mcp.*`. |
| `ai_advent_agent.rag` | Document loading, chunking, embeddings, local stores, comparison и search. |

## Интерактивный агент

Основной и единственный пользовательский entry point актуального пакета:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent \
  --context-strategy sticky_facts \
  --summary-mode off
```

Актуальные namespace-команды:

```text
/status  /config  /session  /storage  /memory  /profile
/task    /invariant  /branch  /file  /help
```

Введите `/` для autocomplete menu или `/help legacy` для временных compatibility aliases.
Для запуска без autocomplete используйте `--plain-input`.

Пользовательский entry point остаётся `ai_advent_agent.cli:main`, а внутренняя реализация CLI
разделена на parser, runtime paths, agent factory, single-shot runner, cleanup runner, interactive
loop и read-only diagnostics.

## Single-shot ask

Для CI, скриптов и быстрой автоматизации доступен single-shot режим:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent ask "текст запроса"
echo "текст запроса" | uv run --project packages/ai_advent_agent ai-advent-agent ask --stdin
```

`ask` строит тот же `SimpleAgent`, что interactive mode, вызывает `SimpleAgent.ask()` и требует
`DEEPSEEK_API_KEY`. Runtime options вроде `--no-persist`, `--no-load-context`, `--context-file`,
`--summary-file` и `--token-report-file` работают так же, как в interactive mode.

## Read-only diagnostics

Grouped commands читают локальный runtime state, не создают `SimpleAgent` и не требуют
`DEEPSEEK_API_KEY`:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent context inspect
uv run --project packages/ai_advent_agent ai-advent-agent memory inspect
uv run --project packages/ai_advent_agent ai-advent-agent profile show
uv run --project packages/ai_advent_agent ai-advent-agent task show
uv run --project packages/ai_advent_agent ai-advent-agent invariant list
uv run --project packages/ai_advent_agent ai-advent-agent report tokens
```

Явный `ai-advent-agent chat` запускает тот же interactive mode. Semantic task/invariant commands
описаны ниже. MCP CLI описан отдельной секцией.

## Runtime cleanup

Cleanup/reset commands удаляют только явно выбранные runtime-файлы, не создают `SimpleAgent` и не
требуют `DEEPSEEK_API_KEY`:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent context clear --yes
uv run --project packages/ai_advent_agent ai-advent-agent memory clear --all --dry-run --yes
uv run --project packages/ai_advent_agent ai-advent-agent report tokens clear --yes
```

Все destructive cleanup commands требуют `--yes`; `--dry-run` ничего не удаляет. Event logs
`memory_events.jsonl`, `profile_events.jsonl`, `task_events.jsonl` и `invariant_events.jsonl`
остаются audit trail и не очищаются этим слоем.

## Semantic memory writes

Explicit memory layers можно изменять grouped CLI-командами без `DEEPSEEK_API_KEY`, `SimpleAgent`
и LLM call:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent memory note add "короткая заметка"
uv run --project packages/ai_advent_agent ai-advent-agent memory set working current_task "docs-pass"
uv run --project packages/ai_advent_agent ai-advent-agent memory set long-term style "кратко"
uv run --project packages/ai_advent_agent ai-advent-agent memory forget working current_task --yes
```

Real write/delete operations append `memory_events.jsonl`. `--dry-run` показывает planned action и
не меняет файлы; forget-команды требуют `--yes`. Profile, task, invariant и MCP commands описаны
ниже.

## Semantic profile commands

User profiles можно читать и изменять grouped CLI-командами без `DEEPSEEK_API_KEY`, `SimpleAgent`
и LLM call:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent profile list
uv run --project packages/ai_advent_agent ai-advent-agent profile active
uv run --project packages/ai_advent_agent ai-advent-agent profile create reviewer
uv run --project packages/ai_advent_agent ai-advent-agent profile set language "русский"
uv run --project packages/ai_advent_agent ai-advent-agent profile set preference tone "direct"
uv run --project packages/ai_advent_agent ai-advent-agent profile clear active --yes
```

Real write/clear operations append `profile_events.jsonl`. `--dry-run` показывает planned action и
не меняет файлы; `profile clear active/all` требуют `--yes`. `profile reset --yes` остаётся
cleanup-командой удаления profiles file.

## Semantic task commands

Task state machine можно изменять grouped CLI-командами без `DEEPSEEK_API_KEY`, `SimpleAgent` и
LLM call:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent task start "Final docs pass"
uv run --project packages/ai_advent_agent ai-advent-agent task set step "run tests"
uv run --project packages/ai_advent_agent ai-advent-agent task approve-plan
uv run --project packages/ai_advent_agent ai-advent-agent task transition execution
uv run --project packages/ai_advent_agent ai-advent-agent task clear active --yes
```

Команды используют controlled lifecycle `planning -> execution -> validation -> done`. Real writes
append `task_events.jsonl`; `--dry-run` ничего не меняет. `task clear active --yes` очищает payload
в `task_state.json`, а `task reset --yes` остаётся cleanup-командой удаления task state file.

## Semantic invariant commands

State invariants можно изменять и проверять grouped CLI-командами без `DEEPSEEK_API_KEY`,
`SimpleAgent` и LLM call:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent invariant add architecture "Не менять snapshots"
uv run --project packages/ai_advent_agent ai-advent-agent invariant pattern add architecture-001 "snapshot"
uv run --project packages/ai_advent_agent ai-advent-agent invariant check "обнови snapshot"
uv run --project packages/ai_advent_agent ai-advent-agent invariant disable architecture-001
uv run --project packages/ai_advent_agent ai-advent-agent invariant remove architecture-001 --yes
```

Real mutations append `invariant_events.jsonl`; `--dry-run` ничего не меняет. `invariant remove`
и `invariant pattern remove` требуют `--yes`. `invariant check` является read-only по умолчанию и
не пишет event log. `invariant clear --yes` остаётся cleanup-командой удаления invariants file.

## MCP grouped CLI

MCP workflows доступны через единый entry point `ai-advent-agent`:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent mcp discover remote
uv run --project packages/ai_advent_agent ai-advent-agent mcp tracker issue AI-17 --include-comments
uv run --project packages/ai_advent_agent ai-advent-agent mcp scheduler run --issue-key AI-17 --issue-key AI-19
uv run --project packages/ai_advent_agent ai-advent-agent mcp compose run --planner scripted
uv run --project packages/ai_advent_agent ai-advent-agent mcp orchestrate run --planner scripted
```

Команды используют `ai_advent_agent.mcp.*`, не создают `SimpleAgent` и не вызывают
`agent_factory.build_agent()`. Parser/help и non-MCP grouped commands не импортируют MCP SDK;
heavy MCP modules загружаются только при выполнении `mcp ...`.

`mcp discover remote` по умолчанию использует DeepWiki MCP URL из
`ai_advent_agent.mcp.discovery` и может требовать network. Local tracker/scheduler workflows и
`scripted` planner modes не требуют `DEEPSEEK_API_KEY`; `llm-json` planner modes для composition и
orchestration требуют `DEEPSEEK_API_KEY`.

## Core capabilities

- `agent.py`, `runtime/`, `context_management.py`, `token_counter.py`, `token_report.py` —
  диалог, runtime state/persistence wiring, domain services, контекст и token budget;
- `memory_layers.py`, `user_profile.py`, `task_state.py`, `invariants.py` — явные слои состояния;
- `ai_advent_agent.mcp.discovery`, `ai_advent_agent.mcp.tool_client`,
  `ai_advent_agent.mcp.scheduler_client` — MCP discovery, calls и scheduler workflow;
- `ai_advent_agent.mcp.composition_client`, `ai_advent_agent.mcp.orchestration_client` —
  composition и multi-server routing;
- `ai_advent_agent.mcp.*_server` modules — локальные deterministic tools и path-safe storage.
- `ai_advent_agent.rag` — reusable ingestion/indexing API без day-specific CLI и LLM answers.

Эти возможности тестируются напрямую через Python API. Отдельный CLI `ai-advent-scenarios` и
централизованный `scenarios.py` больше не входят в актуальный package.
Старые top-level MCP modules `mcp_*.py` оставлены только как thin compatibility wrappers вокруг
`ai_advent_agent.mcp.*`; новая разработка должна импортировать нейтральный subpackage.

## Исторические сценарии

Day-specific команды и воспроизводимые runners сохранены в соответствующих
`weeks/**/snapshot/**`. Они относятся к историческому состоянию дня и не являются compatibility
contract актуального harness.

Read-only grouped CLI работает вокруг актуальных stores. `ask` вызывает runtime pipeline агента.
Cleanup grouped CLI удаляет только runtime-файлы. Semantic memory write grouped CLI управляет
explicit memory layers через актуальные stores. Semantic profile grouped CLI управляет user
profiles через актуальные stores. Semantic task/invariant grouped CLI управляет task state machine
и state invariants через актуальные stores. MCP grouped CLI использует устойчивые
`ai_advent_agent.mcp.*` APIs без возврата scenario layer. `SimpleAgent` остаётся фасадом runtime.

## Проверки

Из корня репозитория:

```bash
make check
make safety
```

Package tests без обязательной сети:

```bash
uv run pytest packages/ai_advent_agent/tests -q
```

Remote MCP integration остаётся opt-in:

```bash
AI_ADVENT_RUN_MCP_INTEGRATION=1 \
uv run pytest packages/ai_advent_agent/tests/test_mcp_connection.py -q
```

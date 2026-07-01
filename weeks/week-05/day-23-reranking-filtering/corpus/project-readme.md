# AI Advent Challenge

Приватный полный репозиторий обучения AI Advent Challenge.

Репозиторий хранит ежедневные задания, снапшоты решений, учебные конспекты, приватные заметки, memory-bank и служебные настройки Codex CLI.

## Быстрые ссылки

- 🎓 [Лекции](learning/)
- 📝 [Дополнительные заметки](notes/)

## Статус

Курс рассчитан на 7 недель / 35 дней.

| Неделя | Дни | Тема | Статус |
|---|---|---|---|
| [Week 01](weeks/week-01/) | day-01 — day-05 | Базовые вызовы LLM API и prompting | ✅ done |
| [Week 02](weeks/week-02/) | day-06 — day-10 | Первый агент, persistence, token accounting, summary memory, context strategies | ✅ done |
| [Week 03](weeks/week-03/) | day-11 — day-15 | Memory, personalization, task state, invariants и controlled transitions | ✅ done |
| [Week 04](weeks/week-04/) | day-16 — day-20 | MCP | ✅ done |
| [Week 05](weeks/week-05/) | day-21 — day-25 | RAG | 🚧 in_progress |

## Структура

```text
weeks/             # задания по неделям и дням
packages/          # актуальная рабочая версия общего кода
learning/          # приватные лекции, конспекты и ссылки
notes/task_notes/  # приватные подробные учебные конспекты по дням
memory-bank/       # долговременная память проекта для Codex
scripts/           # safety-check и public export
templates/         # шаблоны README, заметок и логов
.codex/prompts/    # промпты для Codex CLI
.agents/skills/    # repo-scoped навыки
```

## Ежедневные задания

| День | Тема | Статус |
|---:|---|---|
| 01 | [LLM REST API](weeks/week-01/day-01-llm-rest-api/) | ✅ done |
| 02 | [Answer Format](weeks/week-01/day-02-answer-format/) | ✅ done |
| 03 | [Reasoning](weeks/week-01/day-03-reasoning/) | ✅ done |
| 04 | [Temperature](weeks/week-01/day-04-temperature/) | ✅ done |
| 05 | [Model Versions](weeks/week-01/day-05-model-versions/) | ✅ done |
| 06 | [First Agent](weeks/week-02/day-06-first-agent/) | ✅ done |
| 07 | [Save Context](weeks/week-02/day-07-save-context/) | ✅ done |
| 08 | [Tokens Accounting](weeks/week-02/day-08-tokens-accounting/) | ✅ done |
| 09 | [Context Management Summary](weeks/week-02/day-09-context-management-summary/) | ✅ done |
| 10 | [Context Management Strategies](weeks/week-02/day-10-context-management-strategies/) | ✅ done |
| 11 | [Memory Layers](weeks/week-03/day-11-memory-layers/) | ✅ done |
| 12 | [Assistant Personalization](weeks/week-03/day-12-assistant-personalization/) | ✅ done |
| 13 | [Task State Machine](weeks/week-03/day-13-task-state-machine/) | ✅ done |
| 14 | [State Invariants](weeks/week-03/day-14-state-invariants/) | ✅ done |
| 15 | [Controlled State Transitions](weeks/week-03/day-15-controlled-state-transitions/) | ✅ done |
| 16 | [MCP Connection](weeks/week-04/day-16-mcp-connection/) | ✅ done |
| 17 | [First MCP Tool](weeks/week-04/day-17-first-mcp-tool/) | ✅ done |
| 18 | [Scheduler Background Tasks](weeks/week-04/day-18-scheduler-background-tasks/) | ✅ done |
| 19 | [MCP Tool Composition](weeks/week-04/day-19-mcp-tool-composition/) | ✅ done |
| 20 | [Orchestration MCP](weeks/week-04/day-20-mcp-orchestration/) | ✅ done |

## Актуальный пакет

Текущая рабочая версия агента находится в `packages/ai_advent_agent/`. Пакет развивается
накопительно отдельно от historical snapshots и сейчас включает interactive/chat режим, single-shot
`ask`, grouped diagnostics, cleanup/reset, semantic memory/profile/task/invariant CLI и MCP CLI.

Краткая архитектура актуального harness:

| Компонент | Назначение |
|---|---|
| `ai_advent_agent.agent` | `SimpleAgent` как public facade. |
| `ai_advent_agent.cli` | Entry point `ai-advent-agent`, interactive/chat, `ask`, diagnostics, cleanup, semantic CLI и MCP CLI. |
| `ai_advent_agent.runtime` | Request preparation, prompt assembly, state/stores/services и token/response helpers. |
| `ai_advent_agent.mcp` | Discovery, Tracker, scheduler, composition и orchestration. |

Запуск интерактивного агента:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent --context-strategy sticky_facts --summary-mode off
```

В актуальном package больше нет отдельной команды `ai-advent-scenarios`. Context, memory, state и
MCP-возможности доступны через `ai-advent-agent`, core modules и package tests.

Исторические day-specific команды сохранены в `weeks/**/snapshot/**`. Для воспроизведения
конкретного задания используйте README дня и его snapshot, а не текущий package.

## Проверки

```bash
make format
make check
make safety
```

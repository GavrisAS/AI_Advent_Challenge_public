# Day 13 — Task State Machine

Сценарий выполнен offline, без API-вызовов:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios task-state-machine-demo
```

## Таблица стадий

| Snapshot | Stage | Paused | Done | Prompt tokens | Иллюстрируемое поведение |
|---|---|---:|---:|---:|---|
| `empty` | `-` | False | False | 74 | общий ответ без task state |
| `planning` | `planning` | False | False | 245 | следующий шаг — завершить план и перейти к execution |
| `execution` | `execution` | False | False | 245 | следующий шаг — выполнить текущий command/store task |
| `paused_execution` | `execution` | True | False | 251 | продолжение запрещено до /task resume; stage остаётся execution |
| `validation` | `validation` | False | False | 241 | следующий шаг — проверки и public export |
| `done` | `done` | False | True | 235 | задача завершена; новых действий не требуется |

## Таблица transitions

| Команда | Переход |
|---|---|
| `/task start <title>` | empty/no task -> planning |
| `/task next` | planning -> execution |
| `/task next` | execution -> validation |
| `/task next` или `/task complete` | validation -> done |
| `/task pause` | active stage сохраняется, `paused=true` |
| `/task resume` | stage сохраняется, `paused=false` |
| `/task reset --yes` | task state очищается |

## Prompt assembly order

Day 13 добавляет отдельный слой:

```text
system prompt -> active user profile -> long-term memory -> working memory -> task state -> short-term memory -> current user message
```

В offline-сценарии для наглядности используется минимальный порядок:

```text
system prompt -> working memory -> task state -> current user message
```

## Артефакты

Файлы сохранены в `weeks/week-03/day-13-task-state-machine/artifacts/agent-context`:

- `task_state.json`
- `task_events.jsonl`
- `token_reports.jsonl`
- `prompt_empty.json`
- `prompt_planning.json`
- `prompt_execution.json`
- `prompt_paused_execution.json`
- `prompt_validation.json`
- `prompt_done.json`

## Выводы

- Task state отделён от profile и memory: он хранит этап задачи, текущий шаг, ожидаемое действие
  и флаги выполнения.
- Пауза не превращается в отдельный stage: `paused=true` сохраняется рядом с текущим stage.
- После resume агент может продолжить с того же stage без повторного объяснения задачи.
- Token reports показывают, активен ли task state и сколько prompt tokens добавляет этот слой.

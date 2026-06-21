# Day 15 — Controlled State Transitions

Сценарий выполнен offline, без API-вызовов:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios controlled-state-transitions-demo
```

## States

| Snapshot | Stage | Plan approved | Validation | Paused | Done | Allowed next | Tokens |
|---|---|---:|---:|---:|---:|---|---:|
| `empty` | `-` | False | False | False | False | `-` | 77 |
| `planning_unapproved` | `planning` | False | False | False | False | `-` | 228 |
| `planning_approved` | `planning` | True | False | False | False | `execution` | 224 |
| `execution` | `execution` | True | False | False | False | `validation` | 225 |
| `paused_execution` | `execution` | True | False | True | False | `-` | 226 |
| `validation` | `validation` | True | False | False | False | `-` | 229 |
| `done` | `done` | True | True | False | True | `-` | 225 |

## Allowed transitions

| From | To | Guard |
|---|---|---|
| `planning` | `execution` | `plan_approved=true` |
| `execution` | `validation` | task is not paused |
| `validation` | `done` | `validation_passed=true` |
| active stage | same stage | rejected |
| `done` | any stage | rejected; start a new task with `/task start <title>` |

## Invalid transition checks

| Check | Transition | Allowed | Reason | Required action |
|---|---|---:|---|---|
| `execution_before_plan` | `planning` -> `execution` | False | нельзя перейти к реализации до утверждённого плана. | `/task approve-plan` |
| `done_before_validation` | `execution` -> `done` | False | нельзя завершить задачу без стадии validation. | `/task transition validation, затем /task pass-validation` |
| `while_paused` | `execution` -> `validation` | False | задача на паузе. | `/task resume` |
| `done_before_pass_validation` | `validation` -> `done` | False | нельзя завершить задачу без успешной validation. | `/task pass-validation` |

## Prompt assembly order

Актуальный агент сохраняет порядок Day 14:

```text
system -> invariants -> user_profile -> long_term_memory -> working_memory
       -> task_state -> short_term_memory -> current_user
```

В этом offline-сценарии используется минимальный проверочный prompt:

```text
system -> working_memory -> task_state -> current_user
```

## Артефакты

Файлы сохранены в `../artifacts/agent-context`:

- `task_state.json`
- `task_events.jsonl`
- `token_reports.jsonl`
- `prompt_empty.json`
- `prompt_planning_unapproved.json`
- `prompt_planning_approved.json`
- `prompt_execution.json`
- `prompt_paused_execution.json`
- `prompt_validation.json`
- `prompt_done.json`
- `invalid_transition_execution_before_plan.json`
- `invalid_transition_done_before_validation.json`
- `invalid_transition_while_paused.json`

## Выводы

- Нельзя перейти к `execution` без утверждённого плана.
- Нельзя перейти к `done` напрямую из `execution`.
- Нельзя завершить задачу из `validation`, пока validation не отмечена как passed.
- Нельзя менять stage, пока задача на паузе.
- После `/task resume` переходы продолжаются с сохранённого stage.
- Invalid transitions сохраняются в `task_events.jsonl` как audit trail и не меняют stage.

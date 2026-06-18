# Day 14 — State Invariants

Сценарий выполнен offline, без API-вызовов:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios state-invariants-demo
```

## Prompt assembly

Day 14 добавляет hard invariant layer сразу после system prompt:

```text
system -> invariants -> user_profile -> long_term_memory -> working_memory
       -> task_state -> short_term_memory -> current_user
```

## Сравнение вариантов

| Вариант | Prompt tokens | Projected tokens | Conflict | Conflicts | Иллюстрируемое поведение |
|---|---:|---:|---|---:|---|
| `without_invariants` | 201 | 1 201 | False | 0 | обычный prompt без hard invariant layer |
| `with_invariants` | 413 | 1 413 | False | 0 | ответ следует hard constraints до profile/memory/task |
| `conflict_refusal` | 294 | 294 | True | 2 | локальный отказ; LLM API не вызывается |

## Local refusal

```text
Запрос отклонён локальным deterministic guard: он конфликтует с активными invariants.
- architecture-001 [architecture]: Storage учебного агента остаётся JSON/JSONL. (pattern: перейти на sqlite)
- architecture-001 [architecture]: Storage учебного агента остаётся JSON/JSONL. (pattern: удалить json storage)
LLM API не вызывался; обычная история диалога не изменена.
```

## Артефакты

Файлы сохранены в `../artifacts/agent-context`:

- `invariants.json`
- `invariant_events.jsonl`
- `token_reports.jsonl`
- `prompt_without_invariants.json`
- `prompt_with_invariants.json`
- `prompt_conflict_preflight.json`
- `local_refusal.txt`

## Выводы

- Invariants отделены от profile, memory и task state: это hard constraints, а не preference
  guidance.
- Conflict guard выполняется до sticky facts extraction и до основного LLM-вызова.
- При конфликте сохраняются invariant event и token report, но обычная история диалога не
  пополняется user/assistant turn.
- Offline-сценарий показывает оба уровня защиты: deterministic preflight и prompt-level
  instructions для неконфликтных запросов.

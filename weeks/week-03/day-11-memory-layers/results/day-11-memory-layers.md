# Day 11 — Memory Layers

Сценарий выполнен offline, без API-вызовов:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios memory-layers-demo
```

## Таблица memory layers

| Слой | Что хранит | Файл |
|---|---|---|
| Short-term | Последние реплики и явные short notes | `short_term_memory.json` |
| Working | Текущая задача, ограничения и checklist | `working_memory.json` |
| Long-term | Профиль, предпочтения, решения и знания | `long_term_memory.json` |
| Memory events | Журнал явных операций remember/forget/reset | `memory_events.jsonl` |

## Примеры данных

- Long-term: язык `русский`, стиль `кратко и технически`.
- Working: задача, отдельные файлы памяти, checklist по reports.
- Short-term: последние реплики о демонстрации разделения файлов памяти.

## Prompt assembly

Сборка prompt в варианте `all_layers`:

1. system prompt;
2. long-term memory;
3. working memory;
4. short-term memory;
5. текущее сообщение пользователя.

Файлы prompt сохранены в `../artifacts/agent-context`:

- `prompt_no_memory.json`
- `prompt_working_memory.json`
- `prompt_all_memory_layers.json`

## Сравнение поведения

| Вариант | Prompt tokens | Projected tokens | Иллюстрируемое поведение |
|---|---:|---:|---|
| `no_memory` | 97 | 1 097 | общий ответ без персонализации и без состояния текущей задачи |
| `working_only` | 201 | 1 201 | ответ учитывает текущую задачу, но без профиля и последних уточнений |
| `all_layers` | 416 | 1 416 | ответ на русском, краткий, с учётом задачи и последних уточнений |

## Как слои влияют на ответ

- Без memory layers агент отвечает обобщённо.
- С working memory агент учитывает текущую задачу и ограничения.
- Со всеми слоями агент учитывает профиль, задачу и последние уточнения.

## Артефакты

- `artifacts/agent-context/short_term_memory.json`
- `artifacts/agent-context/working_memory.json`
- `artifacts/agent-context/long_term_memory.json`
- `artifacts/agent-context/memory_events.jsonl`
- `artifacts/agent-context/token_reports.jsonl`

## Выводы

Memory layers делают stateful-поведение наблюдаемым: разные типы данных физически разделены,
сохраняются только явными командами и отдельно участвуют в prompt assembly. Это снижает риск
memory pollution и позволяет объяснить, почему ответ агента изменился.

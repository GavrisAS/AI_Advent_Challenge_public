# Day 10 — сравнение context management strategies

Сценарий выполнен offline, без API-вызовов:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios \
  context-strategies-comparison \
  --output-dir weeks/week-02/day-10-context-management-strategies/artifacts/agent-context
```

Тема синтетического диалога: сбор технического задания на AI-агента для инженерной работы в репозитории. В начале диалога специально зафиксированы факты, которые легко потерять при обрезании истории: цель, название проекта, ограничения безопасности, стиль ответа и договорённости.

## Таблица сравнения

| Стратегия | Что отправляется в запрос | Prompt tokens | Projected tokens | Качество ответа | Стабильность | Удобство |
|---|---|---:|---:|---|---|---|
| Sliding Window | System prompt + последние 6 сообщений | 227 | 1 227 | Среднее | Ранние цель и ограничения потеряны | Простая настройка, но пользователю нужно повторять важные факты |
| Sticky Facts | System prompt + facts + последние 6 сообщений | 385 | 1 385 | Высокое | Ранние факты сохранены в key-value memory | Удобно для требований, ограничений и предпочтений |
| Branching | System prompt + facts + состояние активной ветки | 366 | 1 366 | Высокое | Ветки изолируют альтернативные решения | Удобно для сравнения вариантов, но требует команд checkpoint/branch/switch |

## Token estimates

- `sliding_window`: минимальный prompt, но теряет старые детали.
- `sticky_facts`: prompt больше из-за блока facts, зато устойчивее к потере ранних требований.
- `branching`: расход близок к sticky facts, но зависит от размера активной ветки и checkpoint.
- Во всех строках `summary_active=false`, `summary_tokens_estimated=0`: Day 10 comparison не использует summary memory.

## Артефакты

Файлы сохранены в `artifacts/agent-context/`:

- `sliding_window_messages.json` — пример запроса после обрезания истории.
- `sticky_facts_messages.json` — пример запроса с facts и последними сообщениями.
- `branching_active_messages.json` — пример состояния активной ветки.
- `facts.json` — sticky facts в формате key-value.
- `branches.json` — checkpoint и две независимые ветки.
- `token_reports.jsonl` — token reports для трёх стратегий.

## Выводы

Sliding window дешевле и проще всего, но не подходит для задач, где ранние требования критичны. Sticky facts лучше сохраняет цель, ограничения, предпочтения и решения, особенно если extraction делается LLM-модулем и хранится отдельно от raw history. Branching полезен, когда нужно безопасно исследовать альтернативные решения от одного checkpoint, не смешивая состояния диалога.

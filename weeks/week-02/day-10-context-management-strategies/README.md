# Day 10 — Context Management Strategies
## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1e1NrlZqFp0cS10ybd4TIUkA8mzqCVfEn)

## Исходное условие

🔥 День 10. Управление контекстом: разные стратегии (без summary)

Реализуйте в агенте 3 разных стратегии управления контекстом минимум, и переключатель между ними:

Стратегия 1: Sliding Window

- храните только последние N сообщений;
- всё остальное отбрасывайте.

Стратегия 2: Sticky Facts / Key-Value Memory

- введите отдельный блок facts, который хранит важные данные из диалога: цель, ограничения, предпочтения, решения, договорённости;
- обновляйте facts после каждого сообщения пользователя;
- в запрос отправляйте: facts + последние N сообщений.

Стратегия 3: Branching

- сохраните checkpoint в диалоге;
- создайте 2 ветки от одного места;
- продолжите диалог в каждой ветке независимо;
- переключайтесь между ветками.

Протестируйте на одном и том же сценарии: собираем ТЗ 10–15 сообщений. Сравните качество ответа, стабильность важных деталей, расход токенов и удобство пользователя.

Результат: агент с 3 стратегиями управления контекстом (Sliding Window / Facts / Branching) + сравнение результатов.

Формат: видео + код.

## Цель задания

Сравнить несколько стратегий управления контекстом без summary и понять, какие компромиссы они дают для agentic workflow: экономия токенов, устойчивость памяти, наблюдаемость состояния и работа с альтернативными ветками.

## Реализация

В актуальный пакет `packages/ai_advent_agent/` добавлены три context strategy:

- `sliding_window` — сохраняет и отправляет system prompt + последние N сообщений.
- `sticky_facts` — делает отдельный LLM extraction step, сохраняет facts в JSON и отправляет facts + последние N сообщений.
- `branching` — хранит checkpoints и независимые ветки в JSON, позволяет создавать ветку и переключаться между ветками.

Response strategy `--strategy direct|step_by_step` осталась отдельной настройкой и не смешивается с `--context-strategy`.

Summary memory Day 09 сохранена, но Day 10 comparison запускается с `summary-mode=off` и в token reports имеет `summary_active=false`.

## Структура файлов

```text
.
├── README.md
├── snapshot/
├── results/
│   └── day-10-context-strategies-comparison.md
└── artifacts/
    └── agent-context/
        ├── branching_active_messages.json
        ├── branches.json
        ├── facts.json
        ├── sliding_window_messages.json
        ├── sticky_facts_messages.json
        └── token_reports.jsonl
```

## Как запустить

Актуальный пакет:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios \
  context-strategies-comparison \
  --output-dir weeks/week-02/day-10-context-management-strategies/artifacts/agent-context
```

Интерактивный агент из актуального пакета:

```bash
uv run --project packages/ai_advent_agent ai-advent-agent \
  --context-strategy sticky_facts \
  --summary-mode off \
  --recent-messages-limit 6 \
  --context-file weeks/week-02/day-10-context-management-strategies/artifacts/agent-context/messages.json \
  --facts-file weeks/week-02/day-10-context-management-strategies/artifacts/agent-context/facts.json \
  --branches-file weeks/week-02/day-10-context-management-strategies/artifacts/agent-context/branches.json \
  --token-report-file weeks/week-02/day-10-context-management-strategies/artifacts/agent-context/token_reports.jsonl
```

Команды внутри интерактивного CLI:

```text
/context
/tokens
/facts
/branches
/checkpoint base
/branch option-a
/switch option-a
/reset
/help
```

Snapshot:

```bash
cd weeks/week-02/day-10-context-management-strategies/snapshot
uv run day10-scenarios context-strategies-comparison
```

## Сценарий демонстрации для видео

Запускать из `snapshot/`, а runtime-артефакты сохранять в папку дня:

```bash
cd weeks/week-02/day-10-context-management-strategies
mkdir -p artifacts/agent-context

cd snapshot

uv run day10-scenarios \
  context-strategies-comparison \
  --output-dir ../artifacts/agent-context
```

Интерактивный агент для видео:

```bash
uv run day10-agent \
  --context-strategy sticky_facts \
  --summary-mode off \
  --context-file ../artifacts/agent-context/messages.json \
  --facts-file ../artifacts/agent-context/facts.json \
  --branches-file ../artifacts/agent-context/branches.json \
  --token-report-file ../artifacts/agent-context/token_reports.jsonl
```

Что показать в видео:

- запуск offline-сценария сравнения;
- запуск интерактивного агента;
- `/context`;
- `/facts`;
- `/checkpoint base`;
- `/branch option-a`;
- `/switch option-a`;
- `/branches`;
- `/tokens`;
- файлы в `artifacts/agent-context/`.

## Результаты

- [Сравнение стратегий](results/day-10-context-strategies-comparison.md)
- [Демонстрационные runtime-артефакты](artifacts/agent-context/)

Краткий вывод: sliding window дешевле, но теряет ранние требования; sticky facts устойчивее для целей, ограничений и предпочтений; branching удобен для независимого сравнения альтернатив от одного checkpoint.

## Выводы

Day 10 показывает, что управление контекстом — отдельный слой agent harness. Для реальной работы недостаточно просто сохранять `messages`: нужно явно выбирать, что отправлять в LLM, какие факты хранить структурно и как изолировать альтернативные ветки диалога.

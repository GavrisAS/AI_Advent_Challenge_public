# Day 14 — State Invariants

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1B1H63sr7C21wqV-B6zMu2l3k3twToKUo)

## Исходное условие

🔥 День 14. Инварианты и ограничения состояния

Добавьте в ассистента инварианты, которые он не имеет права нарушать.

Примеры инвариантов:

👉 выбранная архитектура
👉 принятые технические решения
👉 ограничения по стеку
👉 бизнес-правила

Сделайте так, чтобы:

👉 инварианты хранились отдельно от диалога
👉 ассистент явно учитывал их в рассуждениях
👉 ассистент отказывался предлагать решения, которые их нарушают

Проверьте:

👉 что происходит при конфликте запроса и инварианта
👉 как ассистент объясняет отказ

Результат:

Ассистент, который работает в рамках заданных инвариантов

Формат:

Видео + Код / Текст

## Цель задания

Добавить first-class слой `invariants`, отделённый от user profile, memory layers и task state.
Invariants работают как hard constraints: они попадают в prompt сразу после system prompt, а
очевидные конфликты отсекаются локальным deterministic guard до любых LLM-вызовов.

## Реализация

Статус: `✅ done`.

В актуальный пакет `packages/ai_advent_agent/` добавлен слой state invariants:

- `invariants.json` хранит список правил с категориями `architecture`, `technical_decision`,
  `stack_constraint`, `business_rule`;
- `invariant_events.jsonl` хранит append-only audit log операций и conflict checks;
- id генерируются по категориям: `architecture-001`, `decision-001`, `stack-001`,
  `business-001`;
- prompt assembly для активных invariants: `system → invariants → user_profile →
  long_term_memory → working_memory → task_state → short_term_memory → current_user`;
- conflict guard проверяет reject patterns case-insensitive до sticky facts extraction и до
  основного LLM-вызова;
- при конфликте агент возвращает локальный refusal, пишет event и token report с
  `total_tokens_actual=0`, не добавляя обычный user turn в history;
- CLI получил флаги `--invariants-file`, `--invariant-events-file` и env-переменные
  `AI_ADVENT_INVARIANTS_FILE`, `AI_ADVENT_INVARIANT_EVENTS_FILE`;
- `--no-persist` отключает invariant store и event store вместе с остальными runtime-файлами;
- offline-сценарий `state-invariants-demo` создаёт prompt snapshots, refusal и результаты без
  `DEEPSEEK_API_KEY`.

## Новые команды

| Команда | Назначение | Пример |
|---|---|---|
| `/invariant` | Показать список invariants. | `/invariant` |
| `/invariant list` | Показать все invariants. | `/invariant list` |
| `/invariant show <id>` | Показать invariant по id. | `/invariant show architecture-001` |
| `/invariant add <category>: <text>` | Добавить hard invariant. | `/invariant add architecture: Storage остаётся JSON/JSONL` |
| `/invariant rationale <id>: <text>` | Добавить обоснование правила. | `/invariant rationale architecture-001: Snapshot должен быть читаемым` |
| `/invariant pattern <id>: <pattern>` | Добавить reject pattern для deterministic guard. | `/invariant pattern architecture-001: перейти на sqlite` |
| `/invariant check <text>` | Проверить текст на конфликт без API. | `/invariant check Давай перейти на SQLite` |
| `/invariant enable <id>` | Включить invariant. | `/invariant enable architecture-001` |
| `/invariant disable <id>` | Отключить invariant. | `/invariant disable architecture-001` |
| `/invariant remove <id>` | Удалить invariant. | `/invariant remove architecture-001` |
| `/invariant reset --yes` | Очистить все invariants. | `/invariant reset --yes` |

Autocomplete поддерживает:

- `/invariant ` → nested commands;
- `/invariant add ` → категории invariants;
- `/invariant reset ` → `--yes`;
- `/invariant show|enable|disable|remove|rationale|pattern ` → dynamic invariant ids.

## Структура файлов

```text
.
├── README.md
├── snapshot/
│   ├── .env.example
│   ├── pyproject.toml
│   ├── ai_advent_agent/
│   └── tests/
├── results/
│   └── day-14-state-invariants.md
└── artifacts/
    └── agent-context/
        ├── invariants.json
        ├── invariant_events.jsonl
        ├── token_reports.jsonl
        ├── prompt_without_invariants.json
        ├── prompt_with_invariants.json
        ├── prompt_conflict_preflight.json
        └── local_refusal.txt
```

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Day-specific offline runner удалён из актуального package. Текущие invariants проверяются package
tests; историческую демонстрацию запускайте из `Snapshot Day 14` ниже.

#### Online/interactive агент

Day-specific online/interactive walkthrough запускайте из `Snapshot Day 14` ниже. Актуальный
`packages/ai_advent_agent` содержит интегрированный invariant CLI/runtime, но не используется как
runner исторического сценария дня.

### Snapshot Day 14

#### Offline-сценарий

Snapshot-сценарий также offline и не требует `DEEPSEEK_API_KEY`. При запуске из `snapshot/` он
сохраняет проверяемые артефакты вне snapshot, в `../artifacts/agent-context`.

```bash
cd weeks/week-03/day-14-state-invariants/snapshot
uv run day14-scenarios state-invariants-demo
```

#### Online/interactive агент из snapshot

`day14-agent` требует `DEEPSEEK_API_KEY`, потому что отправляет неконфликтные пользовательские
запросы в LLM API. Runtime-файлы online-демо snapshot храните вне `snapshot/`, например в
`../artifacts/online-demo`:

```bash
cd weeks/week-03/day-14-state-invariants/snapshot

mkdir -p ../artifacts/online-demo

uv run day14-agent \
  --context-file ../artifacts/online-demo/messages.json \
  --summary-file ../artifacts/online-demo/summary.json \
  --facts-file ../artifacts/online-demo/facts.json \
  --branches-file ../artifacts/online-demo/branches.json \
  --short-term-memory-file ../artifacts/online-demo/short_term_memory.json \
  --working-memory-file ../artifacts/online-demo/working_memory.json \
  --long-term-memory-file ../artifacts/online-demo/long_term_memory.json \
  --memory-events-file ../artifacts/online-demo/memory_events.jsonl \
  --user-profiles-file ../artifacts/online-demo/user_profiles.json \
  --profile-events-file ../artifacts/online-demo/profile_events.jsonl \
  --invariants-file ../artifacts/online-demo/invariants.json \
  --invariant-events-file ../artifacts/online-demo/invariant_events.jsonl \
  --task-state-file ../artifacts/online-demo/task_state.json \
  --task-events-file ../artifacts/online-demo/task_events.jsonl \
  --token-report-file ../artifacts/online-demo/token_reports.jsonl \
  --context-strategy sticky_facts \
  --summary-mode off
```

Если терминал не поддерживает autocomplete menu, добавьте `--plain-input`.

## Сценарий демонстрации для видео

1. Показать структуру Day 14: `README.md`, `snapshot/`, `results/`, `artifacts/agent-context/`.
2. Запустить offline-сценарий из `Snapshot Day 14` по команде раздела `Как запустить`.
3. Открыть artifacts: `invariants.json`, `invariant_events.jsonl`, `token_reports.jsonl`,
   `prompt_with_invariants.json`, `prompt_conflict_preflight.json`, `local_refusal.txt`.
4. Показать в `results/day-14-state-invariants.md` строку `conflict_refusal` и `API calls: 0`.
5. Запустить interactive snapshot agent.
6. Ввести `/` и показать root menu с `/invariant`.
7. Ввести `/invariant ` и показать nested commands.
8. Добавить invariant и reject pattern:

```text
/invariant add architecture: Storage учебного агента остаётся JSON/JSONL
/invariant rationale architecture-001: JSON удобно инспектировать в snapshot
/invariant pattern architecture-001: перейти на sqlite
/invariant show architecture-001
```

9. Проверить конфликт без API:

```text
/invariant check Давай перейти на SQLite
```

10. Отправить обычный пользовательский запрос с тем же конфликтом и показать локальный refusal,
    token report с `invariant_conflict: true` и `total_tokens_actual: 0`.
11. Показать неконфликтный запрос, где prompt содержит invariants после system prompt.
12. Выполнить cleanup online-демо:

```text
/invariant reset --yes
/session reset
```

## Результаты

- Offline results: [results/day-14-state-invariants.md](results/day-14-state-invariants.md).
- Основные artifacts: [artifacts/agent-context/](artifacts/agent-context/).
- Сценарий создаёт локальный refusal без API-вызова и prompt snapshots для сравнения варианта с
  invariants и без них.

## Выводы

State invariants полезны как отдельный слой hard constraints: они не конкурируют с profile,
memory или task state и не зависят от качества ответа модели. Deterministic guard закрывает
очевидные конфликты до LLM-вызова, а prompt-level invariant block оставляет явное правило для
неконфликтных запросов. Token reports и event log делают это поведение наблюдаемым и
воспроизводимым.

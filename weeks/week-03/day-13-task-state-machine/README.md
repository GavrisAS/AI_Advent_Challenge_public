# Day 13 — Состояние задачи

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1pV713I3xpoKg8gg-FSqH-X9bTlXQBvtt)

## Исходное условие

🔥 День 13. Состояние задачи (Task State Machine)

Реализуйте состояние задачи как конечный автомат:

👉 этап задачи
👉 текущий шаг
👉 ожидаемое действие

Пример состояний:

👉 planning → execution → validation → done

Проверьте:

👉 паузу на любом этапе
👉 продолжение без повторных объяснений

Результат:

Агент с формализованным состоянием задачи

Формат:

Видео + Код / Текст

## Цель задания

Реализовать отдельный слой task state machine для агента: формализованный этап задачи, текущий
шаг, ожидаемое действие, флаг паузы и audit log переходов. Task state не смешивается с working
memory, long-term memory или user profile и включается в prompt assembly как самостоятельный state
layer.

## Реализация

Статус: `✅ done`.

В актуальный пакет `packages/ai_advent_agent/` добавлен first-class слой состояния задачи:

- `task_state.json` хранит текущую задачу, stage, current step, expected action, `done`, `paused`
  и metadata;
- `task_events.jsonl` хранит append-only журнал команд `/task`;
- task state вставляется в prompt после working memory и перед short-term memory;
- token reports фиксируют `task_state_active`, `task_stage`, `task_done`, `task_paused` и token
  impact;
- `--no-persist` отключает persistence task state так же, как остальные runtime stores;
- offline-сценарий `task-state-machine-demo` создаёт prompt snapshots для empty, planning,
  execution, paused execution, validation и done.

Каноническая цепочка этапов остаётся:

```text
planning → execution → validation → done
```

Пауза реализована отдельным флагом `paused: true`, поэтому `/task pause` не превращает stage в
`paused`, а `/task resume` продолжает работу с того же stage.

## Новые команды

| Команда | Назначение | Пример |
|---|---|---|
| `/task` | Показать текущий task state. | `/task` |
| `/task status` | Показать task state явно. | `/task status` |
| `/task start <title>` | Создать новую задачу на этапе `planning`. | `/task start Реализовать Day 13 task state machine` |
| `/task stage <stage>` | Явно задать stage. | `/task stage execution` |
| `/task step <text>` | Задать текущий шаг. | `/task step Добавить команды /task` |
| `/task expected-action <text>` | Задать ожидаемое действие. | `/task expected-action Запустить tests` |
| `/task next` | Перейти по цепочке `planning → execution → validation → done`. | `/task next` |
| `/task pause` | Поставить задачу на паузу без смены stage. | `/task pause` |
| `/task resume` | Продолжить задачу с сохранённого stage. | `/task resume` |
| `/task complete` | Завершить задачу и поставить `stage=done`. | `/task complete` |
| `/task reset --yes` | Очистить task state. | `/task reset --yes` |
| `/task metadata <key>: <value>` | Добавить metadata текущей задачи. | `/task metadata check: pytest` |

Autocomplete поддерживает:

- `/task ` → nested commands;
- `/task stage ` → `planning`, `execution`, `validation`, `done`;
- `/task reset ` → `--yes`.

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
│   └── day-13-task-state-machine.md
└── artifacts/
    └── agent-context/
        ├── task_state.json
        ├── task_events.jsonl
        ├── token_reports.jsonl
        ├── prompt_empty.json
        ├── prompt_planning.json
        ├── prompt_execution.json
        ├── prompt_paused_execution.json
        ├── prompt_validation.json
        └── prompt_done.json
```

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Offline-сценарий не вызывает LLM API и не требует `DEEPSEEK_API_KEY`.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios task-state-machine-demo
```

#### Online/interactive агент

Интерактивный агент вызывает DeepSeek API, поэтому нужен `DEEPSEEK_API_KEY` в окружении или
локальном `.env`. Ключи не сохраняются в репозитории.

Runtime-файлы online-демо актуального пакета держите вне дня, например в `.tmp/day13-online-demo`:

```bash
mkdir -p .tmp/day13-online-demo

uv run --project packages/ai_advent_agent ai-advent-agent \
  --context-file .tmp/day13-online-demo/messages.json \
  --summary-file .tmp/day13-online-demo/summary.json \
  --facts-file .tmp/day13-online-demo/facts.json \
  --branches-file .tmp/day13-online-demo/branches.json \
  --short-term-memory-file .tmp/day13-online-demo/short_term_memory.json \
  --working-memory-file .tmp/day13-online-demo/working_memory.json \
  --long-term-memory-file .tmp/day13-online-demo/long_term_memory.json \
  --memory-events-file .tmp/day13-online-demo/memory_events.jsonl \
  --user-profiles-file .tmp/day13-online-demo/user_profiles.json \
  --profile-events-file .tmp/day13-online-demo/profile_events.jsonl \
  --task-state-file .tmp/day13-online-demo/task_state.json \
  --task-events-file .tmp/day13-online-demo/task_events.jsonl \
  --token-report-file .tmp/day13-online-demo/token_reports.jsonl \
  --context-strategy sticky_facts \
  --summary-mode off
```

### Snapshot Day 13

#### Offline-сценарий

Snapshot-сценарий также offline и не требует `DEEPSEEK_API_KEY`. При запуске из `snapshot/` он
сохраняет проверяемые артефакты вне snapshot, в `../artifacts/agent-context`.

```bash
cd weeks/week-03/day-13-task-state-machine/snapshot
uv run day13-scenarios task-state-machine-demo
```

#### Online/interactive агент из snapshot

`day13-agent` требует `DEEPSEEK_API_KEY`, потому что отправляет пользовательские запросы в LLM API.
Runtime-файлы online-демо snapshot храните вне `snapshot/`, например в `../artifacts/online-demo`:

```bash
cd weeks/week-03/day-13-task-state-machine/snapshot

mkdir -p ../artifacts/online-demo

uv run day13-agent \
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
  --task-state-file ../artifacts/online-demo/task_state.json \
  --task-events-file ../artifacts/online-demo/task_events.jsonl \
  --token-report-file ../artifacts/online-demo/token_reports.jsonl \
  --context-strategy sticky_facts \
  --summary-mode off
```

Если терминал не поддерживает autocomplete menu, добавьте `--plain-input`.

## Сценарий демонстрации для видео

1. Показать структуру Day 13: `README.md`, `snapshot/`, `results/`, `artifacts/agent-context/`.
2. Запустить offline-сценарий:
   `uv run --project packages/ai_advent_agent ai-advent-scenarios task-state-machine-demo`.
3. Открыть artifacts: `task_state.json`, `task_events.jsonl`, `token_reports.jsonl` и prompt
   snapshots.
4. Запустить interactive snapshot agent.
5. Ввести `/` и показать root menu с `/task`.
6. Ввести `/task ` и показать nested commands.
7. Ввести `/task stage ` и показать completion `planning`, `execution`, `validation`, `done`.
8. Создать задачу:

```text
/task start Реализовать Day 13 task state machine
/task step Спроектировать модель состояния задачи
/task expected-action Добавить store, команды и tests
/task status
```

9. Задать обычный вопрос:

```text
Что мне делать дальше?
```

Ответ должен учитывать task state, потому что task block автоматически добавляется в prompt.

10. Перевести стадии и поставить паузу:

```text
/task next
/task step Добавить команды /task
/task expected-action Запустить tests
/task pause
/task status
```

11. Выйти, снова запустить агент с теми же files и показать, что состояние восстановилось.
12. Продолжить и завершить:

```text
/task resume
/task next
/task complete
/task status
```

13. Показать `task_events.jsonl` как audit trail.
14. Показать `token_reports.jsonl` с task metadata.

## Результаты

Результат сценария сохранён в
[results/day-13-task-state-machine.md](results/day-13-task-state-machine.md).

Ключевой результат: агент получил отдельное формализованное состояние задачи, которое сохраняется
между запусками, отображается в prompt assembly и позволяет продолжить работу после паузы без
повторного объяснения задачи.

## Выводы

Task state — это не память и не профиль. Working memory хранит рабочие факты задачи, user profile
хранит предпочтения пользователя, а task state machine хранит положение текущего workflow:
`stage`, `current_step`, `expected_action`, `done` и `paused`. Разделение этих слоёв делает
поведение агента наблюдаемым, тестируемым и пригодным для длинных задач с паузой и продолжением.

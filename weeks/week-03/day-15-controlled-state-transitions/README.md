# Day 15 — Контролируемые переходы состояний

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1tIpDscteb8NOBTqai9tO2QkjbtHrvPEU)

## Исходное условие

🔥 День 15. Контролируемые переходы состояний

Реализуйте явные переходы между состояниями задачи.

Сделайте так, чтобы:

👉 у задачи были допустимые состояния
👉 были разрешённые переходы между ними
👉 ассистент не мог “перепрыгнуть” этап

Пример:

👉 нельзя делать реализацию до утверждённого плана
👉 нельзя делать финал без валидации

Проверьте:

👉 попытки перейти в недопустимое состояние
👉 реакцию ассистента
👉 корректность продолжения после паузы

Результат:

Ассистент с контролируемым жизненным циклом задачи

Формат:

Видео + Код / Текст

## Цель задания

Усилить task state machine Day 13 контролируемым lifecycle: разрешёнными состояниями,
переходами, guard conditions, отказом при недопустимом переходе и audit trail. Task state остаётся
отдельным workflow layer и не смешивается с memory, user profile или invariants.

## Реализация

Статус: `✅ done`.

В актуальном пакете `packages/ai_advent_agent/` task state расширен полями
`plan_approved` и `validation_passed`. Переходы теперь проходят через explicit transition policy:

```text
planning -> execution -> validation -> done
```

Переход `planning -> execution` разрешён только после `/task approve-plan`, а
`validation -> done` — только после `/task pass-validation`. Попытка перейти из `execution` сразу
в `done` отклоняется, потому что пропускает validation. Флаг `paused` остаётся отдельным флагом и
блокирует переходы до `/task resume`.

Invalid transition не меняет stage и сохраняется в `task_events.jsonl` как `invalid_transition` с
`from_stage`, `target_stage`, `reason` и `required_action`. Prompt block task state показывает
lifecycle metadata: approved plan, passed validation и allowed next states. Token reports получили
поля `task_plan_approved`, `task_validation_passed`, `task_allowed_next_stages` и
`task_last_transition_allowed`.

## Новые команды

| Команда | Назначение | Пример |
|---|---|---|
| `/task transition <stage>` | Перейти к stage по controlled lifecycle. | `/task transition execution` |
| `/task approve-plan` | Утвердить план и разблокировать `planning -> execution`. | `/task approve-plan` |
| `/task pass-validation` | Отметить validation как пройденную и разблокировать `validation -> done`. | `/task pass-validation` |
| `/task next` | Перейти к следующему разрешённому stage. | `/task next` |
| `/task complete` | Завершить задачу только через validation guard. | `/task complete` |
| `/task pause` | Поставить задачу на паузу без смены stage. | `/task pause` |
| `/task resume` | Снять паузу и продолжить с сохранённого stage. | `/task resume` |
| `/task stage <stage>` | Compatibility alias для `/task transition <stage>` с теми же guards. | `/task stage validation` |

Также сохраняются команды Day 13: `/task`, `/task status`, `/task start <title>`,
`/task step <text>`, `/task expected-action <text>`, `/task reset --yes`,
`/task metadata <key>: <value>`.

Autocomplete поддерживает:

- `/task ` → nested commands;
- `/task transition ` → `planning`, `execution`, `validation`, `done`;
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
│   └── day-15-controlled-state-transitions.md
└── artifacts/
    ├── agent-context/
        ├── task_state.json
        ├── task_events.jsonl
        ├── token_reports.jsonl
        ├── prompt_empty.json
        ├── prompt_planning_unapproved.json
        ├── prompt_planning_approved.json
        ├── prompt_execution.json
        ├── prompt_paused_execution.json
        ├── prompt_validation.json
        ├── prompt_done.json
        ├── invalid_transition_execution_before_plan.json
        ├── invalid_transition_done_before_validation.json
        └── invalid_transition_while_paused.json
    └── online-demo/
        ├── branches.json
        ├── task_events.jsonl
        └── task_state.json
```

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Offline-сценарий не вызывает LLM API и не требует `DEEPSEEK_API_KEY`.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios controlled-state-transitions-demo
```

#### Online/interactive агент

Интерактивный агент вызывает DeepSeek API, поэтому нужен `DEEPSEEK_API_KEY` в окружении или
локальном `.env`. Ключи не сохраняются в репозитории.

Runtime-файлы online-демо актуального пакета держите вне дня, например в
`.tmp/day15-online-demo`:

```bash
mkdir -p .tmp/day15-online-demo

uv run --project packages/ai_advent_agent ai-advent-agent \
  --context-file .tmp/day15-online-demo/messages.json \
  --summary-file .tmp/day15-online-demo/summary.json \
  --facts-file .tmp/day15-online-demo/facts.json \
  --branches-file .tmp/day15-online-demo/branches.json \
  --short-term-memory-file .tmp/day15-online-demo/short_term_memory.json \
  --working-memory-file .tmp/day15-online-demo/working_memory.json \
  --long-term-memory-file .tmp/day15-online-demo/long_term_memory.json \
  --memory-events-file .tmp/day15-online-demo/memory_events.jsonl \
  --user-profiles-file .tmp/day15-online-demo/user_profiles.json \
  --profile-events-file .tmp/day15-online-demo/profile_events.jsonl \
  --task-state-file .tmp/day15-online-demo/task_state.json \
  --task-events-file .tmp/day15-online-demo/task_events.jsonl \
  --invariants-file .tmp/day15-online-demo/invariants.json \
  --invariant-events-file .tmp/day15-online-demo/invariant_events.jsonl \
  --token-report-file .tmp/day15-online-demo/token_reports.jsonl \
  --context-strategy sticky_facts \
  --summary-mode off
```

### Snapshot Day 15

#### Offline-сценарий

Snapshot-сценарий также offline и не требует `DEEPSEEK_API_KEY`. При запуске из `snapshot/` он
сохраняет проверяемые артефакты вне snapshot, в `../artifacts/agent-context`.

```bash
cd weeks/week-03/day-15-controlled-state-transitions/snapshot
uv run day15-scenarios controlled-state-transitions-demo
```

#### Online/interactive агент из snapshot

`day15-agent` требует `DEEPSEEK_API_KEY`, потому что отправляет пользовательские запросы в LLM API.
Runtime-файлы online-демо snapshot храните вне `snapshot/`, например в
`../artifacts/online-demo`:

```bash
cd weeks/week-03/day-15-controlled-state-transitions/snapshot

mkdir -p ../artifacts/online-demo

uv run day15-agent \
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
  --invariants-file ../artifacts/online-demo/invariants.json \
  --invariant-events-file ../artifacts/online-demo/invariant_events.jsonl \
  --token-report-file ../artifacts/online-demo/token_reports.jsonl \
  --context-strategy sticky_facts \
  --summary-mode off
```

Если терминал не поддерживает autocomplete menu, добавьте `--plain-input`.

## Сценарий демонстрации для видео

1. Показать структуру Day 15: `README.md`, `snapshot/`, `results/`, `artifacts/agent-context/`.
2. Запустить offline-сценарий:
   `uv run --project packages/ai_advent_agent ai-advent-scenarios controlled-state-transitions-demo`.
3. Открыть artifacts: `task_state.json`, `task_events.jsonl`, invalid transition JSON files,
   `token_reports.jsonl` и prompt snapshots.
4. Запустить interactive snapshot agent.
5. Ввести `/` и показать root menu с `/task`.
6. Ввести `/task ` и показать nested commands.
7. Ввести `/task transition ` и показать stage argument completion.
8. Создать задачу:

```text
/task start Реализовать controlled transitions для task state
/task step Согласовать план
/task expected-action Утвердить план перед реализацией
/task status
```

9. Попытаться перепрыгнуть:

```text
/task transition execution
```

Показать отказ: нужен `/task approve-plan`.

10. Утвердить план и перейти:

```text
/task approve-plan
/task transition execution
```

11. Попытаться перейти сразу в done:

```text
/task transition done
```

Показать отказ: нужна validation.

12. Показать pause/resume:

```text
/task pause
/task transition validation
/task resume
/task transition validation
```

13. Попытаться завершить без passed validation:

```text
/task complete
```

Показать отказ.

14. Пройти validation:

```text
/task pass-validation
/task complete
/task status
```

15. Показать `task_events.jsonl` как audit trail.

## Результаты

- Offline results: [results/day-15-controlled-state-transitions.md](results/day-15-controlled-state-transitions.md).
- Основные artifacts: [artifacts/agent-context/](artifacts/agent-context/).
- Артефакты записанной interactive-демонстрации: [artifacts/online-demo/](artifacts/online-demo/).
- Сценарий показывает invalid transitions до approved plan, при попытке пропустить validation и
  во время pause. API calls: `0`.

## Выводы

Controlled transitions превращают task state из произвольного поля stage в проверяемый lifecycle.
Агент больше не может перейти к реализации без утверждённого плана, завершить задачу без validation
или менять stage во время pause. Отказы сохраняют исходный state, объясняют required action и
оставляют audit trail в `task_events.jsonl`.

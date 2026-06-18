# Day 12 — Персонализация ассистента

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1s2TcZfHbkmfylMxQMTJMGZbP03m5Uaj_)

## Исходное условие

🔥 День 12. Персонализация ассистента

Добавьте персонализацию поверх модели памяти:

👉 создайте профиль пользователя  
👉 опишите предпочтения (стиль, формат, ограничения)  
👉 подключите профиль к каждому запросу

Проверьте:

👉 ответы для разных профилей  
👉 что ассистент учитывает автоматически

Результат:

Персонализированный агент, адаптированный под пользователя

Формат:

Видео + Текст

## Цель задания

Реализовать отдельный personalization layer поверх memory layers Day 11: профиль пользователя,
предпочтения ответа, ограничения и автоматическое включение активного профиля в prompt assembly.
Профиль не должен смешиваться с long-term memory, working memory или task state.

## Реализация

Статус: `📦 published`.

В актуальный пакет `packages/ai_advent_agent/` добавлена отдельная подсистема user profiles:

- `user_profiles.json` хранит именованные профили и активный профиль;
- `profile_events.jsonl` ведёт append-only audit trail команд `/profile`;
- `/profile create`, `/profile use`, `/profile set ...`, `/profile reset ...` управляют профилями явно;
- active profile вставляется в prompt после system prompt и до memory layers;
- token reports фиксируют `profile_active`, `active_profile_name`, количество полей и token impact;
- completion menu поддерживает static suggestions для `/profile set/reset` и dynamic suggestions для `/profile use/show`.

Offline-сценарий `assistant-personalization-demo` создаёт два профиля:

- `concise_engineer` — краткий инженерный стиль, проверяемые команды;
- `teacher` — обучающий стиль, объяснение причин, пример и критерии проверки.

Сценарий сохраняет prompt snapshots для одинакового запроса без профиля и с каждым активным
профилем.

## Новые команды

Day 12 добавляет новую namespace-группу `/profile` для явного управления personalization layer.
Legacy aliases для профилей не добавлялись: новые сценарии, README и autocomplete используют
только `/profile ...`.

| Команда | Назначение |
|---|---|
| `/profile` | Показать сводку profile subsystem, активный профиль и пути файлов состояния. |
| `/profile list` | Показать список созданных профилей и отметить активный профиль. |
| `/profile active` | Показать активный профиль со всеми полями, preferences и constraints. |
| `/profile show [name]` | Показать указанный профиль или активный профиль, если имя не передано. |
| `/profile create <name>` | Создать профиль и сразу сделать его активным. |
| `/profile use <name>` | Переключить активный профиль на уже созданный профиль. |
| `/profile set language <value>` | Задать язык ответов активного профиля. |
| `/profile set style <value>` | Задать стиль ответов активного профиля. |
| `/profile set format <value>` | Задать формат ответов активного профиля. |
| `/profile set audience <value>` | Задать аудиторию активного профиля. |
| `/profile set preference <key>: <value>` | Добавить или обновить preference активного профиля. |
| `/profile set constraint <key>: <value>` | Добавить или обновить constraint активного профиля. |
| `/profile reset active --yes` | Очистить поля активного профиля, сохранив сам профиль и active name. |
| `/profile reset all --yes` | Очистить все профили и active profile, сохранив audit trail событий. |

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
│   └── day-12-assistant-personalization.md
└── artifacts/
    ├── agent-context/
    │   ├── user_profiles.json
    │   ├── profile_events.jsonl
    │   ├── token_reports.jsonl
    │   ├── prompt_no_profile.json
    │   ├── prompt_concise_engineer.json
    │   └── prompt_teacher.json
    └── online-demo/
        ├── messages.json
        ├── user_profiles.json
        ├── profile_events.jsonl
        ├── token_reports.jsonl
        ├── branches.json
        ├── facts.json
        ├── short_term_memory.json
        └── summary.json
```

## Как запустить

### Актуальный пакет

#### Offline-сценарий

Offline-сценарий не вызывает LLM API и не требует `DEEPSEEK_API_KEY`.

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios assistant-personalization-demo
```

#### Online/interactive агент

Интерактивный агент вызывает DeepSeek API, поэтому перед запуском нужен `DEEPSEEK_API_KEY` в
окружении или в локальном `.env`. Ключи не сохраняются в репозитории.

Runtime-файлы online-демо актуального пакета держите вне дня, например в `.tmp/day12-online-demo`:

```bash
mkdir -p .tmp/day12-online-demo

uv run --project packages/ai_advent_agent ai-advent-agent \
  --context-file .tmp/day12-online-demo/messages.json \
  --token-report-file .tmp/day12-online-demo/token_reports.jsonl \
  --summary-file .tmp/day12-online-demo/summary.json \
  --facts-file .tmp/day12-online-demo/facts.json \
  --branches-file .tmp/day12-online-demo/branches.json \
  --short-term-memory-file .tmp/day12-online-demo/short_term_memory.json \
  --working-memory-file .tmp/day12-online-demo/working_memory.json \
  --long-term-memory-file .tmp/day12-online-demo/long_term_memory.json \
  --memory-events-file .tmp/day12-online-demo/memory_events.jsonl \
  --user-profiles-file .tmp/day12-online-demo/user_profiles.json \
  --profile-events-file .tmp/day12-online-demo/profile_events.jsonl
```

### Snapshot Day 12

#### Offline-сценарий

Snapshot-сценарий также offline и не требует `DEEPSEEK_API_KEY`. При запуске из `snapshot/` он
сохраняет проверяемые артефакты вне snapshot, в `../artifacts/agent-context`.

```bash
cd weeks/week-03/day-12-assistant-personalization/snapshot
uv run day12-scenarios assistant-personalization-demo
```

#### Online/interactive агент

`day12-agent` требует `DEEPSEEK_API_KEY`, потому что отправляет пользовательские запросы в LLM API.
Runtime-файлы online-демо snapshot храните вне `snapshot/`, например в `../artifacts/online-demo`:

```bash
cd weeks/week-03/day-12-assistant-personalization/snapshot
mkdir -p ../artifacts/online-demo

uv run day12-agent \
  --context-file ../artifacts/online-demo/messages.json \
  --token-report-file ../artifacts/online-demo/token_reports.jsonl \
  --summary-file ../artifacts/online-demo/summary.json \
  --facts-file ../artifacts/online-demo/facts.json \
  --branches-file ../artifacts/online-demo/branches.json \
  --short-term-memory-file ../artifacts/online-demo/short_term_memory.json \
  --working-memory-file ../artifacts/online-demo/working_memory.json \
  --long-term-memory-file ../artifacts/online-demo/long_term_memory.json \
  --memory-events-file ../artifacts/online-demo/memory_events.jsonl \
  --user-profiles-file ../artifacts/online-demo/user_profiles.json \
  --profile-events-file ../artifacts/online-demo/profile_events.jsonl
```

Если терминал не поддерживает autocomplete menu, добавьте `--plain-input`; при этом slash-команды
останутся рабочими, но меню completion не будет показано.

## Сценарий демонстрации для видео

1. Показать структуру дня: `README.md`, `snapshot/`, `results/`, `artifacts/agent-context/`.
2. Запустить offline demo из snapshot и подчеркнуть, что API-вызовов нет:
   `uv run day12-scenarios assistant-personalization-demo`.
3. Запустить `day12-agent` с runtime-файлами в `../artifacts/online-demo` и заранее настроенным
   `DEEPSEEK_API_KEY`.
4. Ввести `/`, показать root slash menu, затем `/profile ` и nested completion для команд профиля.
5. Создать профиль `concise_engineer`:

```text
/profile create concise_engineer
/profile set language русский
/profile set style кратко, технически, без вводных
/profile set preference examples: только если помогает принять решение
/profile show
```

6. Задать одинаковый рабочий вопрос с активным `concise_engineer`:

```text
Объясни, как встроить personalization layer в агента без смешивания с memory.
```

7. Создать и активировать профиль `teacher`, затем повторить тот же вопрос:

```text
/profile create teacher
/profile set style обучающе, с пояснением причин
/profile set format сначала идея, затем пример, затем критерии проверки
/profile use concise_engineer
/profile use teacher
Объясни, как встроить personalization layer в агента без смешивания с memory.
```

8. Показать файлы состояния в `../artifacts/online-demo`: `user_profiles.json`,
   `profile_events.jsonl`, `token_reports.jsonl`, `messages.json`.
9. Показать явный reset:

```text
/profile reset active --yes
/profile reset all --yes
```

## Результаты

Результат сценария сохранён в [results/day-12-assistant-personalization.md](results/day-12-assistant-personalization.md).

Ключевой вывод: profile layer меняет prompt assembly и ожидаемое поведение без записи этих
предпочтений в long-term memory. `reset active --yes` очищает поля активного профиля, но оставляет
record и active name; `reset all --yes` очищает profiles, но сохраняет audit trail событий.

## Выводы

Персонализация должна быть управляемым слоем, а не скрытым побочным эффектом памяти. Явные команды,
отдельный JSON store, event log и token report делают профиль наблюдаемым и проверяемым. Это
подготавливает Day 13: task state должен развиваться отдельно от user profile и explicit memory.

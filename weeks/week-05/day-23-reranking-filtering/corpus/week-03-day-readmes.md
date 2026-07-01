# Public README документов Week 03

Стабильная копия public-safe README завершённых дней для corpus Day 21.

<!-- source: weeks/week-03/day-11-memory-layers/README.md -->

# Day 11 — Memory Layers

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1koR0oPdwlGUadGgw1RCSl9TGhwyBAXum)

## Исходное условие

🔥 День 11. Модель памяти ассистента

Опишите и реализуйте модель памяти для ассистента.

Разделите информацию минимум на 3 типа:

- краткосрочная: текущий диалог;
- рабочая: данные текущей задачи;
- долговременная: профиль, решения, знания.

Сделайте так, чтобы:

- разные типы памяти хранились отдельно;
- явно выбиралось, что и куда сохраняется.

Проверьте:

- какие данные попадают в каждый слой;
- как это влияет на ответы ассистента.

Результат:

Агент с явной моделью памяти: memory layers.

Формат:

Видео + Код / Текст.

## Цель задания

Сделать stateful-агента с явной моделью памяти: отделить текущий диалог от состояния текущей задачи и долговременных предпочтений, а затем показать, как эти слои физически хранятся и участвуют в сборке prompt.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-11-memory-layers.md)

## Реализация

В актуальный пакет `packages/ai_advent_agent/` добавлены memory layers:

- `short-term memory` — последние сообщения текущего диалога и явные `/memory add short`;
- `working memory` — key-value состояние текущей задачи;
- `long-term memory` — key-value профиль, устойчивые предпочтения, решения и знания;
- `memory events` — JSONL-журнал явных операций `add`, `set`, `forget`, `reset`.

С Day 11 CLI использует namespace-структуру slash-команд и интерактивное меню команд через
`prompt_toolkit`. При вводе `/` показываются верхнеуровневые группы, при вводе `/m` список
фильтруется до `/memory`. Выбор root-команды с вложенными командами вставляет пробел
(`/memory `, `/config `, `/status `), после чего меню переходит к вложенным suggestions.
Меню всегда отображается в двухколоночном виде: первая колонка — команда, вторая колонка —
краткое описание.
Команды с ограниченным набором аргументов подсказывают значения автоматически: например,
`/config strategy ` предлагает `direct` и `step_by_step`, `/config overflow ` предлагает
`error`, `no_trim`, `sliding_window`, а `/memory set ` предлагает `working` и `long`.
После выбора intermediate-команды с fixed argument completion CLI вставляет trailing space и сразу
открывает следующее меню: `/config strategy` → `/config strategy ` → `direct`/`step_by_step`,
`/memory set` → `/memory set ` → `working`/`long`.
Command subsystem оформлен как пакет `ai_advent_agent.commands`: registry, router, completer,
builders и feature-модули команд живут отдельно, а публичные импорты
`from ai_advent_agent.commands import ...` сохранены.

Основные команды памяти:

```text
/memory
/memory short
/memory working
/memory long
/memory summary
/memory facts
/memory add short <text>
/memory set working <key>: <value>
/memory set long <key>: <value>
/memory forget working <key>
/memory forget long <key>
/memory reset working
/memory reset all --yes
```

Старые команды `/remember`, `/forget`, `/facts`, `/summary` сохранены как legacy aliases, но новые
README и сценарии используют namespace-команды.
Legacy aliases доступны через `/help legacy`, работают при ручном вводе, но не показываются в
основном autocomplete menu.

Prompt assembly собирается в порядке:

1. system prompt;
2. long-term memory;
3. working memory;
4. short-term memory;
5. текущий user message.

Token reports дополнены metadata по memory layers: активные слои, количество записей, оценка токенов по слоям и порядок сборки prompt.

## Структура файлов

```text
.
├── README.md
├── codex-log.md
├── snapshot/
│   ├── .env.example
│   ├── pyproject.toml
│   ├── ai_advent_agent/
│   │   └── commands/
│   └── tests/
├── results/
│   └── day-11-memory-layers.md
└── artifacts/
    └── agent-context/
        ├── long_term_memory.json
        ├── memory_events.jsonl
        ├── prompt_all_memory_layers.json
        ├── prompt_no_memory.json
        ├── prompt_working_memory.json
        ├── short_term_memory.json
        ├── token_reports.jsonl
        └── working_memory.json
```

## Как запустить

Day-specific offline runner удалён из актуального package. Текущие memory layers проверяются
package tests; историческую демонстрацию запускайте из snapshot ниже.

Offline-сценарий из snapshot:

```bash
cd weeks/week-03/day-11-memory-layers/snapshot
uv run day11-scenarios memory-layers-demo
```

Интерактивный агент из snapshot:

```bash
cd weeks/week-03/day-11-memory-layers
mkdir -p artifacts/agent-context
cd snapshot

uv run day11-agent \
  --context-file ../artifacts/agent-context/messages.json \
  --short-term-memory-file ../artifacts/agent-context/short_term_memory.json \
  --working-memory-file ../artifacts/agent-context/working_memory.json \
  --long-term-memory-file ../artifacts/agent-context/long_term_memory.json \
  --memory-events-file ../artifacts/agent-context/memory_events.jsonl \
  --token-report-file ../artifacts/agent-context/token_reports.jsonl
```

Для online-сценария нужен `DEEPSEEK_API_KEY` в окружении или в `snapshot/.env`.
Если нужно отключить интерактивное меню команд, добавьте флаг `--plain-input`.

## Сценарий демонстрации для видео

### A. Подготовка

Открыть папку дня:

```bash
cd weeks/week-03/day-11-memory-layers
mkdir -p artifacts/agent-context
```

Перед записью можно оставить существующие demo-артефакты или очистить только runtime-файлы текущей демонстрации:

```bash
rm -f artifacts/agent-context/messages.json
rm -f artifacts/agent-context/short_term_memory.json
rm -f artifacts/agent-context/working_memory.json
rm -f artifacts/agent-context/long_term_memory.json
rm -f artifacts/agent-context/memory_events.jsonl
rm -f artifacts/agent-context/token_reports.jsonl
```

На экране должно быть видно, что работа идёт из папки Day 11, а runtime-файлы сохраняются в `artifacts/agent-context/`, не в `snapshot/`.

### B. Демонстрация offline-сценария

Запустить:

```bash
cd snapshot
uv run day11-scenarios memory-layers-demo
```

Показать в терминале таблицу:

- `no_memory` — общий ответ без персонализации и состояния;
- `working_only` — ответ учитывает текущую задачу;
- `all_layers` — ответ учитывает язык, стиль, задачу и последние уточнения.

Открыть файлы:

- `../artifacts/agent-context/short_term_memory.json`;
- `../artifacts/agent-context/working_memory.json`;
- `../artifacts/agent-context/long_term_memory.json`;
- `../artifacts/agent-context/memory_events.jsonl`;
- `../artifacts/agent-context/token_reports.jsonl`;
- `../artifacts/agent-context/prompt_all_memory_layers.json`.

Что объяснить:

- short-term memory содержит текущий диалог и short notes;
- working memory содержит текущую задачу и ограничения;
- long-term memory содержит устойчивый профиль и предпочтения;
- `memory_events.jsonl` показывает, что сохранение было явным;
- `token_reports.jsonl` показывает, какие слои попали в prompt и сколько токенов они добавили.

### C. Демонстрация интерактивного агента и меню команд

Запустить из `snapshot/`:

```bash
uv run day11-agent \
  --context-file ../artifacts/agent-context/messages.json \
  --short-term-memory-file ../artifacts/agent-context/short_term_memory.json \
  --working-memory-file ../artifacts/agent-context/working_memory.json \
  --long-term-memory-file ../artifacts/agent-context/long_term_memory.json \
  --memory-events-file ../artifacts/agent-context/memory_events.jsonl \
  --token-report-file ../artifacts/agent-context/token_reports.jsonl
```

Показать autocomplete menu:

1. Ввести `/` и показать список верхнеуровневых команд:
   `/help`, `/status`, `/config`, `/session`, `/storage`, `/memory`, `/branch`, `/file`, `/exit`.
   Меню отображается в две колонки: команда слева, краткое описание справа.
   В root menu не должны показываться legacy aliases вроде `/facts`, `/remember`, `/context`.
2. Ввести `/br`, выбрать `/branch`: в строку вставляется `/branch ` и сразу открывается
   двухколоночное меню вложенных команд:
   `/branch checkpoint`, `/branch create`, `/branch list`, `/branch switch`.
3. Ввести `/m` и показать, что список фильтруется до `/memory`.
4. Выбрать `/memory`: в строку вставляется `/memory ` и открываются вложенные команды:
   `/memory short`, `/memory working`, `/memory long`, `/memory summary`, `/memory facts`,
   `/memory add`, `/memory set`, `/memory forget`, `/memory reset`.
5. Выбрать `/memory set`: в строку вставляется `/memory set ` и сразу открывается argument menu:
   `working`, `long`.
6. Выбрать `/memory reset`: в строку вставляется `/memory reset ` и сразу открывается argument menu:
   `working`, `all --yes`.
7. Выбрать `/config`: в строку вставляется `/config `. Для показа конфигурации использовать
   `/config show` или `/status config`; `/config` является namespace-командой, а не deprecated alias.
8. Выбрать `/config strategy`: в строку вставляется `/config strategy ` и сразу открывается
   argument menu с `direct` и `step_by_step`.
9. Ввести `/config overflow ` и показать, что argument completion предлагает `error`, `no_trim`,
   `sliding_window`.
10. Ввести `/memory set ` и показать, что argument completion предлагает `working` и `long`.
    После выбора `working` строка становится `/memory set working `, дальше key-value вводится
    вручную.
11. Ввести `/memory reset ` и показать, что argument completion предлагает `working` и
    `all --yes`.

Отдельно показать fixed argument follow-up:

- `/config ` → выбрать `/config strategy` → увидеть `direct`, `step_by_step`;
- `/config ` → выбрать `/config overflow` → увидеть `error`, `no_trim`, `sliding_window`;
- `/memory ` → выбрать `/memory set` → увидеть `working`, `long`;
- `/memory ` → выбрать `/memory reset` → увидеть `working`, `all --yes`.

Ввести вручную:

```text
/memory
/memory set long language: русский
/memory set long style: кратко и технически
/memory set working task: реализовать memory layers для AI Advent агента
/memory set working constraint: хранить слои памяти отдельно
/memory add short Обсуждаем демонстрацию Day 11
/memory
/memory short
/memory working
/memory long
/memory summary
/memory facts
/status
/status context
/status tokens
/status report
```

Показать эффект:

- `/memory` до сохранения показывает пустые слои;
- `/memory set long` пишет только в long-term memory;
- `/memory set working` пишет только в working memory;
- `/memory add short` добавляет short-term note;
- после обычного вопроса token report показывает активные memory layers;
- `/status ...` показывает диагностику, контекстные файлы, token breakdown и последний report.

Показать legacy aliases:

```text
/help legacy
/facts
/remember working demo: legacy alias работает
```

Объяснить, что старые команды продолжают работать, но печатают короткое предупреждение и в новых
сценариях заменяются namespace-командами.

### D. Online-сценарий с моделью по API

Этот сценарий нужен для записи реального ответа модели. Перед запуском подготовить ключ:

```bash
export DEEPSEEK_API_KEY="..."
```

Или создать `snapshot/.env` на основе `snapshot/.env.example`.

Запустить тот же агент:

```bash
uv run day11-agent \
  --context-file ../artifacts/agent-context/messages.json \
  --short-term-memory-file ../artifacts/agent-context/short_term_memory.json \
  --working-memory-file ../artifacts/agent-context/working_memory.json \
  --long-term-memory-file ../artifacts/agent-context/long_term_memory.json \
  --memory-events-file ../artifacts/agent-context/memory_events.jsonl \
  --token-report-file ../artifacts/agent-context/token_reports.jsonl
```

Ввести команды:

```text
/memory reset all --yes
/memory set long language: русский
/memory set long style: кратко и технически
/memory set working task: реализовать memory layers для AI Advent агента
/memory set working constraint: хранить слои памяти отдельно
/memory add short Обсуждаем демонстрацию Day 11
/memory
Сформулируй план реализации ассистента с учётом моей памяти.
```

Что показать:

- реальный ответ online-модели;
- что ответ на русском и в кратком техническом стиле из long-term memory;
- что ответ учитывает текущую задачу и constraint из working memory;
- metadata после ответа, включая token report;
- обновлённые файлы `messages.json`, `short_term_memory.json`, `working_memory.json`, `long_term_memory.json`, `memory_events.jsonl`, `token_reports.jsonl`.

Если `DEEPSEEK_API_KEY` не задан, online-сценарий не выполнять и не подменять результат. Для проверки без ключа используется offline-сценарий.

### E. Что показать в конце

Открыть:

- `../artifacts/agent-context/short_term_memory.json`;
- `../artifacts/agent-context/working_memory.json`;
- `../artifacts/agent-context/long_term_memory.json`;
- `../artifacts/agent-context/memory_events.jsonl`;
- `../results/day-11-memory-layers.md`.

Финальный тезис: разные типы памяти физически разделены, сохраняются только явными командами и отдельно участвуют в prompt assembly.

## Результаты

- [Отчёт Day 11](results/day-11-memory-layers.md)
- [Демонстрационные artifacts](artifacts/agent-context/)

Краткий результат: агент получил явную модель памяти, где short-term, working и long-term данные хранятся отдельно, управляются командами и отражаются в token reports.

## Выводы

Day 11 переводит агент от простого persistent context к более управляемому stateful-поведению. Отдельные memory layers уменьшают риск memory pollution: временные детали задачи не попадают в long-term profile, а устойчивые предпочтения не смешиваются с текущим checklist.

<!-- source: weeks/week-03/day-12-assistant-personalization/README.md -->

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

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-12-assistant-personalization.md)

## Реализация

Статус: `✅ done`.

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
├── codex-log.md
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

Day-specific offline runner удалён из актуального package. Текущие profile APIs проверяются
package tests; историческую демонстрацию запускайте из `Snapshot Day 12` ниже.

#### Online/interactive агент

Day-specific online/interactive walkthrough запускайте из `Snapshot Day 12` ниже. Актуальный
`packages/ai_advent_agent` содержит интегрированный profile CLI/runtime, но не используется как
runner исторического сценария дня.

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

<!-- source: weeks/week-03/day-13-task-state-machine/README.md -->

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

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-13-task-state-machine.md)

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
├── codex-log.md
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

Day-specific offline runner удалён из актуального package. Текущий task state проверяется package
tests; историческую демонстрацию запускайте из `Snapshot Day 13` ниже.

#### Online/interactive агент

Day-specific online/interactive walkthrough запускайте из `Snapshot Day 13` ниже. Актуальный
`packages/ai_advent_agent` содержит интегрированный task CLI/runtime, но не используется как
runner исторического сценария дня.

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
2. Запустить offline-сценарий из `Snapshot Day 13` по команде раздела `Как запустить`.
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

<!-- source: weeks/week-03/day-14-state-invariants/README.md -->

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

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-14-state-invariants.md)

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
├── codex-log.md
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

<!-- source: weeks/week-03/day-15-controlled-state-transitions/README.md -->

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

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-15-controlled-state-transitions.md)

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
├── codex-log.md
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

Day-specific offline runner удалён из актуального package. Текущие controlled transitions
проверяются package tests; историческую демонстрацию запускайте из `Snapshot Day 15` ниже.

#### Online/interactive агент

Day-specific online/interactive walkthrough запускайте из `Snapshot Day 15` ниже. Актуальный
`packages/ai_advent_agent` содержит интегрированный controlled-state harness, но не используется
как runner исторического сценария дня.

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
2. Запустить offline-сценарий из `Snapshot Day 15` по команде раздела `Как запустить`.
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

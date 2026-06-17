# Day 11 — Memory Layers

## 🎥 Видео-отчёт

> Видео будет добавлено после записи демонстрации.

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

## Реализация

В актуальный пакет `packages/ai_advent_agent/` добавлены memory layers:

- `short-term memory` — последние сообщения текущего диалога и явные `/memory add short`;
- `working memory` — key-value состояние текущей задачи;
- `long-term memory` — key-value профиль, устойчивые предпочтения, решения и знания;
- `memory events` — JSONL-журнал явных операций `remember`, `forget`, `reset`.

С Day 11 CLI использует namespace-структуру slash-команд и интерактивное меню команд через
`prompt_toolkit`. При вводе `/` показываются верхнеуровневые группы, при вводе `/m` список
фильтруется до `/memory`. Выбор root-команды с вложенными командами вставляет пробел
(`/memory `, `/config `, `/status `), после чего меню переходит к вложенным suggestions.
Меню всегда отображается в двухколоночном виде: первая колонка — команда, вторая колонка —
краткое описание.
Command subsystem оформлен как пакет `ai_advent_agent.commands`: registry, router, completer,
builders и feature-модули команд живут отдельно, а публичные импорты
`from ai_advent_agent.commands import ...` сохранены.

Основные команды памяти:

```text
/memory
/memory short
/memory summary
/memory facts
/memory working
/memory long
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

Offline-сценарий из актуального пакета:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios memory-layers-demo
```

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
   `/memory short`, `/memory summary`, `/memory facts`, `/memory working`, `/memory long`,
   `/memory add short`, `/memory set working`, `/memory set long`, `/memory forget working`,
   `/memory forget long`, `/memory reset working`, `/memory reset all --yes`.
5. Выбрать `/config`: в строку вставляется `/config `. Для показа конфигурации использовать
   `/config show` или `/status config`; `/config` является namespace-командой, а не deprecated alias.

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

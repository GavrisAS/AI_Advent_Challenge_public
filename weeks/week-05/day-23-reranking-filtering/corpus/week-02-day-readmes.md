# Public README документов Week 02

Стабильная копия public-safe README завершённых дней для corpus Day 21.

<!-- source: weeks/week-02/day-06-first-agent/README.md -->

# Day 06 — First Agent
## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1Jn3QCrsbSmHGBChmHMrQYXQ6EYYAUVEA)

## Исходное условие

🔥 День 6. Первый агент

Реализуйте простого агента, который:

- принимает запрос пользователя;
- отправляет его в LLM через API;
- получает ответ;
- выводит результат в вашем интерфейсе.

Подходит простой чат, CLI или web, запросы через HTTP-клиент.

Важно:

- агент должен быть отдельной сущностью, а не просто один вызов API;
- логика запроса и ответа должна быть инкапсулирована в агенте.

Результат: агент принимает запрос и корректно вызывает LLM через API.

Формат: видео + код.

Видео к заданию: https://disk.yandex.ru/i/Yr-07wUn3xmVhg

## Цель задания

Перейти от одиночного API-вызова к отдельной сущности агента с состоянием, конфигурацией и CLI-интерфейсом.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-06-first-agent.md)

## Реализация

В `snapshot/` находится минимальный stateful LLM-агент. Он принимает запросы пользователя, хранит историю текущей сессии, поддерживает стратегии `direct` и `step_by_step`, вызывает DeepSeek-compatible API и возвращает ответ вместе с metadata: `finish_reason`, `usage`, токены и время ответа.

Основные компоненты:

- `ai_advent_agent/config.py` — настройки агента;
- `ai_advent_agent/env.py` — загрузка `.env`;
- `ai_advent_agent/llm_client.py` — HTTP-клиент LLM API;
- `ai_advent_agent/agent.py` — сущность `SimpleAgent`;
- `ai_advent_agent/cli.py` — тонкий CLI-интерфейс.

## Структура файлов

```text
.
├── README.md
├── codex-log.md
├── snapshot/
│   ├── .env.example
│   ├── pyproject.toml
│   └── ai_advent_agent/
├── results/
└── artifacts/
```

## Как запустить

```bash
cd weeks/week-02/day-06-first-agent/snapshot
cp .env.example .env
# Добавьте DEEPSEEK_API_KEY в .env
uv run day6-agent
```

Альтернативный запуск:

```bash
python -m ai_advent_agent.cli
```

## Результаты

Результат задания представлен самодостаточным snapshot и видео-отчётом. Отдельные файлы результатов для дня 6 не создавались.

## Выводы

Даже простой агент выигрывает от разделения ответственности: CLI не должен знать детали HTTP-запроса, а агент должен инкапсулировать состояние, стратегию и обработку ответа.

<!-- source: weeks/week-02/day-07-save-context/README.md -->

# Day 07 — Save Context
## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1C-TPDf6MpkajEt8Xnb8Aq3riJsAisKI1)

## Исходное условие

🔥 День 7. Сохранение контекста

Добавьте агенту сохранение контекста:

- храните историю диалога `messages` в JSON или SQLite;
- при перезапуске агента загружайте историю обратно;
- продолжайте диалог так, как будто агент не выключался.

Проверьте на практике:

- начните диалог;
- перезапустите приложение;
- продолжите диалог и убедитесь, что агент помнит прошлые сообщения.

Результат: агент, который сохраняет и восстанавливает контекст между запусками.

Формат: видео + код.

## Цель задания

Сделать контекст агента долговременным состоянием и проверить восстановление истории после перезапуска.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-07-save-context.md)

## Реализация

День 7 построен на решении дня 6 и добавляет persistent context через `JsonContextStore`. Агент сохраняет `messages` в JSON после успешного ответа LLM, загружает историю при старте и продолжает диалог с тем же контекстом.

Добавлено:

- `ai_advent_agent/storage.py` — сохранение, загрузка, очистка и валидация JSON-контекста;
- CLI-аргументы `--context-file`, `--no-load-context`, `--no-persist`;
- команды `/context`, `/history full`, `/clear-context`;
- исторический контекст перенесён в `artifacts/agent-context/`.

## Структура файлов

```text
.
├── README.md
├── codex-log.md
├── snapshot/
│   ├── .env.example
│   ├── pyproject.toml
│   └── ai_advent_agent/
├── results/
└── artifacts/
    └── agent-context/
```

## Как запустить

```bash
cd weeks/week-02/day-07-save-context/snapshot
cp .env.example .env
# Добавьте DEEPSEEK_API_KEY в .env
uv run day7-agent
```

Альтернативный запуск:

```bash
python -m ai_advent_agent.cli
```

По умолчанию новый runtime-контекст создаётся в `snapshot/.agent_context/messages.json`. Исторический контекст сдачи сохранён отдельно в `artifacts/agent-context/messages.json`.

## Результаты

- [Исторический JSON-контекст](artifacts/agent-context/messages.json)

## Выводы

Сохранение `messages` превращает агент из одноразового CLI в приложение с памятью между запусками. При этом важно отделять runtime-файлы от сдаваемых артефактов и не публиковать реальные секреты.

<!-- source: weeks/week-02/day-08-tokens-accounting/README.md -->

# Day 08 — Tokens Accounting
## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1hWcVBHbaG2po9z2ksCkGmIG2od9GxanL)

## Исходное условие

🔥 День 8. Работа с токенами

Добавьте в код агента подсчёт токенов:

- для текущего запроса;
- для всей истории диалога;
- для ответа модели.

Сравните:

- короткий диалог;
- длинный диалог;
- диалог, который превышает лимит модели.

Покажите:

- как растёт стоимость/токены по мере диалога;
- что ломается при переполнении.

Речь про лимит контекстного окна. Задание направлено на понимание того, как меняется поведение модели, когда старая часть контекста начинает постепенно уходить из доступного окна.

Результат: код, который считает токены и показывает, как они влияют на поведение агента.

Формат: видео + код.

## Цель задания

Сделать контекст агента наблюдаемым: считать токены текущего запроса, истории и ответа, оценивать стоимость и проверять поведение при переполнении контекстного окна.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-08-tokens-accounting.md)

## Реализация

День 8 расширяет агента дня 7. В `snapshot/` добавлены:

- `token_counter.py` — оценочный локальный подсчёт токенов;
- `token_report.py` — структура отчёта и JSONL-лог;
- `scenarios.py` — offline-сценарии роста контекста без API-вызовов;
- политики переполнения `error`, `no_trim`, `sliding_window`;
- CLI-команды `/tokens`, `/last-report`, `/analyze-file`, `/ask-file`, `/context-mode`.

Точный токенизатор зависит от модели и провайдера, поэтому локальный счётчик используется как оценка. Фактические `prompt_tokens`, `completion_tokens`, `total_tokens` берутся из `usage`, если API их возвращает.

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
└── artifacts/
    ├── agent-context/
    └── skills-all.md
```

## Как запустить

```bash
cd weeks/week-02/day-08-tokens-accounting/snapshot
cp .env.example .env
# Добавьте DEEPSEEK_API_KEY в .env
uv run day8-agent
```

Offline-сценарии без API:

```bash
uv run day8-scenarios long --turns 50
uv run day8-scenarios overflow-file ../artifacts/skills-all.md
```

Тесты snapshot:

```bash
python -m unittest discover -s tests -v
```

## Результаты

- [Исторический JSON-контекст](artifacts/agent-context/messages.json)
- [Исторические token reports](artifacts/agent-context/token_reports.jsonl)
- [Большой файл для проверки переполнения](artifacts/skills-all.md)

## Выводы

Подсчёт токенов делает рост контекста видимым и управляемым. Для агента нужен preflight-расчёт, честная работа с `usage` провайдера и явная политика на случай переполнения окна.

<!-- source: weeks/week-02/day-09-context-management-summary/README.md -->

# Day 09 — Context Management Summary
## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1u4YAYo67XGNN2ngqpsGipbtcBWsB3W7Q)

## Исходное условие

🔥 День 9. Управление контекстом: сжатие истории

Реализуйте механизм управления контекстом:

- храните последние N сообщений “как есть”;
- остальное заменяйте summary, например каждые 10 сообщений;
- храните summary отдельно и подставляйте его в запрос вместо полной истории.

Сравните:

- качество ответов без сжатия;
- качество ответов со сжатием;
- расход токенов до/после.

Результат: агент, который работает с компрессией истории и экономит токены.

Формат: видео + код.

## Цель задания

Добавить к агенту summary memory: старые сообщения сжимаются отдельным LLM-вызовом, summary хранится отдельно, а основной запрос получает summary вместо полной старой истории.

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-09-context-management-summary.md)

## Реализация

День 9 расширяет агента дня 8 без изменения поведения по умолчанию:

- `summary_mode="off"` оставляет прежний persistent context и token reports;
- `summary_mode="llm"` включает отдельный LLM-вызов для сжатия старых сообщений;
- последние `recent_messages_limit` сообщений остаются в истории без изменений;
- summary хранится в `.agent_context/summary.json`;
- основной chat prompt строится как `system prompt → synthetic system summary → recent messages → current user message`;
- `/reset` и `/clear-context` очищают summary вместе с обычным контекстом;
- token report содержит summary metadata: активность summary, оценку токенов summary и число сжатых сообщений.

CLI дополнен аргументами:

- `--summary-mode off|llm`;
- `--summary-file`;
- `--recent-messages-limit`;
- `--summarize-every-messages`;
- `--summary-max-tokens`.

Интерактивные команды:

- `/summary`;
- `/summary clear`;
- `/summary-mode off|llm`;
- `/context`;
- `/config`;
- `/tokens`;
- `/last-report`.

## Структура файлов

```text
.
├── README.md
├── codex-log.md
├── snapshot/
│   ├── pyproject.toml
│   ├── ai_advent_agent/
│   └── tests/
├── results/
│   └── day-09-summary-comparison.md
└── artifacts/
    └── agent-context/
        ├── messages.json
        ├── summary.json
        └── token_reports.jsonl
```

## Как запустить

```bash
cd weeks/week-02/day-09-context-management-summary/snapshot
uv run day9-agent --summary-mode llm
```

Для реального API-запуска нужен `DEEPSEEK_API_KEY` в окружении или `.env`.

Offline-сравнение без API:

```bash
uv run day9-scenarios summary-comparison
```

Тесты snapshot:

```bash
python -m unittest discover -s tests -v
```

## Сценарий демонстрации для видео

Запускайте агент из `snapshot/`, но сохраняйте runtime-артефакты в папку дня:

```bash
cd weeks/week-02/day-09-context-management-summary
rm -rf snapshot/.venv
mkdir -p artifacts/agent-context

cd snapshot

uv run day9-agent \
  --summary-mode llm \
  --context-file ../artifacts/agent-context/messages.json \
  --summary-file ../artifacts/agent-context/summary.json \
  --token-report-file ../artifacts/agent-context/token_reports.jsonl
```

Что показать в видео:

- `/config`;
- `/context`;
- несколько сообщений в диалоге;
- `/tokens`;
- `/summary`;
- файлы `artifacts/agent-context/messages.json`, `artifacts/agent-context/summary.json`, `artifacts/agent-context/token_reports.jsonl`.

## Результаты

- [Сравнение prompt tokens до/после summary](results/day-09-summary-comparison.md)
- [Демонстрационный messages.json](artifacts/agent-context/messages.json)
- [Демонстрационный summary.json](artifacts/agent-context/summary.json)
- [Демонстрационный token_reports.jsonl](artifacts/agent-context/token_reports.jsonl)

Offline-сценарий показал снижение оценочного prompt с 3 569 до 614 токенов: 42 старых сообщения заменены summary, при этом ранний важный факт сохранён в compressed context.

## Выводы

Summary memory экономит контекстное окно, но переносит часть ответственности на качество сжатия. Поэтому summary нужно хранить отдельно, явно маркировать в prompt, тестировать на ранних важных фактах и отражать в token reports.

<!-- source: weeks/week-02/day-10-context-management-strategies/README.md -->

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

## Дополнительные учебные заметки

- [Заметки по теме задания](../../../notes/task_notes/day-10-context-management-strategies.md)

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
├── codex-log.md
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

Day-specific runner удалён из актуального package. Для воспроизведения сравнения используйте
`Snapshot Day 10` ниже. Актуальный `packages/ai_advent_agent` остаётся интегрированным harness,
а не runner-ом исторических day-specific сценариев; его общий CLI описан в
`packages/docs/cli.md`.

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
cd weeks/week-02/day-10-context-management-strategies/snapshot
mkdir -p ../artifacts/agent-context

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

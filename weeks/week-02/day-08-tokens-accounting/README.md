# Day 08 — Tokens Accounting

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
├── artifacts/
│   ├── agent-context/
│   └── skills-all.md
└── video/
    └── day-08-tokens-accounting-demo.webm
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

## Видео-отчёт

- [Видео выполнения задания](video/day-08-tokens-accounting-demo.webm)

## Выводы

Подсчёт токенов делает рост контекста видимым и управляемым. Для агента нужен preflight-расчёт, честная работа с `usage` провайдера и явная политика на случай переполнения окна.

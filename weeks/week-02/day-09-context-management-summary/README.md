# Day 09 — Context Management Summary

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
├── snapshot/
│   ├── pyproject.toml
│   ├── ai_advent_agent/
│   └── tests/
├── results/
│   └── day-09-summary-comparison.md
├── artifacts/
│   └── agent-context/
│       ├── messages.json
│       ├── summary.json
│       └── token_reports.jsonl
└── video/
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

## Видео-отчёт

- [Видео выполнения задания](video/day-09-context-management-summary-demo.webm)

## Выводы

Summary memory экономит контекстное окно, но переносит часть ответственности на качество сжатия. Поэтому summary нужно хранить отдельно, явно маркировать в prompt, тестировать на ранних важных фактах и отражать в token reports.

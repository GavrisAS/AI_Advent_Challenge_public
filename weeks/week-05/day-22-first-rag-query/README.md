# Day 22 — Первый RAG-запрос

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1QS7HVOxSjINqOaZB-Dvd24DWRrN4ZF0x)

## Исходное условие

🔥 День 22. Первый RAG-запрос

Реализуйте функцию:

👉 вопрос → поиск релевантных чанков → объединение с вопросом → запрос к LLM

Сравните:

👉 ответ модели без RAG
👉 ответ модели с RAG

Усиление:

👉 составьте мини-набор из 10 контрольных вопросов по вашей базе
👉 для каждого вопроса зафиксируйте:

- ожидание (что должно быть в ответе)
- какие источники должны быть использованы (если применимо)

Результат:

Агент с двумя режимами (с RAG / без RAG) + 10 контрольных вопросов и сравнение качества

Формат:

Видео + Код

## Цель задания

Собрать полный QA-конвейер `question → embedding → retrieval → context prompt → LLM → answer`
и сравнить его с baseline той же LLM без проектного контекста.

## Реализация

Общий код в `ai_advent_agent.rag` разделён на ingestion/index, plain top-k retrieval, prompt
assembly, LLM adapters, QA orchestration, контрольный набор и отчёты. `answer_question()`
поддерживает `baseline`, `rag` и `both`. Baseline и RAG используют один объект LLM; RAG prompt
запрещает дополнять контекст внешними фактами и требует `source`, `section`, `chunk_id`.

Snapshot содержит собственную копию кода и corpus. Он не читает Python-код, corpus, index или
artifacts Day 21. В `eval/control-questions.json` находятся ровно 10 вопросов с ожидаемыми
пунктами и источниками. Оценка качества — прозрачное keyword matching, не LLM-as-judge.

Corpus дополнен зафиксированной public-safe копией контекста Day 21 в
`corpus/day-21-document-indexing-readme.md`. Это локальный source для q05–q08, а не runtime-ссылка
на предыдущий день.

Финальные artifacts построены реальным запуском: Ollama `nomic-embed-text` и DeepSeek
`deepseek-v4-flash`. Hash/fake остаются только deterministic smoke backends.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios first-rag-query-demo` | Snapshot-local сравнение baseline/RAG на 10 вопросах. |

В актуальный package entry point `ai-advent-scenarios` не добавлялся.

## Структура файлов

```text
day-22-first-rag-query/
├── README.md
├── corpus/                 # собственная public-safe копия, 10 content files
├── eval/control-questions.json
├── artifacts/              # index и comparison reports
└── snapshot/               # самодостаточный runner, lock и tests
```

## Как подготовлен corpus

Corpus содержит стабильные public-safe копии корневого/package README, package docs, README
Week 01–04 и локальную копию ключевого indexing-контекста Day 21: 21 994 слова. Последний source
объясняет metadata, chunking, backends и artifacts для q05–q08, не обращаясь к каталогу Day 21.
cache и временные файлы.

## Как запустить

### Актуальный пакет

Общие RAG QA helpers интегрированы в `packages/ai_advent_agent`; актуальный package не является
per-day runner. Его CLI-контракт описан в [`packages/docs/cli.md`](../../../packages/docs/cli.md).

### Snapshot Day 22

#### Offline/fake smoke

API key, сеть и Ollama не нужны. Hash embeddings нужны только для tests/fallback и не являются
качественной semantic model.

```bash
cd weeks/week-05/day-22-first-rag-query/snapshot

uv run ai-advent-scenarios first-rag-query-demo \
  --corpus-dir ../corpus \
  --questions-json ../eval/control-questions.json \
  --embedding-backend hash \
  --hash-dim 64 \
  --llm-provider fake \
  --output-dir .tmp/day22-fake-demo \
  --rebuild-index
```

#### Основной real demo для видео

Нужны запущенный Ollama с `nomic-embed-text`, сеть и `DEEPSEEK_API_KEY` в окружении. Ключ не
передаётся аргументом и не выводится.

```bash
cd weeks/week-05/day-22-first-rag-query/snapshot

uv run ai-advent-scenarios first-rag-query-demo \
  --corpus-dir ../corpus \
  --questions-json ../eval/control-questions.json \
  --embedding-backend ollama \
  --embedding-model nomic-embed-text \
  --llm-provider deepseek \
  --model deepseek-v4-flash \
  --output-dir ../artifacts \
  --rebuild-index
```

## Какие artifacts смотреть в видео

- `rag-comparison.md` — сводная таблица и 10 подробных сравнений;
- `rag-comparison.json` — полный machine-readable evidence;
- `sample-rag-answer.json` — один компактный показательный ответ;
- `structure-index.json` / `.sqlite3` — один и тот же локальный index;
- `index-manifest.json` — настройки и точный список artifacts без дублей.

## Сценарий демонстрации для видео

1. Открыть `eval/control-questions.json` и показать ожидания для 10 вопросов.
2. Показать, что `corpus/` находится внутри Day 22, а snapshot не ссылается на Day 21.
3. Из `snapshot/` запустить `uv run pytest -q`.
4. Показать основной real command Ollama + DeepSeek и сохранённые настройки manifest.
5. Открыть `rag-comparison.md`: сопоставить baseline/RAG для `q01` и показать сводку 10 вопросов.
6. Для q05–q08 показать retrieved chunks из `day-21-document-indexing-readme.md`.
7. При необходимости выполнить offline-команду в `.tmp/day22-fake-demo` как smoke.
8. Объяснить, что hash/fake проверяют механику, а semantic выводы относятся к real artifacts.
9. Удалить временный `.tmp/day22-fake-demo`; committed real artifacts не очищать.

## Чем baseline отличается от RAG

Baseline получает только вопрос и инструкцию не выдумывать внутренние правила. RAG сначала
векторизует вопрос той же embedding-моделью, выполняет cosine top-k search, передаёт chunks с
metadata в grounded prompt и требует перечислить источники. Генеративная модель в паре одинакова;
меняется только доступный контекст.

## Результаты

Реализованы три режима ответа, 10 контрольных вопросов, JSON/SQLite index и два формата отчёта.
Финальный real run использовал Ollama `nomic-embed-text` (dimension 768) и DeepSeek
`deepseek-v4-flash`: 11 corpus-документов дали 336 structure-aware chunks. Expected source найден
для 8 из 10 вопросов; q05–q08 все используют локальный `day-21-document-indexing-readme.md`.
Offline tests и полный hash/fake smoke также проходят без сети.

## Ограничения Day 22 и продолжение в Day 23

Retrieval использует plain top-k без query rewrite, threshold и reranker. Keyword coverage не
понимает смысл и может недооценить перефразированный ответ. Day 23 вставит между retrieval и prompt
явные `top_k_before_filter`, `similarity_threshold`, reranker/filter и `top_k_after_filter`.

## Выводы

RAG делает внутренние проектные ответы проверяемыми: модель получает локальные факты и provenance,
а baseline остаётся честным контролем. Качество всей системы по-прежнему ограничено retrieval;
наличие LLM не компенсирует нерелевантный context.

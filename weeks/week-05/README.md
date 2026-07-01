# Week 05 — RAG

## Статус

🚧 in_progress

## Ключевая тема недели

Пятая неделя посвящена Retrieval-Augmented Generation: поиску по внутренней базе знаний,
embedding-моделям, chunking, vector similarity, reranking и grounded answers с источниками.
Основной фокус — научиться подключать к агенту не только tools и внешние сервисы, но и собственный
corpus знаний.

## Цели недели

- Научиться работать с embedding-моделями.
- Реализовать подготовку документов для RAG: чтение, chunking, overlap и metadata.
- Реализовать поиск по базе знаний через vector similarity.
- Подключить найденные chunks к ответу агента.
- Научиться показывать источники и снижать риск галлюцинаций.
- Разобраться с reranking и метриками качества retrieval.

## Что важно проверить на практике

- Локальный embedding backend через Ollama и `nomic-embed-text`.
- Стабильную нарезку документов на chunks.
- Влияние `chunk_size` и `overlap` на качество поиска.
- Сохранение vectors вместе с metadata источника.
- Поиск top-k chunks по query пользователя.
- Подмешивание найденного контекста в prompt агента.
- Reranking как второй этап отбора кандидатов.
- Метрики context relevance, faithfulness и answer correctness.

## Связь с предыдущими неделями

Week 01 дала базовые LLM API и prompting. Week 02 добавила tools, persistence, token accounting и
context strategies. Week 03 собрала memory layers, user profile, task state и invariants. Week 04
разобрала MCP как стандарт подключения внешних tools и сервисов. Week 05 переносит фокус на
подключение внутренних знаний: как подготовить corpus, искать по нему и получать проверяемые
ответы с источниками.

## План дней

| День | Тема | Статус | Папка |
|---|---|---|---|
| day-21 | Индексация документов | ✅ done | [day-21-document-indexing](day-21-document-indexing/) |
| day-22 | Первый RAG-запрос | ✅ done | [day-22-first-rag-query](day-22-first-rag-query/) |
| day-23 | Реранкинг и фильтрация | ✅ done | [day-23-reranking-filtering](day-23-reranking-filtering/) |

## Ключевые навыки недели

- Различать генеративные и embedding-модели.
- Превращать текст в vectors и сравнивать их через similarity.
- Проектировать chunking и overlap под конкретный корпус.
- Хранить vectors, chunks и metadata как воспроизводимый knowledge index.
- Подключать retrieval output к prompt assembly.
- Оценивать качество RAG через измеримые метрики.
- Понимать ограничения RAG и выбирать между RAG, MCP, tools, prompt engineering и fine-tuning.

## Итоги недели

Day 21 подготовил индекс. Day 22 добавил полный baseline/RAG QA pipeline, 10 контрольных вопросов,
grounded prompts, источники и comparison reports. Day 23 добавил query rewrite, threshold,
heuristic reranking и сравнение plain/improved RAG. Day 24–25 остаются запланированными.

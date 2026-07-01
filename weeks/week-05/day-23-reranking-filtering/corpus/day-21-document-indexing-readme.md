# Day 21 — Индексация документов: зафиксированный контекст для Day 22

Этот public-safe документ — локальная копия ключевого контекста Day 21, зафиксированная внутри
corpus Day 22. Snapshot Day 22 индексирует этот файл как обычный локальный source и не читает
corpus, artifacts, runtime-файлы или Python-код из каталога Day 21.

## Pipeline индексации

Индексирующий pipeline читает документы, разбивает их на chunks, строит embedding каждого chunk и
сохраняет локальный индекс в JSON и SQLite. JSON удобен для просмотра manifest, текста, vectors и
metadata; SQLite хранит те же записи в структурированной локальной базе без отдельного server
process.

Day 21 сравнивает две стратегии chunking:

1. **Fixed-size chunking** использует окно до 1600 символов и overlap 200 символов. Граница по
   возможности переносится на конец строки. Стратегия проста и даёт сравнительно равномерные
   chunks, но может разрезать смысловой раздел или объединить соседние темы.
2. **Structure-aware chunking** учитывает Markdown headings, top-level Python `class` / `def` и
   границы paragraphs. Для Markdown сохраняется полный section path; слишком крупные sections
   дополнительно режутся до 2400 символов с overlap 200. Эта стратегия лучше сохраняет смысловые
   границы документации и более информативную section metadata.

## Metadata каждого chunk

Каждая индексная запись хранит:

- `source` — относительный путь исходного документа;
- `title` и `section` — заголовок документа и структурный путь раздела;
- стабильный `chunk_id` и порядковый `chunk_index`;
- `strategy` — `fixed` или `structure`;
- `source_sha256` — hash исходного документа;
- `start_line` и `end_line` — line range фрагмента;
- `char_count` и `word_count`;
- текст chunk и embedding vector.

Эти metadata нужны для воспроизводимости retrieval, проверки источников и построения grounded
ответа с `source`, `section` и `chunk_id`.

## Embedding backends

Основной semantic backend для учебного demo — локальный Ollama с моделью
`nomic-embed-text`. Одна и та же embedding model используется при индексации corpus и embedding
query; найденные vectors ранжируются по cosine similarity. Ollama не требует API key, но требует
запущенный локальный server и установленную модель.

Backend `hash` — deterministic normalized feature hashing. Он нужен для unit tests, CI и offline
smoke, потому что не требует Ollama, сети или секретов и даёт воспроизводимые vectors. Hash backend
не является качественной semantic embedding model: он в основном отражает пересечение токенов и
не должен использоваться как финальная оценка semantic retrieval.

## Artifacts индексирующего pipeline

Day 21 создавал следующие типы artifacts:

- `fixed-index.json` и `fixed-index.sqlite3` — fixed-size index в двух форматах;
- `structure-index.json` и `structure-index.sqlite3` — structure-aware index в двух форматах;
- `chunking-comparison.md` — настройки и сравнение стратегий;
- `sample-search-results.json` — sample top-k retrieval без генеративной LLM;
- `index-manifest.json` — corpus statistics, index settings и точный список artifacts.

Day 22 использует только собственный structure-aware index в своей папке `artifacts/`; этот
документ описывает происхождение indexing foundation, но не создаёт runtime-зависимость от Day 21.

## Граница между Day 21 и Day 22

Day 21 заканчивается на indexing и retrieval sanity checks: генеративная LLM не отвечает на
вопросы. Day 22 добавляет query embedding, plain top-k retrieval, сборку grounded prompt, вызов
реальной LLM, источники и сравнение с baseline. Исторический runner каждого дня находится только
в snapshot соответствующего дня.

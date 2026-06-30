# Day 21 — Индексация документов

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=1wajNtKJMpCCxugVnB7daeTTU2NYxHTSj)

## Исходное условие

🔥 День 21. Индексация документов

Возьмите набор документов:

👉 README / статьи / код / pdf → текст
👉 минимум 20–30 страниц текста суммарно (или эквивалент в коде)

Реализуйте пайплайн индексации:

👉 разбиение на чанки (chunking)
👉 генерация эмбеддингов
👉 сохранение индекса (FAISS / SQLite / JSON)

Усиление:

👉 добавьте метаданные к каждому чанку (source, title/file, section, chunk_id)
👉 сделайте минимум 2 стратегии chunking и сравните их:

- по фиксированному размеру
- по структуре (заголовки/разделы/файлы)

Результат:

Локальный индекс документов с эмбеддингами + метаданные + сравнение 2 стратегий chunking

Формат:

Видео + Код

## Цель задания

Построить первый базовый слой RAG без генеративных ответов: загрузить воспроизводимый corpus,
разбить документы двумя способами, получить embeddings, сохранить локальные JSON/SQLite индексы
и проверить их через cosine similarity retrieval.

## Реализация

Статус: `✅ done`.

Актуальный package получил переиспользуемый subpackage `ai_advent_agent.rag`:

- loader для UTF-8 `.md`, `.txt`, `.py` с SHA-256 и статистикой;
- fixed-size chunking с overlap и line ranges;
- structure-aware chunking по Markdown headings, Python `class`/`def` и paragraphs;
- Ollama backend через `/api/embed` с fallback на legacy `/api/embeddings`;
- deterministic normalized feature-hash backend только для tests/offline checks;
- JSON и SQLite stores;
- cosine similarity search и построение comparison artifacts.

Day-specific runner существует только в `snapshot/`. Он не добавляет `ai-advent-scenarios` в
актуальный package.

Corpus содержит 10 Markdown-документов, 21 578 слов и 184 292 Unicode-символа. Это примерно 43
страницы при грубой оценке 500 слов на страницу. Источники — только уже публикуемые README и
package docs. Приватные lecture materials, task notes, memory-bank, codex logs, secrets и runtime
outputs не используются.

### Стратегии chunking

1. `fixed`: окно 1600 символов, overlap 200, перенос границы на конец строки при возможности.
2. `structure`: Markdown section path по headings `#`–`######`; oversized sections дробятся до
   2400 символов с overlap 200, а sections только из heading и пустых строк не индексируются.
   Для Python используются top-level `class`/`def`, для plain text — paragraphs.

Каждый chunk хранит `source`, `title`, `section`, стабильный `chunk_id`, `strategy`, source hash,
line range, char/word counts и индекс внутри документа.

### Embedding backends

- `ollama` + `nomic-embed-text` — основной demo, API key не нужен; требуется работающий локальный
  Ollama и установленная модель.
- `hash` — deterministic fallback размерности 128 по умолчанию. Это тестовый feature hashing, а
  не качественная semantic embedding model.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios document-indexing-demo` | Snapshot-local historical runner индексации Day 21 |
| `--embedding-backend {ollama,hash}` | Выбрать real или deterministic fallback backend |
| `--embedding-model MODEL` | Указать Ollama embedding model |
| `--ollama-base-url URL` | Указать локальный Ollama API URL |
| `--fixed-chunk-size`, `--fixed-overlap` | Настроить fixed-size strategy |
| `--structure-max-chunk-size`, `--structure-overlap` | Настроить structure-aware strategy |
| `--top-k`, `--sample-query` | Настроить retrieval sanity checks |
| `--hash-dim` | Задать dimension hash fallback |

Новых slash-команд интерактивного агента нет.

## Структура файлов

```text
weeks/week-05/day-21-document-indexing/
├── README.md
├── build_corpus.py
├── corpus/
│   ├── README.md
│   ├── docs-*.md
│   ├── package-readme.md
│   ├── project-readme.md
│   └── week-01..04-day-readmes.md
├── artifacts/
│   ├── fixed-index.json
│   ├── fixed-index.sqlite3
│   ├── structure-index.json
│   ├── structure-index.sqlite3
│   ├── chunking-comparison.md
│   ├── index-manifest.json
│   └── sample-search-results.json
└── snapshot/
    ├── pyproject.toml
    ├── uv.lock
    ├── src/ai_advent_agent/
    │   ├── scenarios.py
    │   └── rag/
    └── tests/test_document_indexing.py
```

## Как запустить

### Snapshot Day 21

#### Основной demo с Ollama

API key и `.env` не нужны. До первого запуска установите модель:

```bash
ollama pull nomic-embed-text
```

Затем запустите historical scenario только из snapshot:

```bash
cd weeks/week-05/day-21-document-indexing/snapshot
uv sync --locked --all-groups
uv run ai-advent-scenarios document-indexing-demo \
  --corpus-dir ../corpus \
  --embedding-backend ollama \
  --embedding-model nomic-embed-text \
  --output-dir ../artifacts
```

#### Offline/test fallback

Не требует Ollama, сети, API key или секретов:

```bash
cd weeks/week-05/day-21-document-indexing/snapshot
uv run ai-advent-scenarios document-indexing-demo \
  --corpus-dir ../corpus \
  --embedding-backend hash \
  --output-dir .tmp/day21-hash-demo
```

`.tmp/day21-hash-demo` — только локальный временный output: он игнорируется git, исключается из
public export и не является частью snapshot. Для review/CI output можно направить в `/tmp`.

#### Проверки snapshot

```bash
cd weeks/week-05/day-21-document-indexing/snapshot
uv run pytest -q
uv run ruff check .
uv run ty check src
```

Реализация также тестируется общим `make check`; day-specific запуск из актуального package не
поддерживается.

## Сценарий демонстрации для видео

1. Открыть `corpus/README.md`: показать public-safe состав, 21 578 слов и оценку объёма.
2. Открыть `snapshot/src/ai_advent_agent/rag/documents.py`: показать loader и metadata документа.
3. Открыть `snapshot/src/ai_advent_agent/rag/chunking.py`: показать fixed-size и
   structure-aware стратегии.
4. Открыть `snapshot/src/ai_advent_agent/rag/embeddings.py`: показать Ollama backend и hash
   fallback, подчеркнуть отсутствие API keys.
5. Из `snapshot/` запустить основной Ollama command из раздела выше.
6. Открыть `artifacts/fixed-index.json`: показать manifest, text, metadata и dimension 768.
7. Открыть `artifacts/structure-index.json`: показать section path и стабильный `chunk_id`.
8. Открыть `artifacts/chunking-comparison.md`: показать настройки и таблицу 144 vs 330 chunks.
9. Открыть `artifacts/sample-search-results.json`: показать top-k двух стратегий без LLM.
10. Выполнить `uv run pytest -q` и показать smoke test hash backend.
11. Сделать вывод: fixed-size проще и равномернее; structure-aware сохраняет смысловые границы и
    более информативные metadata.
12. При необходимости удалить только временный `.tmp/day21-hash-demo`; основные `artifacts/`
    сохраняются как результат дня.

## Результаты

Основные artifacts получены через локальный Ollama `nomic-embed-text`:

- 10 документов, 21 578 слов;
- 144 fixed chunks и 330 structure-aware chunks без heading-only fragments;
- embedding dimension 768;
- JSON и SQLite индекс для каждой стратегии;
- пять sample queries с top-3 retrieval results;
- сравнительный отчёт: [chunking-comparison.md](artifacts/chunking-comparison.md).

Structure-aware индекс крупнее из-за тематических sections, но heading-only fragments после ревью
не сохраняются. Для данного corpus он даёт более точные section metadata; fixed-size остаётся
полезным baseline с более равномерными chunks и меньшим индексом.

## Выводы

Индексация отделена от генерации: Day 21 создаёт проверяемый knowledge index, но не отвечает на
вопросы через LLM. Воспроизводимость обеспечивают curated corpus, stable chunk IDs, source hashes,
явные settings в manifest и два формата хранения. Ollama даёт реальные semantic embeddings для
демо, а hash backend делает tests и CI независимыми от локального model server.

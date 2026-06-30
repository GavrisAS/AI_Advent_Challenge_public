# Сравнение стратегий chunking — Day 21

## Corpus

Проиндексировано 10 public-safe документов: 21,578 слов, 184,292 символов.

## Настройки

- Fixed-size: `{'chunk_size': 1600, 'overlap': 200}`.
- Structure-aware: `{'max_chunk_size': 2400, 'overlap': 200}`.
- Embeddings: `ollama` / `nomic-embed-text`, dimension `768`.

## Сравнение

| Метрика | Fixed-size | Structure-aware |
|---|---:|---:|
| Документы | 10 | 10 |
| Chunks | 144 | 330 |
| Символы min / avg / max | 336 / 1502.3 / 1599 | 59 / 556.0 / 2395 |
| Слова min / avg / max | 45 / 175.9 / 281 | 5 / 65.2 / 417 |
| Chunks с section | 144 | 330 |
| Покрыто sources | 10 | 10 |
| JSON bytes | 2742949 | 5885026 |
| SQLite bytes | 1867776 | 4689920 |

## Практические выводы

Fixed-size даёт простой baseline и предсказуемый верхний предел размера, но границы могут объединять соседние смысловые разделы.

Structure-aware сохраняет path заголовков Markdown и границы Python-блоков; крупные разделы всё равно дробятся с overlap. Размеры chunks поэтому менее равномерны.

Fixed-size полезен для однородного сырого текста. Structure-aware предпочтителен для документации и кода, когда section metadata важна для retrieval и объяснимости.

## Sample retrieval

Retrieval — sanity check индекса, без генеративной LLM.

### Как запускать historical day-specific сценарии?

- `fixed`: `fixed:docs-development-rules.md:0001`, score `0.691067`, source `corpus/docs-development-rules.md`, section `Правила развития актуального AI harness`.
- `structure`: `structure:docs-development-rules.md:0001`, score `0.750865`, source `corpus/docs-development-rules.md`, section `Правила развития актуального AI harness > Разделение ответственности > Snapshots дней`.

### Какие правила public export?

- `fixed`: `fixed:docs-cli.md:0000`, score `0.692068`, source `corpus/docs-cli.md`, section `CLI актуального harness`.
- `structure`: `structure:week-04-day-readmes.md:0080`, score `0.730498`, source `corpus/week-04-day-readmes.md`, section `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки`.

### Что такое MCP orchestration?

- `fixed`: `fixed:week-04-day-readmes.md:0024`, score `0.755732`, source `corpus/week-04-day-readmes.md`, section `Public README документов Week 04`.
- `structure`: `structure:week-04-day-readmes.md:0058`, score `0.853025`, source `corpus/week-04-day-readmes.md`, section `Day 20 — Orchestration MCP > Исходное условие`.

### Как устроены context strategies?

- `fixed`: `fixed:week-02-day-readmes.md:0010`, score `0.730239`, source `corpus/week-02-day-readmes.md`, section `Public README документов Week 02`.
- `structure`: `structure:week-02-day-readmes.md:0044`, score `0.784622`, source `corpus/week-02-day-readmes.md`, section `Day 10 — Context Management Strategies > Дополнительные учебные заметки`.

### Какие проверки нужно запускать перед сдачей?

- `fixed`: `fixed:week-01-day-readmes.md:0003`, score `0.729536`, source `corpus/week-01-day-readmes.md`, section `Public README документов Week 01`.
- `structure`: `structure:week-02-day-readmes.md:0013`, score `0.818825`, source `corpus/week-02-day-readmes.md`, section `Day 07 — Save Context > Цель задания`.

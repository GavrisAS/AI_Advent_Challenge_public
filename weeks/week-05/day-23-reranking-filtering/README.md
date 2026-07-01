# Day 23 — Реранкинг и фильтрация

## 🎥 Видео-отчёт

> [▶️ Смотреть видео-отчёт](https://drive.google.com/open?id=17ZmmSj6LH3GyN_UjVPN0XQuwRVHaksQ3)

## Исходное условие

🔥 День 23. Реранкинг и фильтрация

Добавьте второй этап после поиска:

👉 reranker или фильтр релевантности (порог similarity / отдельная модель / heuristic)

Настройте:

👉 порог отсечения нерелевантных результатов
👉 топ-K до и после фильтрации

Сравните:

👉 качество без фильтра/rewriting
👉 качество с фильтром

Результат:

Улучшенный RAG: фильтрация/реранкинг + query rewrite + сравнение режимов

Формат:

Видео + Код

## Цель задания

Добавить к Day 22 отдельные стадии query rewrite и второго отбора кандидатов, а затем измеримо
сравнить plain RAG с improved RAG на тех же 10 вопросах. Особые regression cases — q02 и q03.

## Реализация

Pipeline разделён на независимые стадии:

```text
original question
→ optional deterministic rewrite
→ retrieve top_k_before
→ similarity threshold
→ heuristic reranking
→ select top_k_after
→ grounded prompt
→ LLM answer
→ deterministic evaluation/report
```

`plain_rag` ищет top-4 по исходному вопросу без rewrite и filter. `improved_rag` расширяет запрос
проектными терминами, извлекает top-8, отбрасывает кандидатов ниже threshold `0.25`, вычисляет
`final_score = similarity + source_bonus + section_bonus + keyword_bonus` и передаёт LLM top-4.
Expected sources используются только evaluator, не reranker. Если threshold удаляет всё, pipeline
сохраняет лучший по исходной similarity chunk и ставит `fallback_used=true`.

Rewrite поддерживает режимы `none`, `heuristic`, `llm`. Offline tests используют воспроизводимый
`heuristic`; LLM rewrite опционален. Reranker поддерживает `none`, `similarity_threshold`,
`heuristic`. Original question, rewritten query, обе выдачи, score components, ответы и метрики
сохраняются в JSON/Markdown.

Актуальный `packages/ai_advent_agent` получил reusable modules `query_rewrite.py`, `reranking.py`,
`pipelines.py` и `reports_day23.py`, но не получил day-specific CLI.

## Новые команды

| Команда | Назначение |
|---|---|
| `ai-advent-scenarios reranking-filtering-demo` | Snapshot-local сравнение plain/improved RAG с настройками rewrite, reranking, threshold и top-K. |

## Структура файлов

```text
day-23-reranking-filtering/
├── README.md
├── corpus/                       # собственная public-safe копия corpus
├── eval/control-questions.json   # 10 вопросов, включая q02/q03
├── artifacts/
│   ├── day23-comparison.json
│   ├── day23-comparison.md
│   ├── sample-improved-rag-answer.json
│   ├── structure-index.json
│   ├── structure-index.sqlite3
│   └── index-manifest.json
└── snapshot/
    ├── pyproject.toml
    ├── uv.lock
    ├── src/ai_advent_agent/
    └── tests/
```

Snapshot не читает corpus, index или runtime-файлы Day 21/22.

## Как запустить

### Актуальный пакет

Актуальный package содержит переиспользуемые RAG-компоненты. Он остаётся integrated harness и не
является runner конкретного дня; day-specific запуск выполняется только из snapshot ниже.

### Snapshot Day 23

#### Offline smoke

API key, сеть и Ollama не нужны. Hash/fake проверяет orchestration, но не semantic quality:

```bash
cd weeks/week-05/day-23-reranking-filtering/snapshot

uv run ai-advent-scenarios reranking-filtering-demo \
  --corpus-dir ../corpus \
  --questions-json ../eval/control-questions.json \
  --embedding-backend hash \
  --llm-provider fake \
  --rewrite-mode heuristic \
  --rerank-mode heuristic \
  --top-k-plain 4 \
  --top-k-before 8 \
  --top-k-after 4 \
  --similarity-threshold 0.10 \
  --output-dir .tmp/day23-fake-demo \
  --hash-dim 64 \
  --rebuild-index
```

#### Real demo

Нужны запущенный Ollama, модель `nomic-embed-text`, network и `DEEPSEEK_API_KEY` в окружении или
приватном корневом `.env`:

```bash
cd weeks/week-05/day-23-reranking-filtering/snapshot

uv run ai-advent-scenarios reranking-filtering-demo \
  --corpus-dir ../corpus \
  --questions-json ../eval/control-questions.json \
  --embedding-backend ollama \
  --embedding-model nomic-embed-text \
  --llm-provider deepseek \
  --model deepseek-v4-flash \
  --rewrite-mode heuristic \
  --rerank-mode heuristic \
  --top-k-plain 4 \
  --top-k-before 8 \
  --top-k-after 4 \
  --similarity-threshold 0.25 \
  --output-dir ../artifacts \
  --rebuild-index
```

Threshold `0.25` сохранён: на фактических normalized Ollama scores он не скрывает кандидатов и
оставляет reranker основным вторым этапом. Его нужно перекалибровать при смене embedding model.

## Сценарий демонстрации для видео

1. Открыть этот README и показать различие `plain_rag` / `improved_rag`.
2. Показать `query_rewrite.py`, `reranking.py`, затем `pipelines.py`: этапы не встроены в prompt.
3. Открыть q02/q03 в `eval/control-questions.json`.
4. Запустить offline smoke в `.tmp/day23-fake-demo`; секреты не нужны.
5. Запустить real demo с Ollama + DeepSeek или показать сохранённый `index-manifest.json`, где
   зафиксированы реальные backend/provider/model.
6. Открыть `day23-comparison.md`: сначала aggregate, затем q02/q03 с chunks до/после и scores.
7. Открыть `sample-improved-rag-answer.json` и показать rewrite, score components и ответ q03.
8. Запустить snapshot tests: `uv run pytest -q`.
9. Удалить только временный smoke: `rm -rf .tmp/day23-fake-demo`; финальные artifacts не удалять.

## Результаты

Финальные artifacts собраны через Ollama `nomic-embed-text` и DeepSeek
`deepseek-v4-flash`, не через hash/fake:

- expected source hits: plain `8`, improved `9`;
- expected points covered: plain `10`, improved `14`;
- questions improved/regressed/same: `3 / 1 / 6`;
- q02: source miss→hit, coverage `1→2`;
- q03: source miss→hit, coverage `0→2`;
- q04 честно зафиксирован как regression по source hit.

Подробности: [Markdown report](artifacts/day23-comparison.md) и
[JSON report](artifacts/day23-comparison.json).

## Выводы

Query rewrite и второй этап отбора улучшили главные regression cases Day 22 и aggregate-метрики,
но не сделали retrieval монотонно лучше на каждом вопросе. Trace до/после фильтрации показывает
цену расширения запроса: новые термины повышают recall, но иногда вытесняют нужный источник.
Threshold, top-K и bonuses поэтому должны калиброваться на eval set, а не скрывать слабые места.

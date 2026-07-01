# Day 23 — Реранкинг, фильтрация и query rewrite

## Настройки

- Plain RAG: top_k=`4`, без rewrite и filter.
- Improved RAG: rewrite=`heuristic`, top_k_before=`8`, threshold=`0.25`, top_k_after=`4`, rerank=`heuristic`.
- Embeddings: `ollama` / `nomic-embed-text`.
- LLM: `deepseek` / `deepseek-v4-flash`.

## Итоговая таблица

| ID | Вопрос | Plain source hit | Improved source hit | Plain coverage | Improved coverage | Вывод |
|---|---|---:|---:|---:|---:|---|
| q01 | Как запускать historical day-specific сценарии? | 1 | 1 | 0 | 2 | Improved RAG улучшил попадание в источники или покрытие ожидаемых пунктов. |
| q02 | Почему day-specific сценарии не должны запускаться из актуального package? | 0 | 1 | 2 | 1 | Improved RAG улучшил попадание в источники или покрытие ожидаемых пунктов. |
| q03 | Какие проверки нужно запускать перед сдачей изменений с Python-кодом? | 0 | 1 | 0 | 2 | Improved RAG улучшил попадание в источники или покрытие ожидаемых пунктов. |
| q04 | Какие приватные и временные материалы нельзя включать в public export? | 1 | 0 | 0 | 0 | По deterministic-эвристике improved RAG регрессировал на этом вопросе. |
| q05 | Какие metadata сохраняются для chunk в локальном document index? | 1 | 1 | 2 | 2 | По deterministic-эвристике режимы дали одинаковый результат. |
| q06 | Чем fixed-size chunking отличается от structure-aware chunking? | 1 | 1 | 2 | 2 | По deterministic-эвристике режимы дали одинаковый результат. |
| q07 | Зачем нужен hash embedding backend и почему он не заменяет semantic model? | 1 | 1 | 2 | 2 | По deterministic-эвристике режимы дали одинаковый результат. |
| q08 | Какие artifacts создаёт pipeline индексации документов? | 1 | 1 | 2 | 2 | По deterministic-эвристике режимы дали одинаковый результат. |
| q09 | Что означает MCP orchestration в контексте Week 4? | 1 | 1 | 0 | 1 | Improved RAG улучшил попадание в источники или покрытие ожидаемых пунктов. |
| q10 | Как связаны актуальный package и snapshot каждого завершённого дня? | 1 | 1 | 1 | 1 | По deterministic-эвристике режимы дали одинаковый результат. |

## Aggregate

- Source hits: plain `8`, improved `9`.
- Expected points: plain `11`, improved `15`.
- Вопросы: improved `3`, regressed `2`, same `5`.

## Детализация по вопросам

### q01 — Как запускать historical day-specific сценарии?

**Original question:** Как запускать historical day-specific сценарии?

**Rewritten query:** Как запускать historical day-specific сценарии? snapshot historical runner ai-advent-scenarios актуальный package development rules

#### Plain RAG chunks

1. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Разделение ответственности > Snapshots дней`; similarity `0.750864`; chunk `structure:docs-development-rules.md:0001`.
2. `corpus/week-02-day-readmes.md` — `Day 08 — Tokens Accounting > Цель задания`; similarity `0.744594`; chunk `structure:week-02-day-readmes.md:0023`.
3. `corpus/week-02-day-readmes.md` — `Day 07 — Save Context > Цель задания`; similarity `0.74365`; chunk `structure:week-02-day-readmes.md:0013`.
4. `corpus/week-01-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.716039`; chunk `structure:week-01-day-readmes.md:0039`.

#### Improved RAG chunks before filtering

1. `corpus/week-02-day-readmes.md` — `Day 10 — Context Management Strategies > Как запустить`; similarity `0.860866`; chunk `structure:week-02-day-readmes.md:0047`.
2. `corpus/docs-cli.md` — `CLI актуального harness > Текущий entry point`; similarity `0.833539`; chunk `structure:docs-cli.md:0000`.
3. `corpus/week-03-day-readmes.md` — `Day 14 — State Invariants > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.828479`; chunk `structure:week-03-day-readmes.md:0053`.
4. `corpus/week-03-day-readmes.md` — `Day 13 — Состояние задачи > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.826037`; chunk `structure:week-03-day-readmes.md:0039`.
5. `corpus/week-03-day-readmes.md` — `Day 12 — Персонализация ассистента > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.824105`; chunk `structure:week-03-day-readmes.md:0025`.
6. `corpus/docs-cli.md` — `CLI актуального harness > Что больше не поддерживается`; similarity `0.818185`; chunk `structure:docs-cli.md:0023`.
7. `corpus/week-03-day-readmes.md` — `Day 15 — Контролируемые переходы состояний > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.814113`; chunk `structure:week-03-day-readmes.md:0067`.
8. `corpus/project-readme.md` — `AI Advent Challenge > Актуальный пакет`; similarity `0.80872`; chunk `structure:project-readme.md:0005`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/docs-cli.md` — `CLI актуального harness > Текущий entry point`; similarity `0.833539`, final `0.948084`; chunk `structure:docs-cli.md:0000`.
2. `corpus/project-readme.md` — `AI Advent Challenge > Актуальный пакет`; similarity `0.80872`, final `0.931902`; chunk `structure:project-readme.md:0005`.
3. `corpus/week-02-day-readmes.md` — `Day 10 — Context Management Strategies > Как запустить`; similarity `0.860866`, final `0.926321`; chunk `structure:week-02-day-readmes.md:0047`.
4. `corpus/week-03-day-readmes.md` — `Day 14 — State Invariants > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.828479`, final `0.918933`; chunk `structure:week-03-day-readmes.md:0053`.

Fallback: `false`.

#### Ответ plain RAG

На основе предоставленного контекста, для запуска historical day-specific сценариев необходимо использовать snapshot-local сценарии. Нельзя предлагать запуск исторического сценария через актуальный `packages/ai_advent_agent`. Если правится документация запуска, day-specific offline/online/video сценарии должны оставаться snapshot-local.

**Источники:**
- source: corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Разделение ответственности > Snapshots дней, chunk_id: structure:docs-development-rules.md:0001

#### Ответ improved RAG

На основе предоставленного контекста, для запуска historical day-specific сценариев необходимо:

1. Использовать соответствующий snapshot дня, который сохранён в `weeks/**/snapshot/**`.
2. Следовать инструкциям README конкретного дня и его snapshot.
3. Запускать команду из директории snapshot.

Пример для Day 10:
```bash
cd weeks/week-02/day-10-context-management-strategies/snapshot
uv run day10-scenarios context-strategies-comparison
```

Актуальный пакет `packages/ai_advent_agent` не используется как runner исторических day-specific сценариев.

**Источники:**
- corpus/docs-cli.md, section: CLI актуального harness > Текущий entry point, chunk_id: structure:docs-cli.md:0000
- corpus/project-readme.md, section: AI Advent Challenge > Актуальный пакет, chunk_id: structure:project-readme.md:0005
- corpus/week-02-day-readmes.md, section: Day 10 — Context Management Strategies > Как запустить, chunk_id: structure:week-02-day-readmes.md:0047
- corpus/week-03-day-readmes.md, section: Day 14 — State Invariants > Как запустить > Актуальный пакет > Online/interactive агент, chunk_id: structure:week-03-day-readmes.md:0053

### q02 — Почему day-specific сценарии не должны запускаться из актуального package?

**Original question:** Почему day-specific сценарии не должны запускаться из актуального package?

**Rewritten query:** Почему day-specific сценарии не должны запускаться из актуального package? snapshot historical runner ai-advent-scenarios актуальный package development rules

#### Plain RAG chunks

1. `corpus/week-02-day-readmes.md` — `Day 10 — Context Management Strategies > Как запустить`; similarity `0.82422`; chunk `structure:week-02-day-readmes.md:0047`.
2. `corpus/week-03-day-readmes.md` — `Day 14 — State Invariants > Как запустить > Актуальный пакет > Offline-сценарий`; similarity `0.797955`; chunk `structure:week-03-day-readmes.md:0052`.
3. `corpus/week-03-day-readmes.md` — `Day 12 — Персонализация ассистента > Как запустить > Актуальный пакет > Offline-сценарий`; similarity `0.797715`; chunk `structure:week-03-day-readmes.md:0024`.
4. `corpus/week-03-day-readmes.md` — `Day 15 — Контролируемые переходы состояний > Как запустить > Актуальный пакет > Offline-сценарий`; similarity `0.795732`; chunk `structure:week-03-day-readmes.md:0066`.

#### Improved RAG chunks before filtering

1. `corpus/week-02-day-readmes.md` — `Day 10 — Context Management Strategies > Как запустить`; similarity `0.900801`; chunk `structure:week-02-day-readmes.md:0047`.
2. `corpus/docs-cli.md` — `CLI актуального harness > Текущий entry point`; similarity `0.868488`; chunk `structure:docs-cli.md:0000`.
3. `corpus/docs-cli.md` — `CLI актуального harness > Что больше не поддерживается`; similarity `0.864691`; chunk `structure:docs-cli.md:0023`.
4. `corpus/week-03-day-readmes.md` — `Day 14 — State Invariants > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.855697`; chunk `structure:week-03-day-readmes.md:0053`.
5. `corpus/week-03-day-readmes.md` — `Day 13 — Состояние задачи > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.851198`; chunk `structure:week-03-day-readmes.md:0039`.
6. `corpus/week-03-day-readmes.md` — `Day 12 — Персонализация ассистента > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.849673`; chunk `structure:week-03-day-readmes.md:0025`.
7. `corpus/project-readme.md` — `AI Advent Challenge > Актуальный пакет`; similarity `0.839651`; chunk `structure:project-readme.md:0005`.
8. `corpus/week-03-day-readmes.md` — `Day 15 — Контролируемые переходы состояний > Как запустить > Актуальный пакет > Online/interactive агент`; similarity `0.834611`; chunk `structure:week-03-day-readmes.md:0067`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/docs-cli.md` — `CLI актуального harness > Текущий entry point`; similarity `0.868488`, final `0.998488`; chunk `structure:docs-cli.md:0000`.
2. `corpus/week-02-day-readmes.md` — `Day 10 — Context Management Strategies > Как запустить`; similarity `0.900801`, final `0.975801`; chunk `structure:week-02-day-readmes.md:0047`.
3. `corpus/project-readme.md` — `AI Advent Challenge > Актуальный пакет`; similarity `0.839651`, final `0.969651`; chunk `structure:project-readme.md:0005`.
4. `corpus/docs-cli.md` — `CLI актуального harness > Что больше не поддерживается`; similarity `0.864691`, final `0.964691`; chunk `structure:docs-cli.md:0023`.

Fallback: `false`.

#### Ответ plain RAG

На основе предоставленного контекста, day-specific сценарии не должны запускаться из актуального package, потому что актуальный `packages/ai_advent_agent` остаётся интегрированным harness, а не runner-ом исторических day-specific сценариев (источник: corpus/week-02-day-readmes.md, section: Day 10 — Context Management Strategies, chunk_id: structure:week-02-day-readmes.md:0047). Кроме того, day-specific runner (в том числе offline runner) удалён из актуального package, а текущие проверки выполняются package tests; историческую демонстрацию следует запускать из соответствующего Snapshot (источники: corpus/week-03-day-readmes.md, sections: Day 14 — State Invariants, Day 12 — Персонализация ассистента, Day 15 — Контролируемые переходы состояний; chunk_id: structure:week-03-day-readmes.md:0052, 0024, 0066).

**Источники**  
- corpus/week-02-day-readmes.md, section: Day 10 — Context Management Strategies, chunk_id: structure:week-02-day-readmes.md:0047  
- corpus/week-03-day-readmes.md, section: Day 14 — State Invariants, chunk_id: structure:week-03-day-readmes.md:0052  
- corpus/week-03-day-readmes.md, section: Day 12 — Персонализация ассистента, chunk_id: structure:week-03-day-readmes.md:0024  
- corpus/week-03-day-readmes.md, section: Day 15 — Контролируемые переходы состояний, chunk_id: structure:week-03-day-readmes.md:0066

#### Ответ improved RAG

Day-specific сценарии не должны запускаться из актуального package, потому что актуальный package является интегрированным harness, а не runner-ом исторических day-specific сценариев. Day-specific runners удалены из актуального package и сохранены в `weeks/**/snapshot/**`, где они не определяют интерфейс текущего harness.

Источники:
- corpus/docs-cli.md, section: CLI актуального harness > Текущий entry point, chunk_id: structure:docs-cli.md:0000
- corpus/week-02-day-readmes.md, section: Day 10 — Context Management Strategies > Как запустить, chunk_id: structure:week-02-day-readmes.md:0047
- corpus/project-readme.md, section: AI Advent Challenge > Актуальный пакет, chunk_id: structure:project-readme.md:0005

### q03 — Какие проверки нужно запускать перед сдачей изменений с Python-кодом?

**Original question:** Какие проверки нужно запускать перед сдачей изменений с Python-кодом?

**Rewritten query:** Какие проверки нужно запускать перед сдачей изменений с Python-кодом? make check make safety pytest py_compile export_public check_repo_safety development rules

#### Plain RAG chunks

1. `corpus/week-01-day-readmes.md` — `Day 01 — LLM REST API > Исходное условие`; similarity `0.784579`; chunk `structure:week-01-day-readmes.md:0002`.
2. `corpus/week-02-day-readmes.md` — `Day 07 — Save Context > Цель задания`; similarity `0.778409`; chunk `structure:week-02-day-readmes.md:0013`.
3. `corpus/week-04-day-readmes.md` — `Day 16 — Подключение MCP > Цель задания`; similarity `0.773367`; chunk `structure:week-04-day-readmes.md:0003`.
4. `corpus/week-02-day-readmes.md` — `Day 08 — Tokens Accounting > Цель задания`; similarity `0.770605`; chunk `structure:week-02-day-readmes.md:0023`.

#### Improved RAG chunks before filtering

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки`; similarity `0.819417`; chunk `structure:week-04-day-readmes.md:0080`.
2. `corpus/package-readme.md` — `ai_advent_agent > Проверки`; similarity `0.786868`; chunk `structure:package-readme.md:0013`.
3. `corpus/project-readme.md` — `AI Advent Challenge > Проверки`; similarity `0.781184`; chunk `structure:project-readme.md:0006`.
4. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Критерии готовности изменений`; similarity `0.764224`; chunk `structure:docs-development-rules.md:0011`.
5. `corpus/week-01-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env`; similarity `0.744731`; chunk `structure:week-01-day-readmes.md:0028`.
6. `corpus/week-04-day-readmes.md` — `Day 16 — Подключение MCP > Цель задания`; similarity `0.743805`; chunk `structure:week-04-day-readmes.md:0003`.
7. `corpus/week-04-day-readmes.md` — `Day 17 — Первый инструмент MCP > Реализация`; similarity `0.738723`; chunk `structure:week-04-day-readmes.md:0019`.
8. `corpus/week-02-day-readmes.md` — `Day 08 — Tokens Accounting > Реализация`; similarity `0.737537`; chunk `structure:week-02-day-readmes.md:0025`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки`; similarity `0.819417`, final `0.904417`; chunk `structure:week-04-day-readmes.md:0080`.
2. `corpus/package-readme.md` — `ai_advent_agent > Проверки`; similarity `0.786868`, final `0.886868`; chunk `structure:package-readme.md:0013`.
3. `corpus/project-readme.md` — `AI Advent Challenge > Проверки`; similarity `0.781184`, final `0.866184`; chunk `structure:project-readme.md:0006`.
4. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Критерии готовности изменений`; similarity `0.764224`, final `0.864224`; chunk `structure:docs-development-rules.md:0011`.

Fallback: `false`.

#### Ответ plain RAG

Найденных источников недостаточно.

**Источники**  
- corpus/week-01-day-readmes.md, section: Day 01 — LLM REST API > Исходное условие, chunk_id: structure:week-01-day-readmes.md:0002  
- corpus/week-02-day-readmes.md, section: Day 07 — Save Context > Цель задания, chunk_id: structure:week-02-day-readmes.md:0013  
- corpus/week-04-day-readmes.md, section: Day 16 — Подключение MCP > Цель задания, chunk_id: structure:week-04-day-readmes.md:0003  
- corpus/week-02-day-readmes.md, section: Day 08 — Tokens Accounting > Цель задания, chunk_id: structure:week-02-day-readmes.md:0023

#### Ответ improved RAG

Перед сдачей изменений с Python-кодом нужно запускать следующие проверки:

- `make check`
- `make safety`

Также рекомендуется запускать `make clean` и `python scripts/export_public.py --dry-run`.

**Источники:**
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки, chunk_id: structure:week-04-day-readmes.md:0080
- corpus/package-readme.md, section: ai_advent_agent > Проверки, chunk_id: structure:package-readme.md:0013
- corpus/project-readme.md, section: AI Advent Challenge > Проверки, chunk_id: structure:project-readme.md:0006
- corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Критерии готовности изменений, chunk_id: structure:docs-development-rules.md:0011

### q04 — Какие приватные и временные материалы нельзя включать в public export?

**Original question:** Какие приватные и временные материалы нельзя включать в public export?

**Rewritten query:** Какие приватные и временные материалы нельзя включать в public export? .tmp .env .agent_context scripts/export_public.py check_repo_safety development rules

#### Plain RAG chunks

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки`; similarity `0.719541`; chunk `structure:week-04-day-readmes.md:0080`.
2. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Назначение документа`; similarity `0.71518`; chunk `structure:docs-development-rules.md:0000`.
3. `corpus/week-01-day-readmes.md` — `Day 05 — Model Versions > Цель задания`; similarity `0.710625`; chunk `structure:week-01-day-readmes.md:0043`.
4. `corpus/week-02-day-readmes.md` — `Day 07 — Save Context > Цель задания`; similarity `0.710082`; chunk `structure:week-02-day-readmes.md:0013`.

#### Improved RAG chunks before filtering

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки`; similarity `0.800265`; chunk `structure:week-04-day-readmes.md:0080`.
2. `corpus/package-readme.md` — `ai_advent_agent > Проверки`; similarity `0.76029`; chunk `structure:package-readme.md:0013`.
3. `corpus/project-readme.md` — `AI Advent Challenge > Структура`; similarity `0.755848`; chunk `structure:project-readme.md:0003`.
4. `corpus/week-02-day-readmes.md` — `Public README документов Week 02`; similarity `0.742066`; chunk `structure:week-02-day-readmes.md:0000`.
5. `corpus/docs-cli.md` — `CLI актуального harness > Правила обратной совместимости`; similarity `0.739863`; chunk `structure:docs-cli.md:0024`.
6. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Критерии готовности изменений`; similarity `0.739445`; chunk `structure:docs-development-rules.md:0011`.
7. `corpus/week-03-day-readmes.md` — `Day 15 — Контролируемые переходы состояний > Реализация`; similarity `0.732913`; chunk `structure:week-03-day-readmes.md:0063`.
8. `corpus/week-04-day-readmes.md` — `Day 17 — Первый инструмент MCP > Реализация`; similarity `0.732358`; chunk `structure:week-04-day-readmes.md:0019`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки`; similarity `0.800265`, final `0.855265`; chunk `structure:week-04-day-readmes.md:0080`.
2. `corpus/project-readme.md` — `AI Advent Challenge > Структура`; similarity `0.755848`, final `0.815848`; chunk `structure:project-readme.md:0003`.
3. `corpus/week-02-day-readmes.md` — `Public README документов Week 02`; similarity `0.742066`, final `0.782066`; chunk `structure:week-02-day-readmes.md:0000`.
4. `corpus/package-readme.md` — `ai_advent_agent > Проверки`; similarity `0.76029`, final `0.76029`; chunk `structure:package-readme.md:0013`.

Fallback: `false`.

#### Ответ plain RAG

Найденных источников недостаточно.

**Источники**
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки, chunk_id: structure:week-04-day-readmes.md:0080
- corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Назначение документа, chunk_id: structure:docs-development-rules.md:0000
- corpus/week-01-day-readmes.md, section: Day 05 — Model Versions > Цель задания, chunk_id: structure:week-01-day-readmes.md:0043
- corpus/week-02-day-readmes.md, section: Day 07 — Save Context > Цель задания, chunk_id: structure:week-02-day-readmes.md:0013

#### Ответ improved RAG

На основе предоставленного контекста невозможно определить, какие приватные и временные материалы нельзя включать в public export. В контексте упоминается команда `python scripts/export_public.py --dry-run`, но не указаны критерии исключения материалов.

**Найденных источников недостаточно**

**Источники**
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки, chunk_id: structure:week-04-day-readmes.md:0080
- corpus/project-readme.md, section: AI Advent Challenge > Структура, chunk_id: structure:project-readme.md:0003
- corpus/week-02-day-readmes.md, section: Public README документов Week 02, chunk_id: structure:week-02-day-readmes.md:0000
- corpus/package-readme.md, section: ai_advent_agent > Проверки, chunk_id: structure:package-readme.md:0013

### q05 — Какие metadata сохраняются для chunk в локальном document index?

**Original question:** Какие metadata сохраняются для chunk в локальном document index?

**Rewritten query:** Какие metadata сохраняются для chunk в локальном document index? chunk_id source title section start_line end_line

#### Plain RAG chunks

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk`; similarity `0.878315`; chunk `structure:day-21-document-indexing-readme.md:0002`.
2. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.767544`; chunk `structure:day-21-document-indexing-readme.md:0001`.
3. `corpus/docs-cli.md` — `CLI актуального harness > Интерактивный режим и slash-команды`; similarity `0.74493`; chunk `structure:docs-cli.md:0013`.
4. `corpus/README.md` — `Corpus Day 22 > Объём`; similarity `0.738237`; chunk `structure:README.md:0002`.

#### Improved RAG chunks before filtering

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk`; similarity `0.885315`; chunk `structure:day-21-document-indexing-readme.md:0002`.
2. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.76461`; chunk `structure:day-21-document-indexing-readme.md:0001`.
3. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Реализация`; similarity `0.72361`; chunk `structure:week-03-day-readmes.md:0006`.
4. `corpus/week-01-day-readmes.md` — `Day 02 — Answer Format > Реализация`; similarity `0.708521`; chunk `structure:week-01-day-readmes.md:0015`.
5. `corpus/week-01-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.706593`; chunk `structure:week-01-day-readmes.md:0009`.
6. `corpus/docs-cli.md` — `CLI актуального harness > Текущий entry point`; similarity `0.7025`; chunk `structure:docs-cli.md:0000`.
7. `corpus/README.md` — `Corpus Day 22`; similarity `0.697274`; chunk `structure:README.md:0000`.
8. `corpus/README.md` — `Corpus Day 22 > Объём`; similarity `0.696441`; chunk `structure:README.md:0002`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk`; similarity `0.885315`, final `1.055315`; chunk `structure:day-21-document-indexing-readme.md:0002`.
2. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.76461`, final `0.80961`; chunk `structure:day-21-document-indexing-readme.md:0001`.
3. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Реализация`; similarity `0.72361`, final `0.73861`; chunk `structure:week-03-day-readmes.md:0006`.
4. `corpus/week-01-day-readmes.md` — `Day 02 — Answer Format > Реализация`; similarity `0.708521`, final `0.723521`; chunk `structure:week-01-day-readmes.md:0015`.

Fallback: `false`.

#### Ответ plain RAG

На основе предоставленного контекста, для chunk в локальном document index сохраняются следующие metadata:

- `source` — относительный путь исходного документа;
- `title` и `section` — заголовок документа и структурный путь раздела;
- стабильный `chunk_id` и порядковый `chunk_index`;
- `strategy` — `fixed` или `structure`;
- `source_sha256` — hash исходного документа;
- `start_line` и `end_line` — line range фрагмента;
- `char_count` и `word_count`;
- текст chunk и embedding vector.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk, chunk_id: structure:day-21-document-indexing-readme.md:0002

#### Ответ improved RAG

На основе предоставленного контекста, для chunk в локальном document index сохраняются следующие metadata:

- `source` — относительный путь исходного документа;
- `title` и `section` — заголовок документа и структурный путь раздела;
- стабильный `chunk_id` и порядковый `chunk_index`;
- `strategy` — `fixed` или `structure`;
- `source_sha256` — hash исходного документа;
- `start_line` и `end_line` — line range фрагмента;
- `char_count` и `word_count`;
- текст chunk и embedding vector.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk, chunk_id: structure:day-21-document-indexing-readme.md:0002

### q06 — Чем fixed-size chunking отличается от structure-aware chunking?

**Original question:** Чем fixed-size chunking отличается от structure-aware chunking?

**Rewritten query:** Чем fixed-size chunking отличается от structure-aware chunking? chunk_id source title section start_line end_line

#### Plain RAG chunks

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.803372`; chunk `structure:day-21-document-indexing-readme.md:0001`.
2. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk`; similarity `0.757357`; chunk `structure:day-21-document-indexing-readme.md:0002`.
3. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Сценарий демонстрации для видео > C. Демонстрация интерактивного агента и меню команд`; similarity `0.698198`; chunk `structure:week-03-day-readmes.md:0012`.
4. `corpus/docs-cli.md` — `CLI актуального harness > Интерактивный режим и slash-команды`; similarity `0.685154`; chunk `structure:docs-cli.md:0013`.

#### Improved RAG chunks before filtering

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.792043`; chunk `structure:day-21-document-indexing-readme.md:0001`.
2. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk`; similarity `0.789426`; chunk `structure:day-21-document-indexing-readme.md:0002`.
3. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Сценарий демонстрации для видео > C. Демонстрация интерактивного агента и меню команд`; similarity `0.68717`; chunk `structure:week-03-day-readmes.md:0012`.
4. `corpus/week-01-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.677304`; chunk `structure:week-01-day-readmes.md:0009`.
5. `corpus/docs-cli.md` — `CLI актуального harness > Интерактивный режим и slash-команды`; similarity `0.6705`; chunk `structure:docs-cli.md:0013`.
6. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Текущая модель harness > Slash-команды`; similarity `0.667705`; chunk `structure:docs-development-rules.md:0005`.
7. `corpus/week-01-day-readmes.md` — `Day 01 — LLM REST API > Структура файлов`; similarity `0.667002`; chunk `structure:week-01-day-readmes.md:0006`.
8. `corpus/week-03-day-readmes.md` — `Day 14 — State Invariants > Выводы`; similarity `0.666312`; chunk `structure:week-03-day-readmes.md:0058`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk`; similarity `0.789426`, final `0.887608`; chunk `structure:day-21-document-indexing-readme.md:0002`.
2. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.792043`, final `0.857498`; chunk `structure:day-21-document-indexing-readme.md:0001`.
3. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Сценарий демонстрации для видео > C. Демонстрация интерактивного агента и меню команд`; similarity `0.68717`, final `0.68717`; chunk `structure:week-03-day-readmes.md:0012`.
4. `corpus/week-03-day-readmes.md` — `Day 14 — State Invariants > Выводы`; similarity `0.666312`, final `0.682676`; chunk `structure:week-03-day-readmes.md:0058`.

Fallback: `false`.

#### Ответ plain RAG

Fixed-size chunking использует окно до 1600 символов и overlap 200 символов, граница по возможности переносится на конец строки. Эта стратегия проста и даёт сравнительно равномерные chunks, но может разрезать смысловой раздел или объединить соседние темы. Structure-aware chunking учитывает Markdown headings, top-level Python `class` / `def` и границы paragraphs. Для Markdown сохраняется полный section path; слишком крупные sections дополнительно режутся до 2400 символов с overlap 200. Эта стратегия лучше сохраняет смысловые границы документации и более информативную section metadata.

**Источники**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации, chunk_id: structure:day-21-document-indexing-readme.md:0001

#### Ответ improved RAG

На основе предоставленного контекста, **fixed-size chunking** использует окно до 1600 символов и overlap 200 символов, граница по возможности переносится на конец строки. Эта стратегия проста и даёт сравнительно равномерные chunks, но может разрезать смысловой раздел или объединить соседние темы.

**Structure-aware chunking** учитывает Markdown headings, top-level Python `class` / `def` и границы paragraphs. Для Markdown сохраняется полный section path; слишком крупные sections дополнительно режутся до 2400 символов с overlap 200. Эта стратегия лучше сохраняет смысловые границы документации и более информативную section metadata.

**Источники**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации, chunk_id: structure:day-21-document-indexing-readme.md:0001

### q07 — Зачем нужен hash embedding backend и почему он не заменяет semantic model?

**Original question:** Зачем нужен hash embedding backend и почему он не заменяет semantic model?

**Rewritten query:** Зачем нужен hash embedding backend и почему он не заменяет semantic model? deterministic fallback offline tests semantic quality

#### Plain RAG chunks

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Embedding backends`; similarity `0.892158`; chunk `structure:day-21-document-indexing-readme.md:0003`.
2. `corpus/package-readme.md` — `ai_advent_agent > Semantic memory writes`; similarity `0.757879`; chunk `structure:package-readme.md:0006`.
3. `corpus/docs-cli.md` — `CLI актуального harness > Semantic memory write grouped CLI`; similarity `0.751993`; chunk `structure:docs-cli.md:0004`.
4. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Цель задания`; similarity `0.747742`; chunk `structure:week-04-day-readmes.md:0059`.

#### Improved RAG chunks before filtering

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Embedding backends`; similarity `0.849257`; chunk `structure:day-21-document-indexing-readme.md:0003`.
2. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 12. Offline/test fallback`; similarity `0.742793`; chunk `structure:week-04-day-readmes.md:0079`.
3. `corpus/package-readme.md` — `ai_advent_agent > Semantic memory writes`; similarity `0.734572`; chunk `structure:package-readme.md:0006`.
4. `corpus/week-03-day-readmes.md` — `Day 14 — State Invariants > Как запустить > Snapshot Day 14 > Offline-сценарий`; similarity `0.732693`; chunk `structure:week-03-day-readmes.md:0054`.
5. `corpus/docs-cli.md` — `CLI актуального harness > Semantic memory write grouped CLI`; similarity `0.729286`; chunk `structure:docs-cli.md:0004`.
6. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Сценарий демонстрации для видео > B. Демонстрация offline-сценария`; similarity `0.729191`; chunk `structure:week-03-day-readmes.md:0010`.
7. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Результаты`; similarity `0.729164`; chunk `structure:week-04-day-readmes.md:0081`.
8. `corpus/week-03-day-readmes.md` — `Day 13 — Состояние задачи > Как запустить > Snapshot Day 13 > Offline-сценарий`; similarity `0.725398`; chunk `structure:week-03-day-readmes.md:0040`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Embedding backends`; similarity `0.849257`, final `1.009257`; chunk `structure:day-21-document-indexing-readme.md:0003`.
2. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 12. Offline/test fallback`; similarity `0.742793`, final `0.867793`; chunk `structure:week-04-day-readmes.md:0079`.
3. `corpus/package-readme.md` — `ai_advent_agent > Semantic memory writes`; similarity `0.734572`, final `0.774572`; chunk `structure:package-readme.md:0006`.
4. `corpus/docs-cli.md` — `CLI актуального harness > Semantic memory write grouped CLI`; similarity `0.729286`, final `0.769286`; chunk `structure:docs-cli.md:0004`.

Fallback: `false`.

#### Ответ plain RAG

На основе предоставленного контекста:

**Hash embedding backend** нужен для unit tests, CI и offline smoke, потому что не требует Ollama, сети или секретов и даёт воспроизводимые векторы.

**Hash backend не заменяет semantic model**, потому что он не является качественной semantic embedding model: он в основном отражает пересечение токенов и не должен использоваться как финальная оценка semantic retrieval.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Embedding backends, chunk_id: structure:day-21-document-indexing-readme.md:0003

#### Ответ improved RAG

На основе предоставленного контекста:

Hash embedding backend нужен для unit tests, CI и offline smoke, потому что не требует Ollama, сети или секретов и даёт воспроизводимые векторы. Он не заменяет semantic model, потому что не является качественной semantic embedding model: он в основном отражает пересечение токенов и не должен использоваться как финальная оценка semantic retrieval.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Embedding backends, chunk_id: structure:day-21-document-indexing-readme.md:0003

### q08 — Какие artifacts создаёт pipeline индексации документов?

**Original question:** Какие artifacts создаёт pipeline индексации документов?

**Rewritten query:** Какие artifacts создаёт pipeline индексации документов?

#### Plain RAG chunks

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Artifacts индексирующего pipeline`; similarity `0.800288`; chunk `structure:day-21-document-indexing-readme.md:0004`.
2. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Результаты`; similarity `0.764919`; chunk `structure:week-03-day-readmes.md:0015`.
3. `corpus/week-02-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.761357`; chunk `structure:week-02-day-readmes.md:0029`.
4. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.752802`; chunk `structure:day-21-document-indexing-readme.md:0001`.

#### Improved RAG chunks before filtering

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Artifacts индексирующего pipeline`; similarity `0.800288`; chunk `structure:day-21-document-indexing-readme.md:0004`.
2. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Результаты`; similarity `0.764919`; chunk `structure:week-03-day-readmes.md:0015`.
3. `corpus/week-02-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.761357`; chunk `structure:week-02-day-readmes.md:0029`.
4. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.752802`; chunk `structure:day-21-document-indexing-readme.md:0001`.
5. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Сценарий демонстрации для видео > A. Подготовка`; similarity `0.749301`; chunk `structure:week-03-day-readmes.md:0009`.
6. `corpus/week-01-day-readmes.md` — `Day 03 — Reasoning > Структура файлов`; similarity `0.746276`; chunk `structure:week-01-day-readmes.md:0026`.
7. `corpus/week-01-day-readmes.md` — `Day 02 — Answer Format > Структура файлов`; similarity `0.744803`; chunk `structure:week-01-day-readmes.md:0016`.
8. `corpus/week-02-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.74309`; chunk `structure:week-02-day-readmes.md:0019`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Artifacts индексирующего pipeline`; similarity `0.800288`, final `0.983288`; chunk `structure:day-21-document-indexing-readme.md:0004`.
2. `corpus/day-21-document-indexing-readme.md` — `Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации`; similarity `0.752802`, final `0.899802`; chunk `structure:day-21-document-indexing-readme.md:0001`.
3. `corpus/week-03-day-readmes.md` — `Day 11 — Memory Layers > Результаты`; similarity `0.764919`, final `0.825919`; chunk `structure:week-03-day-readmes.md:0015`.
4. `corpus/week-02-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.761357`, final `0.822357`; chunk `structure:week-02-day-readmes.md:0029`.

Fallback: `false`.

#### Ответ plain RAG

На основе предоставленного контекста, pipeline индексации документов создаёт следующие типы artifacts:

- `fixed-index.json` и `fixed-index.sqlite3` — fixed-size index в двух форматах;
- `structure-index.json` и `structure-index.sqlite3` — structure-aware index в двух форматах;
- `chunking-comparison.md` — настройки и сравнение стратегий;
- `sample-search-results.json` — sample top-k retrieval без генеративной LLM;
- `index-manifest.json` — corpus statistics, index settings и точный список artifacts.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Artifacts индексирующего pipeline, chunk_id: structure:day-21-document-indexing-readme.md:0004

#### Ответ improved RAG

На основе предоставленного контекста, pipeline индексации документов создаёт следующие artifacts:

- `fixed-index.json` и `fixed-index.sqlite3` — fixed-size index в двух форматах;
- `structure-index.json` и `structure-index.sqlite3` — structure-aware index в двух форматах;
- `chunking-comparison.md` — настройки и сравнение стратегий;
- `sample-search-results.json` — sample top-k retrieval без генеративной LLM;
- `index-manifest.json` — corpus statistics, index settings и точный список artifacts.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Artifacts индексирующего pipeline, chunk_id: structure:day-21-document-indexing-readme.md:0004

### q09 — Что означает MCP orchestration в контексте Week 4?

**Original question:** Что означает MCP orchestration в контексте Week 4?

**Rewritten query:** Что означает MCP orchestration в контексте Week 4?

#### Plain RAG chunks

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Исходное условие`; similarity `0.814267`; chunk `structure:week-04-day-readmes.md:0058`.
2. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Дополнительные учебные заметки`; similarity `0.805824`; chunk `structure:week-04-day-readmes.md:0060`.
3. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Выводы`; similarity `0.79767`; chunk `structure:week-04-day-readmes.md:0082`.
4. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 4. Запустить online scenario`; similarity `0.783403`; chunk `structure:week-04-day-readmes.md:0071`.

#### Improved RAG chunks before filtering

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Исходное условие`; similarity `0.814267`; chunk `structure:week-04-day-readmes.md:0058`.
2. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Дополнительные учебные заметки`; similarity `0.805824`; chunk `structure:week-04-day-readmes.md:0060`.
3. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Выводы`; similarity `0.79767`; chunk `structure:week-04-day-readmes.md:0082`.
4. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 4. Запустить online scenario`; similarity `0.783403`; chunk `structure:week-04-day-readmes.md:0071`.
5. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 9. Показать финальный Markdown report`; similarity `0.767904`; chunk `structure:week-04-day-readmes.md:0076`.
6. `corpus/week-04-day-readmes.md` — `Day 18 — Планировщик и фоновые задачи через MCP tools > Выводы`; similarity `0.766703`; chunk `structure:week-04-day-readmes.md:0042`.
7. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 5. Показать server registry`; similarity `0.761821`; chunk `structure:week-04-day-readmes.md:0072`.
8. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 7. Показать orchestration trace`; similarity `0.759062`; chunk `structure:week-04-day-readmes.md:0074`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 4. Запустить online scenario`; similarity `0.783403`, final `0.966403`; chunk `structure:week-04-day-readmes.md:0071`.
2. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Исходное условие`; similarity `0.814267`, final `0.961267`; chunk `structure:week-04-day-readmes.md:0058`.
3. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Выводы`; similarity `0.79767`, final `0.94467`; chunk `structure:week-04-day-readmes.md:0082`.
4. `corpus/week-04-day-readmes.md` — `Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 7. Показать orchestration trace`; similarity `0.759062`, final `0.906062`; chunk `structure:week-04-day-readmes.md:0074`.

Fallback: `false`.

#### Ответ plain RAG

На основе предоставленного контекста, **MCP orchestration** в контексте Week 4 означает:

- Регистрацию нескольких MCP-серверов, где агент выбирает нужный инструмент, корректно маршрутизирует запросы и выполняет длинный флоу взаимодействия.
- Это ответственность host-а: серверы публикуют маленькие deterministic capabilities, registry задаёт проверяемое пространство действий, planner выбирает следующий neutral JSON action, validator охраняет границы, router вызывает правильную session, а evidence позволяет доказать выбор и порядок.
- Практическая реализация включает запуск сценария с использованием `--planner llm-json`, где online LLM planner и финальный evidence mode работают в рамках orchestration lifecycle: startup MCP servers, LLM planner turns, MCP tool calls и запись artifacts.

**Источники:**
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Исходное условие, chunk_id: structure:week-04-day-readmes.md:0058
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Выводы, chunk_id: structure:week-04-day-readmes.md:0082
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 4. Запустить online scenario, chunk_id: structure:week-04-day-readmes.md:0071

#### Ответ improved RAG

На основе предоставленного контекста, **MCP orchestration** в контексте Week 4 означает:

- Регистрацию нескольких MCP-серверов, чтобы агент выбирал нужный инструмент, корректно маршрутизировал запросы и выполнял длинный флоу взаимодействия (Фрагмент 2).
- Сценарий, в котором используются инструменты с разных серверов, с проверкой корректности выбора и порядка вызовов (Фрагмент 2).
- Ответственность host-а за multi-server MCP orchestration: servers публикуют маленькие deterministic capabilities, registry задаёт проверяемое пространство действий, planner выбирает следующий neutral JSON action, validator охраняет границы, router вызывает правильную session, а evidence позволяет доказать выбор и порядок (Фрагмент 3).
- Демонстрацию orchestration trace, который доказывает длинный flow и использование tools с разных MCP servers в правильном порядке (Фрагмент 4).

**Источники:**
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Исходное условие, chunk_id: structure:week-04-day-readmes.md:0058
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Выводы, chunk_id: structure:week-04-day-readmes.md:0082
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 7. Показать orchestration trace, chunk_id: structure:week-04-day-readmes.md:0074

### q10 — Как связаны актуальный package и snapshot каждого завершённого дня?

**Original question:** Как связаны актуальный package и snapshot каждого завершённого дня?

**Rewritten query:** Как связаны актуальный package и snapshot каждого завершённого дня?

#### Plain RAG chunks

1. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Разделение ответственности > Snapshots дней`; similarity `0.83186`; chunk `structure:docs-development-rules.md:0001`.
2. `corpus/week-01-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.807217`; chunk `structure:week-01-day-readmes.md:0009`.
3. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Назначение документа`; similarity `0.803587`; chunk `structure:docs-development-rules.md:0000`.
4. `corpus/week-02-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.801962`; chunk `structure:week-02-day-readmes.md:0009`.

#### Improved RAG chunks before filtering

1. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Разделение ответственности > Snapshots дней`; similarity `0.83186`; chunk `structure:docs-development-rules.md:0001`.
2. `corpus/week-01-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.807217`; chunk `structure:week-01-day-readmes.md:0009`.
3. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Назначение документа`; similarity `0.803587`; chunk `structure:docs-development-rules.md:0000`.
4. `corpus/week-02-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.801962`; chunk `structure:week-02-day-readmes.md:0009`.
5. `corpus/week-02-day-readmes.md` — `Day 10 — Context Management Strategies > Как запустить`; similarity `0.791129`; chunk `structure:week-02-day-readmes.md:0047`.
6. `corpus/week-04-day-readmes.md` — `Day 17 — Первый инструмент MCP > Как запустить > Snapshot Day 17 > Online/interactive агент`; similarity `0.786469`; chunk `structure:week-04-day-readmes.md:0025`.
7. `corpus/week-04-day-readmes.md` — `Day 18 — Планировщик и фоновые задачи через MCP tools > Как запустить > Snapshot Day 18 > Online/interactive агент`; similarity `0.786469`; chunk `structure:week-04-day-readmes.md:0039`.
8. `corpus/docs-cli.md` — `CLI актуального harness > Текущий entry point`; similarity `0.782083`; chunk `structure:docs-cli.md:0000`.

#### Improved RAG chunks after filtering/reranking

1. `corpus/docs-development-rules.md` — `Правила развития актуального AI harness > Разделение ответственности > Snapshots дней`; similarity `0.83186`, final `0.909003`; chunk `structure:docs-development-rules.md:0001`.
2. `corpus/docs-cli.md` — `CLI актуального harness > Текущий entry point`; similarity `0.782083`, final `0.859226`; chunk `structure:docs-cli.md:0000`.
3. `corpus/week-01-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.807217`, final `0.858646`; chunk `structure:week-01-day-readmes.md:0009`.
4. `corpus/week-02-day-readmes.md` — `Добавьте DEEPSEEK_API_KEY в .env > Результаты`; similarity `0.801962`, final `0.853391`; chunk `structure:week-02-day-readmes.md:0009`.

Fallback: `false`.

#### Ответ plain RAG

На основе предоставленного контекста, актуальный package и snapshot каждого завершённого дня связаны следующим образом: snapshot является историческим слепком, который сохраняет архитектуру, команды, зависимости и ограничения конкретного дня. Новые улучшения актуального пакета не копируются в старые snapshots автоматически. Исправление исторического snapshot допускается только по отдельной явной задаче, и нельзя предлагать запуск исторического сценария через актуальный `packages/ai_advent_agent`.

**Источники**
- source: corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Разделение ответственности > Snapshots дней, chunk_id: structure:docs-development-rules.md:0001
- source: corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Назначение документа, chunk_id: structure:docs-development-rules.md:0000

#### Ответ improved RAG

На основе предоставленного контекста, актуальный package и snapshot каждого завершённого дня связаны следующим образом: snapshot является историческим слепком, который сохраняет архитектуру, команды, зависимости и ограничения конкретного дня. Новые улучшения актуального пакета не копируются в старые snapshots автоматически. Исправление исторического snapshot допускается только по отдельной явной задаче, и нельзя предлагать запуск исторического сценария через актуальный `packages/ai_advent_agent`. Кроме того, исторические day-specific runners сохранены в `weeks/**/snapshot/**` и не определяют интерфейс текущего harness.

**Источники**
- source: corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Разделение ответственности > Snapshots дней, chunk_id: structure:docs-development-rules.md:0001
- source: corpus/docs-cli.md, section: CLI актуального harness > Текущий entry point, chunk_id: structure:docs-cli.md:0000

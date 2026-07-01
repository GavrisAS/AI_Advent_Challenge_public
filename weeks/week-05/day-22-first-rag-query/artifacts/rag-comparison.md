# Сравнение baseline и RAG — Day 22

Цель: сравнить одну LLM без проектного контекста и с top-k chunks локального индекса.

## Настройки

- Embeddings: `ollama` / `nomic-embed-text`.
- LLM: `deepseek` / `deepseek-v4-flash`.
- Retrieval: plain top-4 без reranking и filtering.

## Сводка

| ID | Baseline points | RAG points | Expected sources | Вывод |
|---|---:|---:|---|---|
| q01 | 0 | 0 | да | без преимущества по эвристике |
| q02 | 0 | 2 | нет | RAG лучше |
| q03 | 0 | 0 | нет | без преимущества по эвристике |
| q04 | 0 | 0 | да | без преимущества по эвристике |
| q05 | 1 | 2 | да | RAG лучше |
| q06 | 0 | 2 | да | RAG лучше |
| q07 | 1 | 2 | да | RAG лучше |
| q08 | 2 | 2 | да | без преимущества по эвристике |
| q09 | 0 | 0 | да | без преимущества по эвристике |
| q10 | 1 | 1 | да | без преимущества по эвристике |

## Подробности

### q01: Как запускать historical day-specific сценарии?

- Baseline: Для точного ответа на ваш вопрос о запуске **historical day-specific сценариев** мне не хватает доступа к внутренней документации, структуре папок или конфигурации вашего конкретного проекта.

Однако, исходя из общей практики работы с такими сценариями (например, в тестировании, аналитике или ETL-процессах), могу описать **наиболее вероятные способы**, которые используются в подобных системах. Пожалуйста, уточните детали вашего проекта, если это не то, что вы ищете.

**Типичные варианты запуска
- RAG: На основе предоставленного контекста, для запуска historical day-specific сценариев необходимо использовать snapshot-local сценарии. Нельзя предлагать запуск исторического сценария через актуальный `packages/ai_advent_agent`. Если правится документация запуска, day-specific offline/online/video сценарии должны оставаться snapshot-local.

**Источники:**
- source: corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Разделение ответственности > Snapshots дней, chunk_id: structure:docs-development-rules.md:0001
- Найденные источники: `corpus/docs-development-rules.md` (0.750864), `corpus/week-02-day-readmes.md` (0.744594), `corpus/week-02-day-readmes.md` (0.74365), `corpus/week-01-day-readmes.md` (0.716039).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q02: Почему day-specific сценарии не должны запускаться из актуального package?

- Baseline: Поскольку у меня нет доступа к внутренней базе знаний вашего проекта, я не могу назвать точные причины, установленные в вашей команде. Однако, исходя из общей практики разработки, могу предположить наиболее вероятные объяснения. Пожалуйста, уточните их у коллег или в документации проекта.

**Наиболее вероятные причины (требуют верификации в вашем проекте):**

1.  **Конфликт версий и зависимостей:** Актуальный `package` (например, `package.json` или собранный пакет) обычно содержит последние стаб
- RAG: На основе предоставленного контекста, day-specific сценарии не должны запускаться из актуального package, потому что актуальный `packages/ai_advent_agent` остаётся интегрированным harness, а не runner-ом исторических day-specific сценариев (источник: corpus/week-02-day-readmes.md, section: Day 10 — Context Management Strategies > Как запустить, chunk_id: structure:week-02-day-readmes.md:0047). Кроме того, day-specific runner (или offline runner) удалён из актуального package, и текущие проверки выполняются package tests, а историческую демонстрацию следует запускать из соответствующего Snapshot (источники: corpus/week-03-day-readmes.md, section: Day 14 — State Invariants > Как запустить > Актуальный пакет > Offline-сценарий, chunk_id: structure:week-03-day-readmes.md:0052; corpus/week-03-d
- Найденные источники: `corpus/week-02-day-readmes.md` (0.82422), `corpus/week-03-day-readmes.md` (0.797955), `corpus/week-03-day-readmes.md` (0.797715), `corpus/week-03-day-readmes.md` (0.795732).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q03: Какие проверки нужно запускать перед сдачей изменений с Python-кодом?

- Baseline: Поскольку у меня нет доступа к внутренней базе знаний вашего проекта, я не могу назвать точные команды или скрипты, которые используются именно у вас. Однако, основываясь на общепринятой практике для Python-проектов, перед сдачей изменений (commit/push) обычно рекомендуется запускать следующие проверки:

1.  **Линтер (Linter):** Проверка стиля кода (например, `flake8`, `pylint`, `ruff`).
2.  **Форматтер (Formatter):** Проверка или автоматическое приведение кода к единому стилю (например, `black`
- RAG: Найденных источников недостаточно.

**Источники**
- corpus/week-01-day-readmes.md, section: Day 01 — LLM REST API > Исходное условие, chunk_id: structure:week-01-day-readmes.md:0002
- corpus/week-02-day-readmes.md, section: Day 07 — Save Context > Цель задания, chunk_id: structure:week-02-day-readmes.md:0013
- corpus/week-04-day-readmes.md, section: Day 16 — Подключение MCP > Цель задания, chunk_id: structure:week-04-day-readmes.md:0003
- corpus/week-02-day-readmes.md, section: Day 08 — Tokens Accounting > Цель задания, chunk_id: structure:week-02-day-readmes.md:0023
- Найденные источники: `corpus/week-01-day-readmes.md` (0.784579), `corpus/week-02-day-readmes.md` (0.778409), `corpus/week-04-day-readmes.md` (0.773367), `corpus/week-02-day-readmes.md` (0.770605).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q04: Какие приватные и временные материалы нельзя включать в public export?

- Baseline: Поскольку у меня нет доступа к внутренней базе знаний вашего проекта, я не могу назвать точный перечень правил или файлов, действующих в вашей системе. Однако, основываясь на общих принципах безопасности и управления данными, в публичный экспорт (public export) **не следует включать** следующие категории приватных и временных материалов (если они присутствуют в проекте):

1.  **Персональные данные (PII):** Имена, адреса, email, номера телефонов, IP-адреса пользователей или сотрудников.
2.  **Учё
- RAG: Найденных источников недостаточно.

**Источники**
- corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Сценарий демонстрации для видео > 13. Финальные проверки, chunk_id: structure:week-04-day-readmes.md:0080
- corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Назначение документа, chunk_id: structure:docs-development-rules.md:0000
- corpus/week-01-day-readmes.md, section: Day 05 — Model Versions > Цель задания, chunk_id: structure:week-01-day-readmes.md:0043
- corpus/week-02-day-readmes.md, section: Day 07 — Save Context > Цель задания, chunk_id: structure:week-02-day-readmes.md:0013
- Найденные источники: `corpus/week-04-day-readmes.md` (0.719541), `corpus/docs-development-rules.md` (0.71518), `corpus/week-01-day-readmes.md` (0.710625), `corpus/week-02-day-readmes.md` (0.710082).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q05: Какие metadata сохраняются для chunk в локальном document index?

- Baseline: Для ответа на ваш вопрос о metadata, сохраняемых для chunk в локальном document index, у меня нет доступа к внутренней базе знаний этого конкретного проекта. Без точных данных о реализации (например, какая библиотека или фреймворк используется — LangChain, LlamaIndex, собственное решение) я не могу назвать точный набор полей.

Однако, основываясь на общей практике в подобных системах, можно предположить, что типичные metadata для chunk включают:
- **source** (источник: имя файла, URL или идентиф
- RAG: На основе предоставленного контекста, для chunk в локальном document index сохраняются следующие metadata:

- `source` — относительный путь исходного документа;
- `title` и `section` — заголовок документа и структурный путь раздела;
- стабильный `chunk_id` и порядковый `chunk_index`;
- `strategy` — `fixed` или `structure`;
- `source_sha256` — hash исходного документа;
- `start_line` и `end_line` — line range фрагмента;
- `char_count` и `word_count`;
- текст chunk и embedding vector.

**Источники**:
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Metadata каждого chunk, chunk_id: structure:day-21-document-indexing-readme.md:0002
- Найденные источники: `corpus/day-21-document-indexing-readme.md` (0.878315), `corpus/day-21-document-indexing-readme.md` (0.767544), `corpus/docs-cli.md` (0.74493), `corpus/README.md` (0.738237).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q06: Чем fixed-size chunking отличается от structure-aware chunking?

- Baseline: Для ответа на ваш вопрос о различиях между **fixed-size chunking** (разбиение на фрагменты фиксированного размера) и **structure-aware chunking** (разбиение с учётом структуры) я могу опираться только на общеизвестные концепции в области обработки текстов и RAG-систем, так как у меня нет доступа к внутренней базе знаний вашего проекта.

**Fixed-size chunking** — это метод, при котором текст делится на фрагменты (чанки) строго определённой длины, например, по количеству символов, слов или токенов
- RAG: Fixed-size chunking использует окно до 1600 символов и overlap 200 символов, граница по возможности переносится на конец строки. Эта стратегия проста и даёт сравнительно равномерные chunks, но может разрезать смысловой раздел или объединить соседние темы. Structure-aware chunking учитывает Markdown headings, top-level Python `class` / `def` и границы paragraphs, для Markdown сохраняется полный section path, а слишком крупные sections дополнительно режутся до 2400 символов с overlap 200. Эта стратегия лучше сохраняет смысловые границы документации и более информативную section metadata.

**Источники**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Pipeline индексации, chunk_id: structure:day-21-document-indexing-re
- Найденные источники: `corpus/day-21-document-indexing-readme.md` (0.803372), `corpus/day-21-document-indexing-readme.md` (0.757357), `corpus/week-03-day-readmes.md` (0.698198), `corpus/docs-cli.md` (0.685154).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q07: Зачем нужен hash embedding backend и почему он не заменяет semantic model?

- Baseline: Для ответа на ваш вопрос о **hash embedding backend** и его отличии от **semantic model** у меня нет доступа к внутренней документации или базе знаний конкретного проекта. Однако я могу объяснить общую логику, исходя из типовой архитектуры систем, работающих с эмбеддингами и семантикой.

**Зачем нужен hash embedding backend?**

Hash embedding backend обычно используется для **быстрого и детерминированного сопоставления** (lookup) между идентификаторами (например, ID сущностей, токенов, строк) и
- RAG: На основе предоставленного контекста:

Hash embedding backend нужен для unit tests, CI и offline smoke, потому что не требует Ollama, сети или секретов и даёт воспроизводимые векторы. Он не заменяет semantic model, потому что не является качественной semantic embedding model: он в основном отражает пересечение токенов и не должен использоваться как финальная оценка semantic retrieval.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Embedding backends, chunk_id: structure:day-21-document-indexing-readme.md:0003
- Найденные источники: `corpus/day-21-document-indexing-readme.md` (0.892158), `corpus/package-readme.md` (0.757879), `corpus/docs-cli.md` (0.751993), `corpus/week-04-day-readmes.md` (0.747742).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q08: Какие artifacts создаёт pipeline индексации документов?

- Baseline: Поскольку у меня нет доступа к внутренней базе знаний вашего проекта, я не могу точно назвать конкретные артефакты, которые создаёт ваш pipeline индексации документов. Состав артефактов сильно зависит от архитектуры системы (например, используется ли Elasticsearch, векторная БД, гибридный поиск) и настроек обработки.

Однако, в типичных системах индексации документов pipeline обычно создаёт следующие категории артефактов (с высокой степенью неопределённости для вашего конкретного случая):

1.  *
- RAG: На основе предоставленного контекста, pipeline индексации документов создаёт следующие типы artifacts:

- `fixed-index.json` и `fixed-index.sqlite3` — fixed-size index в двух форматах;
- `structure-index.json` и `structure-index.sqlite3` — structure-aware index в двух форматах;
- `chunking-comparison.md` — настройки и сравнение стратегий;
- `sample-search-results.json` — sample top-k retrieval без генеративной LLM;
- `index-manifest.json` — corpus statistics, index settings и точный список artifacts.

**Источники:**
- corpus/day-21-document-indexing-readme.md, section: Day 21 — Индексация документов: зафиксированный контекст для Day 22 > Artifacts индексирующего pipeline, chunk_id: structure:day-21-document-indexing-readme.md:0004
- Найденные источники: `corpus/day-21-document-indexing-readme.md` (0.800288), `corpus/week-03-day-readmes.md` (0.764919), `corpus/week-02-day-readmes.md` (0.761357), `corpus/day-21-document-indexing-readme.md` (0.752802).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q09: Что означает MCP orchestration в контексте Week 4?

- Baseline: В контексте Week 4 (предположительно, какого-то курса или программы обучения) термин **MCP orchestration** может означать координацию или управление несколькими **MCP** (Message Control Protocol, Model Context Protocol, или другим специфическим для проекта акронимом). Однако, поскольку у меня нет доступа к внутренней базе знаний вашего проекта, я не могу точно определить, что именно подразумевается под MCP в вашем случае.

**Возможные интерпретации (без привязки к конкретному проекту):**
- Если
- RAG: На основе предоставленного контекста, **MCP orchestration** в контексте Week 4 означает:

- Регистрацию нескольких MCP-серверов, где агент выбирает нужный инструмент, корректно маршрутизирует запросы и выполняет длинный флоу взаимодействия (source: corpus/week-04-day-readmes.md, section: Day 20 — Orchestration MCP > Исходное условие, chunk_id: structure:week-04-day-readmes.md:0058).
- Это **multi-server MCP orchestration**, где host отвечает за orchestration: servers публикуют маленькие deterministic capabilities, registry задаёт проверяемое пространство действий, planner выбирает следующий neutral JSON action, validator охраняет границы, router вызывает правильную session, а evidence позволяет доказать выбор и порядок (source: corpus/week-04-day-readmes.md, section: Day 20 — Orchestration
- Найденные источники: `corpus/week-04-day-readmes.md` (0.814267), `corpus/week-04-day-readmes.md` (0.805824), `corpus/week-04-day-readmes.md` (0.79767), `corpus/week-04-day-readmes.md` (0.783403).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

### q10: Как связаны актуальный package и snapshot каждого завершённого дня?

- Baseline: Для ответа на ваш вопрос мне не хватает доступа к внутренней базе знаний проекта, поэтому я не могу точно описать связь между актуальным package и snapshot каждого завершённого дня.

Если в проекте под «актуальным package» подразумевается текущая версия зависимостей или сборки, а под «snapshot» — срез состояния на конец дня, то логично предположить, что snapshot фиксирует состояние package на момент завершения дня. Однако без конкретных правил проекта (например, как именно формируется snapshot
- RAG: На основе предоставленного контекста, актуальный package и snapshot каждого завершённого дня связаны следующим образом: snapshot является историческим слепком, который сохраняет архитектуру, команды, зависимости и ограничения конкретного дня. Новые улучшения актуального пакета не копируются в старые snapshots автоматически. Исправление исторического snapshot допускается только по отдельной явной задаче, и нельзя предлагать запуск исторического сценария через актуальный `packages/ai_advent_agent`.

**Источники**
- source: corpus/docs-development-rules.md, section: Правила развития актуального AI harness > Разделение ответственности > Snapshots дней, chunk_id: structure:docs-development-rules.md:0001
- Найденные источники: `corpus/docs-development-rules.md` (0.83186), `corpus/week-01-day-readmes.md` (0.807217), `corpus/docs-development-rules.md` (0.803587), `corpus/week-02-day-readmes.md` (0.801962).
- Вывод: Эвристика: совпадение значимых слов; это не LLM-as-judge.

## Общий вывод

RAG получает проверяемый проектный контекст и source metadata; baseline не имеет доступа к внутренним правилам. Числа являются keyword-эвристикой, а не полной оценкой factual correctness. Day 23 добавит query rewrite и этап фильтрации.

# Правила развития актуального AI harness

## Назначение документа

Этот документ описывает текущее правило развития кода в `packages/`.

Он относится к актуальному AI harness и не меняет историю уже завершённых дней курса.

## Разделение ответственности

### Snapshots дней

Каталоги `weeks/week-XX/day-YY-topic/snapshot/` — исторические слепки.

После завершения дня snapshot считается неизменяемым.

Он сохраняет архитектуру, команды, зависимости и ограничения конкретного дня.

В snapshot могут оставаться старые CLI-команды, сценарии и runtime-результаты.

Новые улучшения актуального пакета не копируются в старые snapshots автоматически.

Исправление исторического snapshot допускается только по отдельной явной задаче. Если правится
документация запуска, day-specific offline/online/video сценарии должны оставаться snapshot-local;
нельзя предлагать запуск исторического сценария через актуальный `packages/ai_advent_agent`.

### Актуальный модуль

`packages/ai_advent_agent/` — текущая развивающаяся версия собственного AI harness.

Это не архив интерфейсов всех дней и не compatibility layer для каждого учебного шага.

В актуальном модуле сохраняются изученные функциональные возможности.

Способ доступа к ним может меняться по мере развития архитектуры.

## Допустимые изменения harness

Старые команды можно удалять или заменять более последовательным интерфейсом.

CLI можно унифицировать и группировать по устойчивым namespace-командам.

Большие модули можно разделять по ответственности.

Повторяющуюся логику можно объединять в общие компоненты.

Day-specific сценарии можно удалять, когда они больше не нужны актуальному пакету.

Централизованный `scenarios.py` и console entry point `ai-advent-scenarios` удалены из актуального
package. Исторические runners остаются только в snapshots соответствующих дней.

Новые day-specific runners не добавляются обратно в `packages/`; автоматизация должна опираться
на core helpers, tests или устойчивые grouped CLI-команды.

Временные compatibility aliases не являются бессрочным публичным контрактом.

Изменение не должно молча устранять существующую функциональную возможность.

При удалении интерфейса должна существовать документированная замена или явное решение об отказе.

Новые возможности должны сопровождаться тестами и актуальной документацией.

RAG ingestion/indexing развивается в нейтральном `ai_advent_agent.rag`: loaders, chunkers,
embedding adapters, stores и retrieval helpers не должны зависеть от day-specific runner или
генеративного ответа. Reproducible runners конкретных дней остаются в snapshots.

Изменения public API должны быть отражены в README пакета.

Крупные архитектурные решения фиксируются в `memory-bank/decisions.md`.

Структурные изменения фиксируются в `CHANGELOG.md`.

## Текущая модель harness

### Интерактивный режим

Интерактивный режим остаётся основным интерфейсом для работы человека с агентом.

Он должен показывать понятные ошибки, состояние и доступные действия.

### Slash-команды

Slash-команды управляют сессией, конфигурацией, памятью и состоянием harness.

Команды группируются по namespace и не должны разрастаться в набор несвязанных aliases.

### CLI для автоматизации

Неинтерактивные CLI-команды нужны для тестирования, воспроизводимых запусков и автоматизации.

Их вывод и exit codes должны быть пригодны для скриптов и CI.

Единственным пользовательским entry point остаётся `ai-advent-agent`; временная замена
`ai-advent-scenarios` не создаётся.

Внутренне CLI разделён на parser, runtime paths, agent factory, interactive loop, ask runner,
read-only diagnostics, cleanup/reset, semantic command handlers, MCP handlers и top-level
orchestration.

Read-only diagnostics читают runtime state без `SimpleAgent`, API key и записи файлов. Missing
state не является ошибкой; некорректный persisted format должен давать стабильный ненулевой exit
code.

`ai-advent-agent ask` является single-shot automation command. Он строит `SimpleAgent` через общий
agent factory, вызывает `SimpleAgent.ask()` и требует те же LLM credentials, что interactive mode.

Cleanup/reset commands удаляют явно выбранные runtime-файлы. Они не создают `SimpleAgent`, не
требуют API key, поддерживают `--dry-run`, требуют `--yes` для удаления и не очищают event logs.
Это file cleanup, а не semantic state editing.

Semantic memory/profile/task/invariant grouped commands используют существующие stores/models, не
создают `SimpleAgent`, не требуют API key и не вызывают LLM. Real mutations пишут соответствующие
event logs; `--dry-run` не меняет файлы. Cleanup commands вроде `profile reset --yes`,
`task reset --yes` и `invariant clear --yes` остаются file deletion commands и отделены от
semantic clear/remove операций.

Grouped MCP CLI `ai-advent-agent mcp ...` работает поверх `ai_advent_agent.mcp.*`: remote
discovery, local Tracker tool call, scheduler workflow, tool composition и multi-server
orchestration. Эти commands не создают `SimpleAgent`; scripted composition/orchestration planners
не требуют API key, а `llm-json` planners требуют `DEEPSEEK_API_KEY`. Remote discovery может
требовать network.

Runtime-1 начал разбор `agent.py`: request preparation, prompt assembly, overflow handling и
preflight token report construction вынесены в `ai_advent_agent.runtime`. `SimpleAgent` остаётся
публичной runtime-точкой, а CLI/MCP contract не меняется. Runtime-2 вынес store wiring,
in-memory runtime state persistence helpers, path/save helpers и optional event append wrappers в
`ai_advent_agent.runtime`; constructor signature сохраняется. Runtime-3 вынес
memory/profile/task/invariant domain services в `ai_advent_agent.runtime`, оставив
`SimpleAgent` public facade и не меняя CLI/MCP contract или event payload formats. Runtime-4
завершил final slim pass: summary/facts/branch/token/response helpers вынесены в
`ai_advent_agent.runtime`, а `SimpleAgent` остался фасадом с прежним public API. Нельзя добавлять
subcommand-заглушки, которые выглядят как рабочий пользовательский contract.

### MCP

MCP развивается как отдельный подмодуль `ai_advent_agent.mcp` со своими transport, registry и
orchestration слоями.

MCP-код не должен смешиваться с interactive CLI или persistence без явной границы.

Старые top-level MCP modules `ai_advent_agent.mcp_*.py` являются временными thin compatibility
wrappers. Новые imports, tests и docs должны ссылаться на `ai_advent_agent.mcp.*`.

MCP CLI реализован отдельной группой `ai-advent-agent mcp ...`. Parser/help и non-MCP commands не
должны импортировать MCP SDK; heavy MCP imports выполняются лениво только в MCP handlers.

### Документация

Документация актуального пакета является источником правды по текущему состоянию harness.

README описывает пользовательский запуск и доступные интерфейсы.

Текущий CLI-контракт и slash-команды описаны в
[`cli.md`](cli.md). Этот файл является источником правды по текущему пользовательскому интерфейсу.

Практические безопасные examples поддерживаются в [`examples.md`](examples.md).

Этот документ описывает правила развития и архитектурные границы.

Snapshots документируют только историческое состояние соответствующего дня.

README дней могут кратко указывать, что возможность интегрирована в актуальный harness, но
day-specific scenario launch commands должны вести в snapshot соответствующего дня. Актуальный CLI
документируется в `packages/docs/cli.md`, а не в snapshot README как замена historical runner.

## Runtime-файлы

Корневая `.agent_context/` содержит runtime-состояние актуального harness.

Она не коммитится и игнорируется правилом `/.agent_context/`.

Нельзя использовать глобальное правило `**/.agent_context/`, скрывающее исторические данные дней.

Для временных сценариев актуального пакета используется `.tmp/`.

Runtime-файлы не должны попадать в исходный код пакета или его tests fixtures без необходимости.

Исторические `results/` и `artifacts/` внутри дней не удаляются автоматически.

Runtime-результаты внутри snapshot или day artifacts могут оставаться частью учебного evidence.

Cleanup актуального harness не применяется к завершённым дням.

## Критерии готовности изменений

Функциональность имеет локальные тесты без обязательного обращения к сети.

Документация соответствует фактическим интерфейсам.

Runtime-файлы не появляются в git status.

Завершённые snapshots и day artifacts отсутствуют в diff.

Перед сдачей выполняются `make check` и `make safety`.

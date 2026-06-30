# Examples актуального harness

Примеры ниже используют только `ai-advent-agent` и не восстанавливают scenario layer. Для локальных
semantic/cleanup примеров runtime-файлы направлены в `.tmp/docs-examples/`, чтобы не трогать
обычную `.agent_context/` текущей рабочей сессии.

## 1. Интерактивная сессия

Interactive mode вызывает LLM и требует `DEEPSEEK_API_KEY` в окружении или в `.env`.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent
uv run --project packages/ai_advent_agent ai-advent-agent chat --plain-input
```

## 2. Single-shot ask

`ask` использует тот же runtime pipeline, что interactive mode, и требует `DEEPSEEK_API_KEY`.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent ask --no-persist \
  "Кратко объясни, что делает текущий harness"

echo "Сформулируй короткий checklist проверки" \
  | uv run --project packages/ai_advent_agent ai-advent-agent ask --stdin --no-persist
```

## 3. Inspect context

Read-only diagnostics не требуют API key.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent context inspect \
  --context-file .tmp/docs-examples/messages.json
```

## 4. Add memory note and inspect

Semantic memory commands работают локально и не требуют API key.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent memory note add \
  "Документация должна описывать текущий ai-advent-agent CLI" \
  --short-term-memory-file .tmp/docs-examples/short_term_memory.json \
  --memory-events-file .tmp/docs-examples/memory_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent memory inspect \
  --summary-file .tmp/docs-examples/summary.json \
  --facts-file .tmp/docs-examples/facts.json \
  --short-term-memory-file .tmp/docs-examples/short_term_memory.json \
  --working-memory-file .tmp/docs-examples/working_memory.json \
  --long-term-memory-file .tmp/docs-examples/long_term_memory.json
```

## 5. Create/use profile

Profile commands работают с local `user_profiles.json` и не требуют API key.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent profile create docs-reviewer \
  --user-profiles-file .tmp/docs-examples/user_profiles.json \
  --profile-events-file .tmp/docs-examples/profile_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent profile use docs-reviewer \
  --user-profiles-file .tmp/docs-examples/user_profiles.json \
  --profile-events-file .tmp/docs-examples/profile_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent profile set language "русский" \
  --user-profiles-file .tmp/docs-examples/user_profiles.json \
  --profile-events-file .tmp/docs-examples/profile_events.jsonl
```

## 6. Start task and advance lifecycle

Task lifecycle guarded: planning требует `approve-plan`, done требует `pass-validation`.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent task start "Final docs pass" \
  --task-state-file .tmp/docs-examples/task_state.json \
  --task-events-file .tmp/docs-examples/task_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent task approve-plan \
  --task-state-file .tmp/docs-examples/task_state.json \
  --task-events-file .tmp/docs-examples/task_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent task advance \
  --task-state-file .tmp/docs-examples/task_state.json \
  --task-events-file .tmp/docs-examples/task_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent task advance \
  --task-state-file .tmp/docs-examples/task_state.json \
  --task-events-file .tmp/docs-examples/task_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent task pass-validation \
  --task-state-file .tmp/docs-examples/task_state.json \
  --task-events-file .tmp/docs-examples/task_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent task complete \
  --task-state-file .tmp/docs-examples/task_state.json \
  --task-events-file .tmp/docs-examples/task_events.jsonl
```

## 7. Add invariant and check text

Invariant commands работают локально и не требуют API key.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent invariant add architecture \
  "Не изменять historical snapshots без отдельной задачи" \
  --invariants-file .tmp/docs-examples/invariants.json \
  --invariant-events-file .tmp/docs-examples/invariant_events.jsonl

uv run --project packages/ai_advent_agent ai-advent-agent invariant check \
  "Обнови snapshot текущей версией package" \
  --invariants-file .tmp/docs-examples/invariants.json
```

## 8. Run MCP scripted composition

`scripted` planner не требует API key. Команда пишет artifacts в указанный output dir.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent mcp compose run \
  --planner scripted \
  --goal "Собери tracker report и сохрани его" \
  --output-dir .tmp/docs-examples/mcp/composition
```

## 9. Run MCP scripted orchestration

`scripted` planner не требует API key. `llm-json` planner требует `DEEPSEEK_API_KEY`.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent mcp orchestrate run \
  --planner scripted \
  --goal "Собери итоговый MCP report" \
  --output-dir .tmp/docs-examples/mcp/orchestration
```

## 10. Cleanup local runtime files

Destructive cleanup commands всегда требуют `--yes`.

```bash
uv run --project packages/ai_advent_agent ai-advent-agent context clear --yes \
  --context-file .tmp/docs-examples/messages.json

uv run --project packages/ai_advent_agent ai-advent-agent memory clear --all --yes \
  --summary-file .tmp/docs-examples/summary.json \
  --facts-file .tmp/docs-examples/facts.json \
  --short-term-memory-file .tmp/docs-examples/short_term_memory.json \
  --working-memory-file .tmp/docs-examples/working_memory.json \
  --long-term-memory-file .tmp/docs-examples/long_term_memory.json

uv run --project packages/ai_advent_agent ai-advent-agent profile reset --yes \
  --user-profiles-file .tmp/docs-examples/user_profiles.json

uv run --project packages/ai_advent_agent ai-advent-agent task reset --yes \
  --task-state-file .tmp/docs-examples/task_state.json

uv run --project packages/ai_advent_agent ai-advent-agent invariant clear --yes \
  --invariants-file .tmp/docs-examples/invariants.json

uv run --project packages/ai_advent_agent ai-advent-agent report tokens clear --yes \
  --token-report-file .tmp/docs-examples/token_reports.jsonl
```

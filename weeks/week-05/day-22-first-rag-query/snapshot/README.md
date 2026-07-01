# Snapshot Day 22 — Первый RAG-запрос

Самодостаточный historical runner. По умолчанию читает только `../corpus` и
`../eval/control-questions.json`, а результаты пишет в `../artifacts`.

Offline smoke не требует API key:

```bash
uv run ai-advent-scenarios first-rag-query-demo --embedding-backend hash \
  --hash-dim 64 --llm-provider fake --output-dir .tmp/day22-fake-demo --rebuild-index
```

Реальный demo использует локальный Ollama и `DEEPSEEK_API_KEY`; ключ хранится только в окружении.

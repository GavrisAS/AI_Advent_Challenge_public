# Day 12 — Assistant Personalization

Сценарий выполнен offline, без API-вызовов:

```bash
uv run --project packages/ai_advent_agent ai-advent-scenarios assistant-personalization-demo
```

## Профили

Созданы два демонстрационных профиля без реальных персональных данных:

- `concise_engineer` — русский язык, краткий инженерный стиль, проверяемые команды.
- `teacher` — русский язык, обучающее объяснение, пример и критерии проверки.

## Prompt assembly

Базовый порядок для personalization:

1. system prompt;
2. user profile, если активный профиль существует и не пустой;
3. current user request.

В актуальном агенте этот слой вставляется перед explicit memory layers, чтобы user profile не
смешивался с long-term memory, working memory и task state.

Файлы prompt сохранены в `../artifacts/agent-context`:

- `prompt_no_profile.json`
- `prompt_concise_engineer.json`
- `prompt_teacher.json`

## Сравнение поведения

| Вариант | Prompt tokens | Projected tokens | Иллюстрируемое поведение |
|---|---:|---:|---|
| `no_profile` | 93 | 1 093 | нейтральный ответ без сохранённой персонализации |
| `concise_engineer` | 246 | 1 246 | краткий инженерный ответ с командами и без вводных |
| `teacher` | 251 | 1 251 | обучающее объяснение с причиной, примером и критериями проверки |

## Артефакты

- `artifacts/agent-context/user_profiles.json`
- `artifacts/agent-context/profile_events.jsonl`
- `artifacts/agent-context/token_reports.jsonl`
- `artifacts/agent-context/prompt_no_profile.json`
- `artifacts/agent-context/prompt_concise_engineer.json`
- `artifacts/agent-context/prompt_teacher.json`

## Выводы

Assistant personalization полезна как отдельный слой устойчивых пользовательских предпочтений.
Она не должна быть скрытой long-term memory: профиль управляется явными командами `/profile`,
попадает в prompt как preference guidance и отражается в token reports. Это делает поведение
ассистента воспроизводимым и проверяемым без API-вызовов.

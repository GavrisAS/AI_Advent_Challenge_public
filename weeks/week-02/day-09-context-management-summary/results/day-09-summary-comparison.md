# Day 09 summary comparison

Offline-сценарий сравнивает длинный synthetic dialog в двух режимах:

- без сжатия: весь старый диалог передаётся в prompt;
- с summary memory: старые сообщения заменяются synthetic system summary, последние сообщения остаются как есть.

Сценарий не вызывает внешний LLM API. Summary в этом сравнении синтетическая, но структура prompt соответствует реализации Day 09.

## Результат запуска

```text
# Day 09 summary comparison

- turns: 24
- full_messages: 50
- compressed_messages: 9
- replaced_messages: 42
- recent_messages_limit: 6
- full_prompt_tokens_estimated: 3 569
- compressed_prompt_tokens_estimated: 614
- saved_prompt_tokens_estimated: 2 955
- projected_full_with_max_tokens: 4 569
- projected_compressed_with_max_tokens: 1 614
- early_important_fact_preserved: True

## Summary

Summary старой истории: Пользователя зовут Алексей; проект AI Advent Challenge; кодовое слово amber. Агент должен развивать context management, storage, token accounting, CLI-команды и тесты.
```

## Вывод

Summary memory уменьшила оценку prompt с 3 569 до 614 токенов и заменила 42 старых сообщения одним summary-сообщением. При этом ранний важный факт про пользователя, проект и кодовое слово остался в compressed context.

# Week 02 — Agent tools и context management

## Тема недели

Вторая неделя переводит решения от отдельных API-скриптов к агенту: отдельная сущность агента, сохранение контекста, подсчёт токенов и стратегии управления контекстом.

## Задания недели

| День | Тема | Статус | Папка |
|---|---|---|---|
| day-06 | First Agent | done | [day-06-first-agent](day-06-first-agent/) |
| day-07 | Save Context | done | [day-07-save-context](day-07-save-context/) |
| day-08 | Tokens Accounting | done | [day-08-tokens-accounting](day-08-tokens-accounting/) |
| day-09 | Context Management Summary | done | [day-09-context-management-summary](day-09-context-management-summary/) |
| day-10 | Context Management Strategies | done | [day-10-context-management-strategies](day-10-context-management-strategies/) |

## Ключевые навыки недели

- Выделять агента как отдельную сущность.
- Сохранять и восстанавливать `messages`.
- Считать токены, стоимость и заполнение контекстного окна.
- Проектировать summary memory, sliding window, sticky facts и branching.

## Итоги недели

Дни 6–10 выполнены и имеют snapshot/артефакты. Неделя 02 закрывает базовую линию agent context management: persistence, token accounting, summary memory и стратегии без summary.

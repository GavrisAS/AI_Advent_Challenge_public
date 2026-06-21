# Week 03 — Memory и состояние ассистента

## Тема недели

Третья неделя посвящена memory, состоянию ассистента, memory layers, управлению знаниями и профилем пользователя. Основной фокус — переход от stateless-взаимодействия с отдельными сообщениями к stateful-агенту, который хранит контекст задачи, профиль, ограничения и может управляемо продолжать работу.

## Задания недели

| День | Тема | Статус | Папка |
|---|---|---|---|
| day-11 | Memory Layers | ✅ done | [day-11-memory-layers](day-11-memory-layers/) |
| day-12 | Assistant Personalization | ✅ done | [day-12-assistant-personalization](day-12-assistant-personalization/) |
| day-13 | Task State Machine | ✅ done | [day-13-task-state-machine](day-13-task-state-machine/) |
| day-14 | State Invariants | ✅ done | [day-14-state-invariants](day-14-state-invariants/) |
| day-15 | Controlled State Transitions | ✅ done | [day-15-controlled-state-transitions](day-15-controlled-state-transitions/) |

## Ключевые навыки недели

- Разделять память ассистента на слои.
- Явно выбирать, какие данные сохраняются в какой слой.
- Проектировать stateful-поведение агента.
- Управлять профилем пользователя, рабочим состоянием и долговременными знаниями.
- Фиксировать hard invariants отдельно от profile, memory и task state.
- Контролировать переходы task lifecycle через explicit guards.
- Проверять влияние памяти и состояния на ответы ассистента.

## Итоги недели

Week 03 завершена. В актуальном агенте есть отдельные layers для memory, user profile, task state,
hard invariants и controlled task transitions. Состояние задачи теперь не только сохраняется, но и
переходит по проверяемому lifecycle: план, реализация, validation, финал.

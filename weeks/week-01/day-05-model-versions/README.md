# Day 05 — Model Versions

## Исходное условие

🔥 День 5. Версии моделей

Выполните один и тот же запрос:

- на слабой модели;
- на средней модели;
- на сильной модели.

Замерьте:

- время ответа;
- количество токенов;
- стоимость, если модель платная.

Сравните:

- качество ответов;
- скорость;
- ресурсоёмкость.

Результат: короткий вывод о различиях между моделями + ссылки.

Формат: видео + код.

## Цель задания

Научиться сравнивать модели не только по качеству текста, но и по задержке, расходу токенов и стоимости.

## Реализация

В `snapshot/MODEL_VERSIONS.py` один и тот же запрос выполняется в трёх DeepSeek-конфигурациях:

1. `deepseek-v4-flash` без thinking mode;
2. `deepseek-v4-flash` с thinking mode;
3. `deepseek-v4-pro` с thinking mode.

Скрипт измеряет время ответа, токены из `usage`, cache hit/cache miss при наличии этих полей и примерную стоимость по заданным тарифам.

## Структура файлов

```text
.
├── README.md
├── codex-log.md
├── snapshot/
│   ├── .env.example
│   └── MODEL_VERSIONS.py
├── results/
│   ├── day5_model_versions_results_20260607_223007.md
│   └── day5_model_versions_results_20260607_223007_filled.md
├── artifacts/
└── video/
    └── day-05-model-versions-demo.webm
```

## Как запустить

```bash
cd weeks/week-01/day-05-model-versions/snapshot
cp .env.example .env
# Добавьте DEEPSEEK_API_KEY в .env
python MODEL_VERSIONS.py
```

Если запрос оставить пустым, используется пример по умолчанию про архитектуру AI-агента для разбора email.

## Результаты

- [Сырой отчёт запуска](results/day5_model_versions_results_20260607_223007.md)
- [Заполненный отчёт со сравнением](results/day5_model_versions_results_20260607_223007_filled.md)

## Видео-отчёт

- [Видео выполнения задания](video/day-05-model-versions-demo.webm)

## Выводы

Сравнение моделей должно учитывать не только субъективное качество ответа, но и latency, стоимость и доступный режим reasoning. Для прикладного агента быстрый режим часто выгоднее как default, а более сильный режим стоит включать точечно.

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MAX_TOKENS = 900

DEFAULT_PROMPT = (
    "Предложи архитектуру AI-агента для автоматизации разбора входящих email: "
    "классификация писем, извлечение задач, приоритизация и формирование короткого отчета. "
    "Ответь структурированно: цель, компоненты, алгоритм работы, риски."
)


@dataclass(frozen=True)
class ModelConfig:
    level: str
    name: str
    model: str
    thinking_type: str
    reasoning_effort: str | None
    input_cache_hit_usd_per_1m: float
    input_cache_miss_usd_per_1m: float
    output_usd_per_1m: float


# DeepSeek сейчас официально публикует два актуальных model id: deepseek-v4-flash и deepseek-v4-pro.
# Чтобы получить три уровня для учебного сравнения, используем разные режимы thinking:
# 1) Flash без thinking — быстрый/экономичный режим
# 2) Flash с thinking — тот же Flash, но с рассуждением перед финальным ответом
# 3) Pro с thinking — более сильный режим
MODEL_CONFIGS: list[ModelConfig] = [
    ModelConfig(
        level="Слабая / быстрая",
        name="DeepSeek V4 Flash, non-thinking",
        model="deepseek-v4-flash",
        thinking_type="disabled",
        reasoning_effort=None,
        input_cache_hit_usd_per_1m=0.0028,
        input_cache_miss_usd_per_1m=0.14,
        output_usd_per_1m=0.28,
    ),
    ModelConfig(
        level="Средняя / reasoning",
        name="DeepSeek V4 Flash, thinking",
        model="deepseek-v4-flash",
        thinking_type="enabled",
        reasoning_effort="high",
        input_cache_hit_usd_per_1m=0.0028,
        input_cache_miss_usd_per_1m=0.14,
        output_usd_per_1m=0.28,
    ),
    ModelConfig(
        level="Сильная",
        name="DeepSeek V4 Pro, thinking",
        model="deepseek-v4-pro",
        thinking_type="enabled",
        reasoning_effort="high",
        input_cache_hit_usd_per_1m=0.003625,
        input_cache_miss_usd_per_1m=0.435,
        output_usd_per_1m=0.87,
    ),
]


class DeepSeekError(RuntimeError):
    pass


def load_env_file(env_path: Path | None = None) -> None:
    """Загружает переменные из .env рядом со скриптом без внешних зависимостей."""
    if env_path is None:
        env_path = Path(__file__).resolve().parent / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line.removeprefix("export ").strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


def require_api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print(
            "Ошибка: не найдена переменная окружения DEEPSEEK_API_KEY.\n"
            "Добавьте DEEPSEEK_API_KEY в .env рядом со скриптом или экспортируйте переменную в терминале.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


def ask_int(prompt: str, default: int) -> int:
    while True:
        raw_value = input(f"{prompt} [{default}]: ").strip()
        if not raw_value:
            return default
        try:
            value = int(raw_value)
        except ValueError:
            print("Введите целое число.")
            continue
        if value <= 0:
            print("Значение должно быть больше 0.")
            continue
        return value


def build_messages(user_prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Ты полезный AI-ассистент. Отвечай на русском языке. "
                "Давай практичный, структурированный и проверяемый ответ."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]


def build_payload(config: ModelConfig, user_prompt: str, max_tokens: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": build_messages(user_prompt),
        "stream": False,
        "max_tokens": max_tokens,
        "thinking": {"type": config.thinking_type},
    }

    if config.reasoning_effort:
        payload["reasoning_effort"] = config.reasoning_effort

    return payload


def call_deepseek(api_key: str, config: ModelConfig, user_prompt: str, max_tokens: int) -> dict[str, Any]:
    payload = build_payload(config, user_prompt, max_tokens)

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise DeepSeekError(f"DeepSeek API вернул HTTP {error.code}: {error_body}") from error
    except urllib.error.URLError as error:
        raise DeepSeekError(f"Не удалось подключиться к DeepSeek API: {error}") from error
    elapsed_seconds = time.perf_counter() - started_at

    data = json.loads(response_body)
    choice = data["choices"][0]
    message = choice["message"]

    return {
        "level": config.level,
        "name": config.name,
        "model": config.model,
        "thinking_type": config.thinking_type,
        "reasoning_effort": config.reasoning_effort or "-",
        "content": message.get("content", ""),
        # reasoning_content может возвращаться в thinking mode, но для учебного сравнения
        # выводим только финальный ответ content.
        "has_reasoning_content": bool(message.get("reasoning_content")),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage", {}),
        "elapsed_seconds": elapsed_seconds,
        "estimated_cost_usd": estimate_cost_usd(config, data.get("usage", {})),
    }


def estimate_cost_usd(config: ModelConfig, usage: dict[str, Any]) -> float | None:
    if not usage:
        return None

    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)

    # DeepSeek может вернуть раздельную статистику cache hit / cache miss.
    # Если полей нет, считаем все входные токены cache miss — это консервативная оценка сверху.
    cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
    cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)

    if cache_hit_tokens == 0 and cache_miss_tokens == 0:
        cache_miss_tokens = prompt_tokens

    input_cost = (
        cache_hit_tokens * config.input_cache_hit_usd_per_1m
        + cache_miss_tokens * config.input_cache_miss_usd_per_1m
    ) / 1_000_000
    output_cost = completion_tokens * config.output_usd_per_1m / 1_000_000

    return input_cost + output_cost


def format_cost(value: float | None) -> str:
    if value is None:
        return "-"
    return f"${value:.8f}"


def print_answer(result: dict[str, Any]) -> None:
    usage = result.get("usage") or {}

    print("=" * 90)
    print(f"{result['level']} — {result['name']}")
    print("=" * 90)
    print(result["content"].strip())
    print("\n--- metadata ---")
    print(f"model: {result['model']}")
    print(f"thinking: {result['thinking_type']}")
    print(f"reasoning_effort: {result['reasoning_effort']}")
    print(f"finish_reason: {result['finish_reason']}")
    print(f"elapsed_seconds: {result['elapsed_seconds']:.3f}")
    print(f"prompt_tokens: {usage.get('prompt_tokens')}")
    print(f"completion_tokens: {usage.get('completion_tokens')}")
    print(f"total_tokens: {usage.get('total_tokens')}")
    print(f"estimated_cost_usd: {format_cost(result['estimated_cost_usd'])}")
    print()


def markdown_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Уровень | Модель / режим | Thinking | Время, сек | Prompt tokens | Completion tokens | Total tokens | Cache hit | Cache miss | Finish reason | Стоимость, $ |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]

    for result in results:
        usage = result.get("usage") or {}
        lines.append(
            "| {level} | `{model}` / {name} | {thinking} | {elapsed:.3f} | {prompt} | {completion} | {total} | {hit} | {miss} | `{finish}` | {cost} |".format(
                level=result["level"],
                model=result["model"],
                name=result["name"],
                thinking=result["thinking_type"],
                elapsed=result["elapsed_seconds"],
                prompt=usage.get("prompt_tokens", "-"),
                completion=usage.get("completion_tokens", "-"),
                total=usage.get("total_tokens", "-"),
                hit=usage.get("prompt_cache_hit_tokens", "-"),
                miss=usage.get("prompt_cache_miss_tokens", "-"),
                finish=result.get("finish_reason", "-"),
                cost=format_cost(result.get("estimated_cost_usd")),
            )
        )

    return "\n".join(lines)


def build_markdown_report(user_prompt: str, max_tokens: int, results: list[dict[str, Any]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    parts = [
        "# День 5. Сравнение версий моделей DeepSeek",
        "",
        f"Дата запуска: {now}",
        f"max_tokens: `{max_tokens}`",
        "",
        "## Исходный запрос",
        "",
        user_prompt,
        "",
        "## Использованные уровни",
        "",
        "- **Слабая / быстрая:** `deepseek-v4-flash`, thinking disabled.",
        "- **Средняя / reasoning:** `deepseek-v4-flash`, thinking enabled, reasoning_effort high.",
        "- **Сильная:** `deepseek-v4-pro`, thinking enabled, reasoning_effort high.",
        "",
        "## Ответы",
        "",
    ]

    for result in results:
        usage = result.get("usage") or {}
        parts.extend(
            [
                f"### {result['level']} — {result['name']}",
                "",
                f"Модель: `{result['model']}`  ",
                f"Thinking: `{result['thinking_type']}`  ",
                f"Reasoning effort: `{result['reasoning_effort']}`  ",
                "",
                result["content"].strip(),
                "",
                "#### Metadata",
                "",
                f"- finish_reason: `{result.get('finish_reason')}`",
                f"- elapsed_seconds: `{result['elapsed_seconds']:.3f}`",
                f"- prompt_tokens: `{usage.get('prompt_tokens')}`",
                f"- completion_tokens: `{usage.get('completion_tokens')}`",
                f"- total_tokens: `{usage.get('total_tokens')}`",
                f"- prompt_cache_hit_tokens: `{usage.get('prompt_cache_hit_tokens', '-')}`",
                f"- prompt_cache_miss_tokens: `{usage.get('prompt_cache_miss_tokens', '-')}`",
                f"- estimated_cost_usd: `{format_cost(result.get('estimated_cost_usd'))}`",
                "",
            ]
        )

    parts.extend(
        [
            "## Таблица замеров",
            "",
            markdown_table(results),
            "",
            "## Место для последующего сравнения качества",
            "",
            "<Сравнить вручную после просмотра ответов>",
            "",
        ]
    )

    return "\n".join(parts)


def save_report(report: str) -> Path:
    filename = f"day5_model_versions_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = Path(__file__).resolve().parent / filename
    path.write_text(report, encoding="utf-8")
    return path


def main() -> None:
    load_env_file()
    api_key = require_api_key()

    print("День 5. Сравнение моделей/режимов DeepSeek")
    print("Будет выполнен один и тот же запрос для трех уровней.")
    print("Ответы будут выведены в терминал и сохранены в Markdown-файл.\n")

    max_tokens = ask_int("max_tokens", DEFAULT_MAX_TOKENS)
    user_prompt = input("Запрос для всех моделей [Enter — пример по умолчанию]: ").strip()
    if not user_prompt:
        user_prompt = DEFAULT_PROMPT

    print("\nИсходный запрос:")
    print(user_prompt)
    print()

    results: list[dict[str, Any]] = []

    for config in MODEL_CONFIGS:
        print(f"Выполняю запрос: {config.level} — {config.name}...")
        try:
            result = call_deepseek(api_key, config, user_prompt, max_tokens)
        except DeepSeekError as error:
            print(f"\nОшибка для {config.name}: {error}\n", file=sys.stderr)
            continue

        results.append(result)
        print_answer(result)

    if not results:
        print("Не удалось получить ни одного ответа.", file=sys.stderr)
        sys.exit(1)

    print("Итоговая таблица замеров:")
    print(markdown_table(results))
    print()

    report = build_markdown_report(user_prompt, max_tokens, results)
    report_path = save_report(report)
    print(f"Markdown-отчет сохранен: {report_path}")


if __name__ == "__main__":
    main()

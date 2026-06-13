import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_ANSWER_MAX_TOKENS = 1600
DEFAULT_META_PROMPT_MAX_TOKENS = 900
DEFAULT_COMPARISON_MAX_TOKENS = 1400

DEFAULT_TASK = (
    "Я решил сегодня помыть машину. Автомойка находится в 50 метрах от моего дома. "
    "Как лучше, пойти пешком или поехать на машине?"
)

DEFAULT_EXPECTED_CRITERIA = (
    "Поехать на машине. Ведь мы ее и хотим помыть. "
)


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


load_env_file()

MODEL = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


class DeepSeekError(RuntimeError):
    pass


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


def build_payload(messages: list[dict[str, str]], *, max_tokens: int) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        # Отключаем отдельный reasoning/thinking-режим, чтобы получать обычный финальный ответ.
        "thinking": {"type": "disabled"},
    }


def call_deepseek(api_key: str, messages: list[dict[str, str]], *, max_tokens: int) -> dict[str, Any]:
    payload = build_payload(messages, max_tokens=max_tokens)

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise DeepSeekError(f"DeepSeek API вернул HTTP {error.code}: {error_body}") from error
    except urllib.error.URLError as error:
        raise DeepSeekError(f"Не удалось подключиться к DeepSeek API: {error}") from error

    data = json.loads(response_body)
    choice = data["choices"][0]
    message = choice["message"]

    return {
        "content": message.get("content", ""),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage", {}),
    }


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
            print("Число должно быть больше нуля.")
            continue
        return value


def make_direct_messages(task: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Ты полезный AI-ассистент. Отвечай на русском языке.",
        },
        {
            "role": "user",
            "content": task,
        },
    ]


def make_step_by_step_messages(task: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Ты полезный AI-ассистент. Отвечай на русском языке.",
        },
        {
            "role": "user",
            "content": f"{task}\n\nРешай пошагово. В конце отдельно укажи итоговый ответ.",
        },
    ]


def make_prompt_generation_messages(task: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Ты эксперт по промптингу. Твоя задача — составить промпт, "
                "который поможет другой LLM точно решить задачу."
            ),
        },
        {
            "role": "user",
            "content": (
                "Составь один качественный промпт для решения задачи ниже.\n"
                "Требования к промпту:\n"
                "- промпт должен быть на русском языке;\n"
                "- промпт должен заставить модель проверить условия задачи;\n"
                "- промпт должен попросить модель явно указать итоговый ответ;\n"
                "- не решай задачу сам;\n"
                "- верни только готовый промпт, без пояснений.\n\n"
                f"Задача:\n{task}"
            ),
        },
    ]


def make_meta_solution_messages(generated_prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Ты полезный AI-ассистент. Отвечай на русском языке и строго следуй промпту пользователя.",
        },
        {
            "role": "user",
            "content": generated_prompt,
        },
    ]


def make_expert_group_messages(task: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Ты фасилитатор группы экспертов. Отвечай на русском языке. "
                "Нужно получить независимый взгляд нескольких ролей, а затем общий вывод."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Задача:\n{task}\n\n"
                "Реши задачу через группу экспертов.\n"
                "Дай ответ строго в структуре:\n"
                "1. Аналитик: разбор условий и решение.\n"
                "2. Инженер: алгоритм или проверяемая процедура решения.\n"
                "3. Критик: проверка решения, поиск ошибок и крайних случаев.\n"
                "4. Итоговое решение: короткий финальный ответ."
            ),
        },
    ]


def make_comparison_messages(
    task: str,
    expected_criteria: str,
    direct_answer: str,
    step_by_step_answer: str,
    meta_prompt: str,
    meta_answer: str,
    expert_answer: str,
) -> list[dict[str, str]]:
    criteria_block = expected_criteria.strip() or (
        "Эталон не задан. Оцени точность по внутренней логике, полноте проверки условий "
        "и отсутствию противоречий."
    )

    return [
        {
            "role": "system",
            "content": (
                "Ты строгий проверяющий. Сравни решения одной задачи. "
                "Не переписывай решения полностью, оцени их кратко и объективно."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Задача:\n{task}\n\n"
                f"Критерии точности / эталон:\n{criteria_block}\n\n"
                "Решение 1 — прямой ответ без дополнительных инструкций:\n"
                f"{direct_answer}\n\n"
                "Решение 2 — инструкция 'решай пошагово':\n"
                f"{step_by_step_answer}\n\n"
                "Сгенерированный промпт для способа 3:\n"
                f"{meta_prompt}\n\n"
                "Решение 3 — сначала сгенерирован промпт, затем использован для решения:\n"
                f"{meta_answer}\n\n"
                "Решение 4 — группа экспертов:\n"
                f"{expert_answer}\n\n"
                "Сравни ответы в формате:\n"
                "1. Отличаются ли ответы: кратко.\n"
                "2. Таблица: способ | точность | сильные стороны | слабые стороны.\n"
                "3. Самый точный способ: один вариант и почему.\n"
                "4. Финальный правильный ответ по задаче."
            ),
        },
    ]


def print_result(title: str, result: dict[str, Any]) -> None:
    usage = result.get("usage") or {}
    content = result["content"].strip()

    print("=" * 100)
    print(title)
    print("=" * 100)
    print(content)
    print("\n--- metadata ---")
    print(f"finish_reason: {result.get('finish_reason')}")
    if usage:
        print(f"prompt_tokens: {usage.get('prompt_tokens')}")
        print(f"completion_tokens: {usage.get('completion_tokens')}")
        print(f"total_tokens: {usage.get('total_tokens')}")
    print()


def make_markdown_report(
    task: str,
    expected_criteria: str,
    direct: dict[str, Any],
    step_by_step: dict[str, Any],
    generated_prompt: str,
    meta_solution: dict[str, Any],
    expert_group: dict[str, Any],
    comparison: dict[str, Any],
) -> str:
    return f"""# День 3. Разные способы рассуждения

## Задача

{task}

## Критерии точности / эталон

{expected_criteria or 'Эталон не задан. Оценка выполнялась по внутренней логике задачи.'}

## 1. Прямой ответ без дополнительных инструкций

{direct['content'].strip()}

## 2. Инструкция «решай пошагово»

{step_by_step['content'].strip()}

## 3. Метапромптинг

### Сгенерированный промпт

{generated_prompt.strip()}

### Решение по сгенерированному промпту

{meta_solution['content'].strip()}

## 4. Группа экспертов

{expert_group['content'].strip()}

## Сравнение

{comparison['content'].strip()}
"""


def save_report(report: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(__file__).resolve().parent / f"day3_results_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> None:
    api_key = require_api_key()

    print("День 3. Разные способы рассуждения через DeepSeek API")
    print(f"Модель: {MODEL}\n")

    answer_max_tokens = ask_int("Максимум токенов для каждого решения", DEFAULT_ANSWER_MAX_TOKENS)
    comparison_max_tokens = ask_int("Максимум токенов для сравнения", DEFAULT_COMPARISON_MAX_TOKENS)

    print("\nВведите задачу. Если оставить пусто, будет использована демонстрационная задача:")
    print("\nЗадача:", DEFAULT_TASK)
    print("\nОтвет:", DEFAULT_EXPECTED_CRITERIA)
    task = input("Задача: ").strip() or DEFAULT_TASK

    if task == DEFAULT_TASK:
        expected_criteria = DEFAULT_EXPECTED_CRITERIA
        print("Используется демонстрационная задача и встроенный эталон проверки.\n")
    else:
        print("\nМожно указать эталон или критерии точности. Если оставить пусто, модель оценит по логике задачи.")
        expected_criteria = input("Критерии точности / эталон: ").strip()
        print()

    try:
        direct = call_deepseek(
            api_key,
            make_direct_messages(task),
            max_tokens=answer_max_tokens,
        )
        print_result("1. Прямой ответ без дополнительных инструкций", direct)

        step_by_step = call_deepseek(
            api_key,
            make_step_by_step_messages(task),
            max_tokens=answer_max_tokens,
        )
        print_result("2. Инструкция: решай пошагово", step_by_step)

        prompt_generation = call_deepseek(
            api_key,
            make_prompt_generation_messages(task),
            max_tokens=DEFAULT_META_PROMPT_MAX_TOKENS,
        )
        generated_prompt = prompt_generation["content"].strip()
        print_result("3a. Сначала модель составляет промпт для решения", prompt_generation)

        meta_solution = call_deepseek(
            api_key,
            make_meta_solution_messages(generated_prompt),
            max_tokens=answer_max_tokens,
        )
        print_result("3b. Решение по сгенерированному промпту", meta_solution)

        expert_group = call_deepseek(
            api_key,
            make_expert_group_messages(task),
            max_tokens=answer_max_tokens,
        )
        print_result("4. Группа экспертов: аналитик, инженер, критик", expert_group)

        comparison = call_deepseek(
            api_key,
            make_comparison_messages(
                task=task,
                expected_criteria=expected_criteria,
                direct_answer=direct["content"],
                step_by_step_answer=step_by_step["content"],
                meta_prompt=generated_prompt,
                meta_answer=meta_solution["content"],
                expert_answer=expert_group["content"],
            ),
            max_tokens=comparison_max_tokens,
        )
        print_result("Сравнение способов", comparison)

    except DeepSeekError as error:
        print(f"\nОшибка: {error}\n", file=sys.stderr)
        sys.exit(1)

    report = make_markdown_report(
        task=task,
        expected_criteria=expected_criteria,
        direct=direct,
        step_by_step=step_by_step,
        generated_prompt=generated_prompt,
        meta_solution=meta_solution,
        expert_group=expert_group,
        comparison=comparison,
    )
    report_path = save_report(report)

    print("Краткое сравнение:")
    print("- способ 1 показывает базовое поведение модели без дополнительного контроля;")
    print("- способ 2 проверяет влияние инструкции 'решай пошагово';")
    print("- способ 3 демонстрирует метапромптинг: модель сначала улучшает промпт, затем решает задачу;")
    print("- способ 4 демонстрирует разбор через роли экспертов: аналитик, инженер, критик;")
    print("- финальный блок сравнивает точность и выбирает лучший способ.")
    print(f"\nMarkdown-отчёт сохранён: {report_path}")


if __name__ == "__main__":
    main()

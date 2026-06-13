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
TEMPERATURES = [0, 0.7, 1.2]
DEFAULT_MAX_TOKENS = 1000

SYSTEM_PROMPT = (
    "Ты полезный AI-ассистент. Отвечай на русском языке. "
    "Давай понятный, самодостаточный ответ."
)

DEFAULT_QUESTION = (
    "Предложи архитектуру небольшого сервиса заметок с REST API. "
    "Опиши основные компоненты, хранение данных и обработку ошибок."
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
            # Не перетираем переменные, которые уже заданы в окружении терминала.
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


def parse_max_tokens(raw_value: str) -> int:
    if not raw_value:
        return DEFAULT_MAX_TOKENS

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError("max_tokens должен быть целым числом") from error

    if value <= 0:
        raise ValueError("max_tokens должен быть больше 0")

    return value


def build_messages(question: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]


def build_payload(question: str, *, temperature: float, max_tokens: int) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": build_messages(question),
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }


def call_deepseek(
    api_key: str,
    *,
    question: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    payload = build_payload(
        question,
        temperature=temperature,
        max_tokens=max_tokens,
    )

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
        "temperature": temperature,
        "content": message.get("content", ""),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage", {}),
    }


def make_report(
    *,
    question: str,
    max_tokens: int,
    results: list[dict[str, Any]],
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# День 4. Ответы DeepSeek с разной temperature",
        "",
        f"Дата запуска: {timestamp}",
        f"Модель: `{MODEL}`",
        f"max_tokens: `{max_tokens}`",
        "",
        "## Исходный запрос",
        "",
        question,
        "",
        "## Ответы",
        "",
    ]

    for result in results:
        usage = result.get("usage") or {}
        temperature = result["temperature"]
        content = result["content"].strip()

        lines.extend(
            [
                f"### Temperature = {temperature}",
                "",
                content,
                "",
                "#### Metadata",
                "",
                f"- finish_reason: `{result.get('finish_reason')}`",
                f"- prompt_tokens: `{usage.get('prompt_tokens')}`",
                f"- completion_tokens: `{usage.get('completion_tokens')}`",
                f"- total_tokens: `{usage.get('total_tokens')}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Место для последующего сравнения",
            "",
            "<Сравнить вручную>",
            "",
        ]
    )

    return "\n".join(lines)


def save_report(report: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(__file__).resolve().parent / f"day4_temperature_results_{timestamp}.md"
    output_path.write_text(report, encoding="utf-8")
    return output_path


def main() -> None:
    api_key = require_api_key()

    print("День 4. Запрос с разной temperature")
    print(f"Модель: {MODEL}")
    print(f"Температуры: {', '.join(str(item) for item in TEMPERATURES)}")
    print("Код не сравнивает ответы, а только сохраняет их в Markdown-файл.\n")

    raw_max_tokens = input(f"max_tokens [{DEFAULT_MAX_TOKENS}]: ").strip()
    try:
        max_tokens = parse_max_tokens(raw_max_tokens)
    except ValueError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(1)

    question = input("Вопрос: ").strip()
    if not question:
        question = DEFAULT_QUESTION
        print("Пустой ввод. Использую демо-запрос:")
        print(question)

    results: list[dict[str, Any]] = []

    for temperature in TEMPERATURES:
        print(f"\nОтправляю запрос с temperature = {temperature}...")
        try:
            result = call_deepseek(
                api_key,
                question=question,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except DeepSeekError as error:
            print(f"\nОшибка: {error}\n", file=sys.stderr)
            sys.exit(1)

        print("Ответ:", result["content"].strip())
        results.append(result)
        usage = result.get("usage") or {}
        print(
            "Готово. "
            f"finish_reason={result.get('finish_reason')}, "
            f"completion_tokens={usage.get('completion_tokens')}"
        )

    report = make_report(
        question=question,
        max_tokens=max_tokens,
        results=results,
    )
    output_path = save_report(report)

    print("\nФайл с ответами сохранён:")
    print(output_path)


if __name__ == "__main__":
    main()

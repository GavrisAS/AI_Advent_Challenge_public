import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_env_file(env_path: Path | None = None) -> None:
    """Загружает переменные из .env без внешних зависимостей.

    Формат строк в .env:
        DEEPSEEK_API_KEY=...
        DEEPSEEK_MODEL=...

    Уже заданные переменные окружения не перезаписываются.
    """
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

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

SYSTEM_PROMPT = (
    "Ты полезный AI-ассистент. Отвечай на русском языке, кратко и по делу."
)


def require_api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print(
            "Ошибка: не найдена переменная окружения DEEPSEEK_API_KEY.\n"
            "Добавьте DEEPSEEK_API_KEY в .env рядом со скриптом "
            "или экспортируйте переменную в терминале.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


def call_deepseek(api_key: str, messages: list[dict[str, str]]) -> str:
    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "max_tokens": 1000,
        "thinking": {"type": "disabled"},
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"DeepSeek API вернул ошибку HTTP {error.code}: {error_body}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Не удалось подключиться к DeepSeek API: {error}") from error

    data = json.loads(response_body)
    return data["choices"][0]["message"]["content"]


def print_help() -> None:
    print(
        "Команды:\n"
        "  /help   — показать подсказку\n"
        "  /reset  — очистить историю диалога\n"
        "  /exit   — выйти\n"
    )


def main() -> None:
    api_key = require_api_key()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    print("Интерактивный CLI-чат с DeepSeek")
    print(f"Модель: {MODEL}")
    print("Введите вопрос. Для выхода: /exit. Для подсказки: /help.\n")

    while True:
        try:
            user_text = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not user_text:
            continue

        command = user_text.lower()
        if command in {"/exit", "/quit", "exit", "quit"}:
            print("Выход.")
            break
        if command == "/help":
            print_help()
            continue
        if command == "/reset":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("История диалога очищена.\n")
            continue

        messages.append({"role": "user", "content": user_text})

        try:
            answer = call_deepseek(api_key, messages)
        except RuntimeError as error:
            print(f"\nОшибка: {error}\n", file=sys.stderr)
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": answer})
        print(f"\nDeepSeek: {answer}\n")


if __name__ == "__main__":
    main()

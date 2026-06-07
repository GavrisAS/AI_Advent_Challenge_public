import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
STOP_SEQUENCE = "###END###"

RESPONSE_FORMAT = (
    "Дай ответ строго в таком формате:\n"
    "1. Короткое определение: одно предложение.\n"
    "2. Практическая польза: ровно 3 пункта маркированного списка.\n"
    "3. Мини-пример: один короткий пример."
)

TEXT_LENGTH_LIMIT = (
    "Ограничение на длину ответа:\n"
    "- максимум 150 слов;\n"
    "- без вступления и заключения;\n"
    "- не добавляй разделы сверх указанного формата."
)


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
            # Не перетираем переменные, которые уже заданы в окружении терминала.
            os.environ.setdefault(key, value)


load_env_file()

MODEL = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


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


def ask_max_tokens() -> int | None:
    """Запрашивает max_tokens перед вопросом. Возвращает None, если пользователь хочет выйти."""
    while True:
        raw_value = input("Максимум токенов для ответа: ").strip()

        if raw_value.lower() in {"/exit", "/quit", "exit", "quit"}:
            return None

        try:
            max_tokens = int(raw_value)
        except ValueError:
            print("Введите целое число, например 100. Для выхода: /exit.\n")
            continue

        if max_tokens <= 0:
            print("Значение должно быть больше нуля.\n")
            continue

        return max_tokens


def build_payload(
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    use_stop_sequence: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        # Для задания отключаем reasoning/thinking, чтобы сравнивать только финальные ответы.
        "thinking": {"type": "disabled"},
    }

    if use_stop_sequence:
        if max_tokens is None:
            raise ValueError("max_tokens обязателен для запроса со stop sequence")

        # По условию задания max_tokens используется только в третьем запросе.
        # Stop sequence: когда модель начнет генерировать этот маркер,
        # API остановит вывод. Сам маркер обычно не попадает в content.
        payload["max_tokens"] = max_tokens
        payload["stop"] = [STOP_SEQUENCE]

    return payload


def call_deepseek(
    api_key: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    use_stop_sequence: bool = False,
) -> dict[str, Any]:
    payload = build_payload(
        messages,
        max_tokens=max_tokens,
        use_stop_sequence=use_stop_sequence,
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
        with urllib.request.urlopen(request, timeout=90) as response:
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


def make_messages(
    user_question: str,
    *,
    include_text_length_limit: bool,
    include_stop_instruction: bool,
) -> list[dict[str, str]]:
    prompt_parts = [
        f"Запрос: {user_question}",
        RESPONSE_FORMAT,
    ]

    if include_text_length_limit:
        prompt_parts.append(TEXT_LENGTH_LIMIT)

    if include_stop_instruction:
        prompt_parts.append(
            f"После последнего символа ответа напиши маркер завершения {STOP_SEQUENCE}."
        )

    return [
        {
            "role": "system",
            "content": (
                "Ты полезный AI-ассистент. Отвечай на русском языке. "
                "Строго соблюдай формат, который задан пользователем."
            ),
        },
        {
            "role": "user",
            "content": "\n\n".join(prompt_parts),
        },
    ]


def print_result(
    title: str,
    result: dict[str, Any],
    *,
    print_stop_sequence_after_answer: bool = False,
) -> None:
    usage = result.get("usage") or {}

    print("=" * 80)
    print(title)
    print("=" * 80)
    print(result["content"].strip())

    if print_stop_sequence_after_answer:
        # API stop sequence обычно не возвращает сам маркер в content,
        # поэтому явно выводим его в консоль после третьего ответа для демонстрации.
        print(STOP_SEQUENCE)

    print("\n--- metadata ---")
    print(f"finish_reason: {result.get('finish_reason')}")

    if usage:
        print(f"prompt_tokens: {usage.get('prompt_tokens')}")
        print(f"completion_tokens: {usage.get('completion_tokens')}")
        print(f"total_tokens: {usage.get('total_tokens')}")
    print()


def print_help() -> None:
    print(
        "Команды:\n"
        "  /help   — показать подсказку\n"
        "  /exit   — выйти\n\n"
        "Сценарий одного запуска сравнения:\n"
        "  1) введите максимум токенов;\n"
        "  2) введите вопрос;\n"
        "  3) скрипт отправит один и тот же запрос 3 раза:\n"
        "     - формат ответа;\n"
        "     - формат ответа + текстовое ограничение длины;\n"
        "     - формат ответа + текстовое ограничение длины + stop sequence.\n"
    )


def main() -> None:
    api_key = require_api_key()

    print("День 2. Сравнение уровней контроля ответа")
    print(f"Модель: {MODEL}")
    print(f"Stop sequence: {STOP_SEQUENCE}")
    print("Для выхода: /exit. Для подсказки: /help.\n")

    while True:
        max_tokens = ask_max_tokens()
        if max_tokens is None:
            print("Выход.")
            break

        try:
            user_question = input("Вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not user_question:
            print("Пустой вопрос пропущен.\n")
            continue

        command = user_question.lower()
        if command in {"/exit", "/quit", "exit", "quit"}:
            print("Выход.")
            break
        if command == "/help":
            print_help()
            continue

        try:
            response_with_format = call_deepseek(
                api_key,
                make_messages(
                    user_question,
                    include_text_length_limit=False,
                    include_stop_instruction=False,
                ),
            )
            response_with_format_and_limit = call_deepseek(
                api_key,
                make_messages(
                    user_question,
                    include_text_length_limit=True,
                    include_stop_instruction=False,
                ),
            )
            response_with_format_limit_and_stop = call_deepseek(
                api_key,
                make_messages(
                    user_question,
                    include_text_length_limit=True,
                    include_stop_instruction=True,
                ),
                max_tokens=max_tokens,
                use_stop_sequence=True,
            )
        except DeepSeekError as error:
            print(f"\nОшибка: {error}\n", file=sys.stderr)
            continue

        print_result(
            "Ответ 1: формат ответа",
            response_with_format,
        )
        print_result(
            "Ответ 2: формат ответа + текстовое ограничение длины",
            response_with_format_and_limit,
        )
        print_result(
            "Ответ 3: формат ответа + текстовое ограничение длины + stop sequence",
            response_with_format_limit_and_stop,
            print_stop_sequence_after_answer=True,
        )

        print(
            "Краткое описание:\n"
            "- во всех трех запросах задан один и тот же формат ответа;\n"
            "- во втором запросе добавлено текстовое ограничение длины;\n"
            "- в третьем запросе добавлен stop sequence;\n"
            "- max_tokens задается пользователем перед вопросом, но применяется только в третьем API-вызове;\n"
            "- после третьего ответа stop token выводится явно, потому что API обычно не возвращает его в content.\n"
        )


if __name__ == "__main__":
    main()

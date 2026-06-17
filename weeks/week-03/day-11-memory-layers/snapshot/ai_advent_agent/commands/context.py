"""Shared command presentation helpers."""

from __future__ import annotations

from pathlib import Path

from ai_advent_agent.agent import AgentResponse, SimpleAgent
from ai_advent_agent.llm_client import Message
from ai_advent_agent.token_report import TokenReport


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_optional_number(value: int | None) -> str:
    return "-" if value is None else format_number(value)


def print_config(agent: SimpleAgent) -> None:
    config = agent.config
    print(
        "Текущая конфигурация:\n"
        f"  model: {config.model}\n"
        f"  strategy: {config.strategy}\n"
        f"  temperature: {config.temperature}\n"
        f"  max_tokens: {config.max_tokens}\n"
        f"  thinking: {config.thinking_type}\n"
        f"  reasoning_effort: {config.reasoning_effort or '-'}\n"
        f"  context_window_tokens: {format_number(config.context_window_tokens)}\n"
        f"  warn_context_ratio: {config.warn_context_ratio:.2f}\n"
        f"  overflow_policy: {config.overflow_policy.value}\n"
        f"  context_strategy: {config.context_strategy}\n"
        f"  summary_mode: {config.summary_mode}\n"
        f"  recent_messages_limit: {config.recent_messages_limit}\n"
        f"  summarize_every_messages: {config.summarize_every_messages}\n"
        f"  summary_max_tokens: {config.summary_max_tokens}\n"
        f"  input_price_per_1m_tokens: {config.input_price_per_1m_tokens}\n"
        f"  output_price_per_1m_tokens: {config.output_price_per_1m_tokens}\n"
        f"  context_file: {agent.context_path or 'disabled'}\n"
        f"  facts_file: {agent.facts_path or 'disabled'}\n"
        f"  branches_file: {agent.branches_path or 'disabled'}\n"
        f"  summary_file: {agent.summary_path or 'disabled'}\n"
        f"  short_term_memory_file: {agent.short_term_memory_path or 'disabled'}\n"
        f"  working_memory_file: {agent.working_memory_path or 'disabled'}\n"
        f"  long_term_memory_file: {agent.long_term_memory_path or 'disabled'}\n"
        f"  memory_events_file: {agent.memory_events_path or 'disabled'}\n"
        f"  token_report_file: {agent.token_report_path or 'disabled'}\n"
    )


def print_metadata(response: AgentResponse) -> None:
    usage = response.usage or {}
    print(
        "\n--- metadata ---\n"
        f"model: {response.model}\n"
        f"strategy: {response.strategy}\n"
        f"finish_reason: {response.finish_reason}\n"
        f"elapsed_seconds: {response.elapsed_seconds:.2f}\n"
        f"message_count: {response.message_count}\n"
        f"summary_active: {response.summary_active}\n"
        f"context_saved: {response.context_saved}\n"
        f"context_path: {response.context_path or '-'}\n"
        f"prompt_tokens_actual: {usage.get('prompt_tokens', '-')}\n"
        f"completion_tokens_actual: {usage.get('completion_tokens', '-')}\n"
        f"total_tokens_actual: {usage.get('total_tokens', '-')}"
    )
    print_token_report(response.token_report)


def print_token_report(report: TokenReport) -> None:
    print(
        "\n--- token report ---\n"
        f"request_tokens_estimated: {format_number(report.request_tokens_estimated)}\n"
        "history_tokens_before_estimated: "
        f"{format_number(report.history_tokens_before_estimated)}\n"
        f"prompt_tokens_estimated: {format_number(report.prompt_tokens_estimated)}\n"
        f"projected_total_tokens_estimated: "
        f"{format_number(report.projected_total_tokens_estimated)}\n"
        f"context_window_tokens: {format_number(report.context_window_tokens)}\n"
        f"context_usage: {report.context_usage_percent:.2f}%\n"
        f"projected_usage: {report.projected_usage_percent:.2f}%\n"
        f"warning: {report.warn_threshold_reached}\n"
        f"overflow_detected: {report.overflow_detected}\n"
        f"overflow_policy: {report.overflow_policy}\n"
        f"trimmed_messages_count: {report.trimmed_messages_count}\n"
        f"summary_active: {report.summary_active}\n"
        f"summary_tokens_estimated: {format_number(report.summary_tokens_estimated)}\n"
        f"summarized_messages_count: {format_number(report.summarized_messages_count)}"
    )
    if report.memory_layers_active:
        print(
            "memory_layers_active: true\n"
            f"memory_layer_entries: {report.memory_layer_entries}\n"
            f"memory_layer_tokens_estimated: {report.memory_layer_tokens_estimated}\n"
            "memory_prompt_tokens_estimated: "
            f"{format_number(report.memory_prompt_tokens_estimated)}\n"
            f"prompt_assembly_order: {', '.join(report.prompt_assembly_order)}"
        )
    if report.response_tokens_estimated is not None:
        print(f"response_tokens_estimated: {format_number(report.response_tokens_estimated)}")
    if report.history_tokens_after_response_estimated is not None:
        print(
            "history_tokens_after_response_estimated: "
            f"{format_number(report.history_tokens_after_response_estimated)}"
        )
    print(
        f"prompt_tokens_actual: {format_optional_number(report.prompt_tokens_actual)}\n"
        f"completion_tokens_actual: {format_optional_number(report.completion_tokens_actual)}\n"
        f"total_tokens_actual: {format_optional_number(report.total_tokens_actual)}"
    )
    if report.estimated_total_cost_usd is not None:
        print(
            "estimated_cost_usd: "
            f"input={report.estimated_input_cost_usd:.8f}, "
            f"output={report.estimated_output_cost_usd:.8f}, "
            f"total={report.estimated_total_cost_usd:.8f}"
        )
    if report.elapsed_seconds is not None:
        print(f"elapsed_seconds: {report.elapsed_seconds:.2f}")


def print_token_breakdown(agent: SimpleAgent) -> None:
    breakdown = agent.get_token_breakdown()
    config = agent.config
    ratio = breakdown.total / config.context_window_tokens
    projected_ratio = (breakdown.total + config.max_tokens) / config.context_window_tokens
    print(
        "Token breakdown текущей истории:\n"
        f"  messages: {breakdown.message_count}\n"
        f"  total_estimated: {format_number(breakdown.total)}\n"
        f"  system: {format_number(breakdown.system)}\n"
        f"  user: {format_number(breakdown.user)}\n"
        f"  assistant: {format_number(breakdown.assistant)}\n"
        f"  tool: {format_number(breakdown.tool)}\n"
        f"  context_window_tokens: {format_number(config.context_window_tokens)}\n"
        f"  current_context_usage: {ratio * 100:.2f}%\n"
        f"  projected_with_max_tokens: {projected_ratio * 100:.2f}%\n"
    )


def print_history_summary(messages: list[Message]) -> None:
    role_counts: dict[str, int] = {}
    for message in messages:
        role = message.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
    print(f"Сообщений в истории: {len(messages)}")
    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")
    print()


def print_history_full(messages: list[Message]) -> None:
    for index, message in enumerate(messages, start=1):
        content = message.get("content", "")
        print(f"[{index}] {message.get('role', 'unknown')}\n{content}\n")


def print_memory_summary(agent: SimpleAgent) -> None:
    short_notes = agent.short_term_memory.normalized_notes()
    recent_messages = agent.short_term_memory.recent_messages
    working = agent.working_memory.normalized()
    long_term = agent.long_term_memory.normalized()
    print("Memory layers:")
    print(
        f"  short-term: notes={len(short_notes)}, "
        f"recent_messages={len(recent_messages)}, file={agent.short_term_memory_path or 'disabled'}"
    )
    print(f"  working: entries={len(working)}, file={agent.working_memory_path or 'disabled'}")
    print(
        f"  long-term: entries={len(long_term)}, file={agent.long_term_memory_path or 'disabled'}"
    )
    print(f"  events: {agent.memory_events_path or 'disabled'}\n")


def print_memory_layer(agent: SimpleAgent, layer: str) -> None:
    if layer == "short":
        notes = agent.short_term_memory.normalized_notes()
        recent_messages = agent.short_term_memory.recent_messages
        print("Short-term memory:")
        if not notes and not recent_messages:
            print("  пусто\n")
            return
        if notes:
            print("  Явные notes:")
            for note in notes:
                print(f"    - {note}")
        if recent_messages:
            print("  Последние сообщения:")
            for message in recent_messages:
                print(f"    - {message['role']}: {message['content']}")
        print()
        return
    if layer == "working":
        print_key_value_memory("Working memory", agent.working_memory.normalized())
        return
    if layer == "long":
        print_key_value_memory("Long-term memory", agent.long_term_memory.normalized())
        return
    raise ValueError("memory layer должен быть short, working или long")


def print_key_value_memory(title: str, entries: dict[str, str]) -> None:
    print(f"{title}:")
    if not entries:
        print("  пусто\n")
        return
    for key, value in entries.items():
        print(f"  {key}: {value}")
    print()


def extract_path_argument(argument: str) -> Path | None:
    cleaned = argument.strip()
    if not cleaned:
        return None
    return Path(cleaned.strip('"').strip("'"))


def analyze_file(path: Path, agent: SimpleAgent) -> None:
    text = path.expanduser().read_text(encoding="utf-8")
    report = agent.build_file_token_report(text)
    print(f"Файл: {path}")
    print(f"Размер: {format_number(len(text))} символов")
    print_token_report(report)
    print("\nDry-run: содержимое файла не отправлялось в API и не сохранялось в history.\n")


def ask_file(path: Path, agent: SimpleAgent, *, show_metadata: bool) -> None:
    text = path.expanduser().read_text(encoding="utf-8")
    print(
        f"Файл {path} будет отправлен в модель как одно user message "
        f"({format_number(agent.estimate_text_tokens(text))} estimated tokens)."
    )
    response = agent.ask(text)
    print(f"\nAgent:\n{response.content.strip()}")
    if show_metadata:
        print_metadata(response)
    print()

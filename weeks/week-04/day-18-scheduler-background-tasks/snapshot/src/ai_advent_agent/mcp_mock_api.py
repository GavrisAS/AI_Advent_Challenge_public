"""Deterministic mock Tracker API backend for Day 17."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class TrackerCommentPayload(TypedDict):
    author: str
    text: str


class TrackerIssuePayload(TypedDict):
    issue_key: str
    title: str
    status: str
    assignee: str
    priority: str
    summary: str
    comments: list[TrackerCommentPayload]


@dataclass(frozen=True, slots=True)
class TrackerComment:
    author: str
    text: str

    def to_dict(self) -> TrackerCommentPayload:
        return {"author": self.author, "text": self.text}


@dataclass(frozen=True, slots=True)
class TrackerIssue:
    issue_key: str
    title: str
    status: str
    assignee: str
    priority: str
    summary: str
    comments: tuple[TrackerComment, ...] = ()

    def to_dict(self, *, include_comments: bool = False) -> TrackerIssuePayload:
        return {
            "issue_key": self.issue_key,
            "title": self.title,
            "status": self.status,
            "assignee": self.assignee,
            "priority": self.priority,
            "summary": self.summary,
            "comments": [comment.to_dict() for comment in self.comments]
            if include_comments
            else [],
        }


class UnknownTrackerIssueError(KeyError):
    """Raised when the mock Tracker API does not know the requested issue."""


MOCK_TRACKER_ISSUES: dict[str, TrackerIssue] = {
    "AI-16": TrackerIssue(
        issue_key="AI-16",
        title="Подключить MCP discovery",
        status="done",
        assignee="student",
        priority="medium",
        summary=(
            "Подключить публичный DeepWiki MCP server, выполнить initialization и получить "
            "список tools без вызова инструментов."
        ),
        comments=(
            TrackerComment(
                author="mentor",
                text="Day 16 должен оставаться только discovery-сценарием без tools/call.",
            ),
        ),
    ),
    "AI-17": TrackerIssue(
        issue_key="AI-17",
        title="Подключить первый MCP tool",
        status="done",
        assignee="student",
        priority="high",
        summary=(
            "Реализовать локальный stdio MCP server поверх mock Tracker API и вызвать его "
            "из агента."
        ),
        comments=(
            TrackerComment(
                author="mentor",
                text=(
                    "Сфокусироваться на registration, input schema и call_tool без реального "
                    "внешнего API."
                ),
            ),
            TrackerComment(
                author="student",
                text="Использовать read-only tool и сохранить воспроизводимые artifacts.",
            ),
        ),
    ),
    "AI-18": TrackerIssue(
        issue_key="AI-18",
        title="Расширить MCP orchestration",
        status="done",
        assignee="student",
        priority="medium",
        summary=(
            "Следующим шагом проверить более сложный MCP workflow после первого локального "
            "tool call."
        ),
        comments=(
            TrackerComment(
                author="mentor",
                text=(
                    "Не усложнять Day 17 несколькими tools: расширение оставить на следующий день."
                ),
            ),
        ),
    ),
}


def normalize_issue_key(issue_key: str) -> str:
    """Normalize a tracker issue key to the mock API canonical form."""

    normalized = issue_key.strip().upper()
    if not normalized:
        raise ValueError("issue_key must not be empty")
    return normalized


def get_issue(issue_key: str, *, include_comments: bool = False) -> TrackerIssuePayload:
    """Return a deterministic mock tracker issue payload by key."""

    normalized_key = normalize_issue_key(issue_key)
    issue = MOCK_TRACKER_ISSUES.get(normalized_key)
    if issue is None:
        known = ", ".join(sorted(MOCK_TRACKER_ISSUES))
        raise UnknownTrackerIssueError(
            f"Unknown mock tracker issue: {normalized_key}. Known issues: {known}"
        )
    return issue.to_dict(include_comments=include_comments)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TaskPlanItem:
    title: str
    priority: int
    objective: str
    brief: str = ""
    deliverable: str = ""
    done_when: str = ""


@dataclass(slots=True)
class TaskRecord:
    id: str
    title: str
    priority: int
    objective: str
    status: str = "pending"
    created: str | None = None


@dataclass(slots=True)
class ObjectiveRecord:
    id: str
    title: str
    status: str = "pending"
    created: str | None = None
    final_report_url: str = ""


@dataclass(slots=True)
class ResultRecord:
    id: str
    title: str
    task_id: str
    output: str
    agent: str
    status: str = "pending_review"
    review_score: int | None = None
    review_summary: str = ""


@dataclass(slots=True)
class WorkerExecution:
    summary: str
    output_markdown: str
    assumptions: list[str]
    next_action: str
    confidence: str


@dataclass(slots=True)
class ReviewDecision:
    status: str
    justification: str
    score: int
    strengths: list[str]
    risks: list[str]
    final_summary: str


@dataclass(slots=True)
class AgentDescriptor:
    name: str
    agent_type: str
    model: str
    status: str = "active"


@dataclass(slots=True)
class FinalReportRecord:
    id: str
    title: str
    objective: str
    summary: str
    score: float | None = None
    status: str = "published"
    url: str = ""

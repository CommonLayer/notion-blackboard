from __future__ import annotations

from models import TaskRecord


class ManagerAgent:
    def __init__(self, name: str, model: str, llm_client, notion_client) -> None:
        self.name = name
        self.model = model
        self.llm_client = llm_client
        self.notion_client = notion_client

    def run(self, objective: str) -> list[TaskRecord]:
        planned_tasks = self.llm_client.plan_tasks(self.model, objective)
        created_tasks: list[TaskRecord] = []
        for task in planned_tasks:
            created_tasks.append(
                self.notion_client.create_task(
                    title=task.title,
                    priority=task.priority,
                    objective=self._compose_task_context(task),
                )
            )
        self.notion_client.create_audit_log(
            action="created",
            agent=self.name,
            details=f"Objective split into {len(created_tasks)} tasks: {objective}",
        )
        return created_tasks

    @staticmethod
    def _compose_task_context(task) -> str:
        sections = [f"Parent objective: {task.objective}"]
        if task.brief:
            sections.append(f"Task brief: {task.brief}")
        if task.deliverable:
            sections.append(f"Expected deliverable: {task.deliverable}")
        if task.done_when:
            sections.append(f"Done when: {task.done_when}")
        return "\n".join(sections)

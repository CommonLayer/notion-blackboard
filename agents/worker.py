from __future__ import annotations

from models import ResultRecord, TaskRecord


class WorkerAgent:
    def __init__(self, name: str, model: str, llm_client, notion_client) -> None:
        self.name = name
        self.model = model
        self.llm_client = llm_client
        self.notion_client = notion_client

    def run(self, tasks: list[TaskRecord] | None = None) -> list[ResultRecord]:
        tasks = tasks or self.notion_client.get_pending_tasks()
        produced_results: list[ResultRecord] = []
        for task in tasks:
            self.notion_client.update_task_status(task.id, "in_progress")
            try:
                execution = self.llm_client.execute_task(self.model, task)
                result = self.notion_client.create_result(
                    title=f"Result - {task.title}",
                    task_id=task.id,
                    output=execution.summary,
                    agent=self.name,
                    body_markdown=execution.output_markdown,
                )
                self.notion_client.update_task_status(task.id, "done")
                assumptions_text = (
                    "; ".join(execution.assumptions) if execution.assumptions else "No explicit assumptions."
                )
                self.notion_client.create_audit_log(
                    action="updated",
                    agent=self.name,
                    details=(
                        f"Completed task '{task.title}' and stored result '{result.title}'. "
                        f"Summary: {execution.summary} "
                        f"Confidence: {execution.confidence}. "
                        f"Next action: {execution.next_action}. "
                        f"Assumptions: {assumptions_text}"
                    ),
                )
                produced_results.append(result)
            except Exception as exc:
                self.notion_client.update_task_status(task.id, "rejected")
                self.notion_client.create_audit_log(
                    action="rejected",
                    agent=self.name,
                    details=f"Task '{task.title}' failed with error: {exc}",
                )
                raise
        return produced_results

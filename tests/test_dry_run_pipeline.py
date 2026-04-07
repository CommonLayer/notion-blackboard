import unittest

from agents import BlackboardLLMClient, ManagerAgent, ReviewerAgent, WorkerAgent
from notion import NotionMCPClient


class DryRunPipelineTest(unittest.TestCase):
    def test_dry_run_pipeline(self) -> None:
        notion_client = NotionMCPClient(
            notion_token=None,
            objectives_db=None,
            task_queue_db=None,
            agent_registry_db=None,
            results_db=None,
            audit_log_db=None,
            final_reports_db=None,
            dry_run=True,
        )
        llm_client = BlackboardLLMClient(
            api_key=None,
            base_url="https://openrouter.ai/api/v1",
            dry_run=True,
        )

        manager = ManagerAgent("manager", "mock-manager", llm_client, notion_client)
        worker = WorkerAgent("worker", "mock-worker", llm_client, notion_client)
        reviewer = ReviewerAgent("reviewer", "mock-reviewer", llm_client, notion_client)

        tasks = manager.run("Preparer une synthese sur les LLMs open source")
        extra_task = notion_client.create_task(
            title="Extra pending task",
            priority=99,
            objective="Parent objective: ignore this task",
        )

        results = worker.run(tasks)
        extra_result = notion_client.create_result(
            title="Result - Extra pending task",
            task_id=extra_task.id,
            output="Should remain pending review.",
            agent="worker",
            body_markdown="# Extra pending task\n\n## Deliverable\nShould remain pending review.",
        )
        reviewed = reviewer.run(results)

        self.assertEqual(len(tasks), 3)
        self.assertEqual(len(results), 3)
        self.assertEqual(len(reviewed), 3)
        self.assertTrue(all(result.status == "approved" for result in reviewed))
        self.assertTrue(all("Parent objective:" in task.objective for task in tasks))
        self.assertTrue(all("## Deliverable" in result.output for result in results))
        self.assertTrue(all(result.review_score is not None for result in reviewed))
        self.assertTrue(all(result.review_summary for result in reviewed))
        self.assertEqual(notion_client.get_task(extra_task.id).status, "pending")
        self.assertEqual(
            [result.id for result in notion_client.get_pending_results()],
            [extra_result.id],
        )


if __name__ == "__main__":
    unittest.main()

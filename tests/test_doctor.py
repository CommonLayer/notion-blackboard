import unittest

from notion import NotionMCPClient
from notion.doctor import run_notion_doctor


class NotionDoctorTest(unittest.TestCase):
    def test_doctor_passes_in_dry_run(self) -> None:
        client = NotionMCPClient(
            notion_token=None,
            objectives_db="objectives-db",
            task_queue_db="task-db",
            agent_registry_db="agent-db",
            results_db="results-db",
            audit_log_db="audit-db",
            final_reports_db="final-reports-db",
            dry_run=True,
        )

        healthy, lines = run_notion_doctor(client)

        self.assertTrue(healthy)
        self.assertTrue(any(line.startswith("PASS  Task Queue") for line in lines))
        self.assertTrue(any("relation property 'Task' points to Task Queue" in line for line in lines))


if __name__ == "__main__":
    unittest.main()

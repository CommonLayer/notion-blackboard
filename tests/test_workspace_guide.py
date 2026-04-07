import unittest

from workspace_guide import build_workspace_guide_markdown, build_workspace_home_markdown


class WorkspaceGuideTest(unittest.TestCase):
    def test_workspace_guide_highlights_objectives_and_final_reports(self) -> None:
        markdown = build_workspace_guide_markdown(
            objectives_url="https://www.notion.so/objectives",
            final_reports_url="https://www.notion.so/final-reports",
            task_queue_url="https://www.notion.so/task-queue",
            results_url="https://www.notion.so/results",
            audit_log_url="https://www.notion.so/audit-log",
            agent_registry_url="https://www.notion.so/agent-registry",
            latest_final_report_title="Final Report - Demo",
            latest_final_report_url="https://www.notion.so/final-report-demo",
        )

        self.assertIn("# Start Here", markdown)
        self.assertIn("[Objectives](https://www.notion.so/objectives)", markdown)
        self.assertIn("[Final Reports](https://www.notion.so/final-reports)", markdown)
        self.assertIn("python3 main.py --process-objectives", markdown)
        self.assertIn("Objectives in, final reports out", markdown)
        self.assertIn("[Final Report - Demo](https://www.notion.so/final-report-demo)", markdown)

    def test_workspace_home_highlights_root_navigation(self) -> None:
        markdown = build_workspace_home_markdown(
            start_here_url="https://www.notion.so/start-here",
            objectives_url="https://www.notion.so/objectives",
            final_reports_url="https://www.notion.so/final-reports",
            task_queue_url="https://www.notion.so/task-queue",
            results_url="https://www.notion.so/results",
            audit_log_url="https://www.notion.so/audit-log",
            agent_registry_url="https://www.notion.so/agent-registry",
            latest_final_report_title="Final Report - Demo",
            latest_final_report_url="https://www.notion.so/final-report-demo",
        )

        self.assertIn("main landing page for the demo", markdown)
        self.assertIn("[Start Here](https://www.notion.so/start-here)", markdown)
        self.assertIn("[Objectives](https://www.notion.so/objectives)", markdown)
        self.assertIn("[Final Reports](https://www.notion.so/final-reports)", markdown)
        self.assertIn("## Back Office", markdown)
        self.assertIn("[Final Report - Demo](https://www.notion.so/final-report-demo)", markdown)


if __name__ == "__main__":
    unittest.main()

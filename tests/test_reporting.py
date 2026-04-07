import tempfile
import unittest
from pathlib import Path

from models import ResultRecord, TaskRecord
from reporting import build_final_deliverable_markdown, build_final_deliverable_title, write_run_artifacts


class ReportingTest(unittest.TestCase):
    def test_write_run_artifacts_generates_report_and_submission(self) -> None:
        tasks = [
            TaskRecord(
                id="task-1",
                title="Scope the objective",
                priority=1,
                objective="Parent objective: Prepare a competitive report\nTask brief: define scope",
                status="done",
            )
        ]
        results = [
            ResultRecord(
                id="result-1",
                title="Result - Scope the objective",
                task_id="task-1",
                output="# Scope the objective\n\n## Deliverable\nA concise scoped note.",
                agent="worker",
                status="approved",
                review_score=91,
                review_summary="Clear and complete.",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_run_artifacts(
                objective="Prepare a competitive report",
                mode="dry-run",
                tasks=tasks,
                results=results,
                reviewed_results=results,
                final_deliverable_markdown=(
                    "# Prepare a competitive report\n\n"
                    "## Executive Summary\n\n"
                    "A short synthetic report.\n\n"
                    "## Conclusion\n\n"
                    "Use this as the final deliverable."
                ),
                docs_dir=tmpdir,
            )

            report_text = Path(paths["report"]).read_text(encoding="utf-8")
            final_deliverable_text = Path(paths["final_deliverable"]).read_text(encoding="utf-8")
            submission_text = Path(paths["submission"]).read_text(encoding="utf-8")

            self.assertIn("Latest Run Report", report_text)
            self.assertIn("Prepare a competitive report", report_text)
            self.assertIn("Average review score: 91.0", report_text)
            self.assertIn("## Executive Summary", final_deliverable_text)
            self.assertIn("Use this as the final deliverable.", final_deliverable_text)
            self.assertIn("I Built a Multi-Agent Workflow", submission_text)
            self.assertIn("github.com/CommonLayer/notion-blackboard", submission_text)
            self.assertIn("## The Idea", submission_text)
            self.assertNotIn("TODO", submission_text)

            write_run_artifacts(
                objective="Prepare a refreshed competitive report",
                mode="live",
                tasks=tasks,
                results=results,
                reviewed_results=results,
                final_deliverable_markdown=(
                    "# Prepare a refreshed competitive report\n\n"
                    "## Executive Summary\n\n"
                    "An updated synthetic report.\n\n"
                    "## Conclusion\n\n"
                    "Updated."
                ),
                docs_dir=tmpdir,
            )

            updated_submission = Path(paths["submission"]).read_text(encoding="utf-8")
            self.assertIn("I Built a Multi-Agent Workflow", updated_submission)
            self.assertIn("github.com/CommonLayer/notion-blackboard", updated_submission)
            self.assertNotIn("TODO", updated_submission)

    def test_final_deliverable_helpers(self) -> None:
        reviewed_results = [
            ResultRecord(
                id="result-1",
                title="Result - Scope the objective",
                task_id="task-1",
                output="# Scope the objective\n\n## Deliverable\nA concise scoped note.",
                agent="worker",
                status="approved",
                review_score=91,
                review_summary="Clear and complete.",
            )
        ]

        title = build_final_deliverable_title("Prepare a competitive report")
        markdown = build_final_deliverable_markdown(
            "Prepare a competitive report",
            reviewed_results,
            "live",
        )

        self.assertEqual(title, "Final Report - Prepare a competitive report")
        self.assertIn("This document is the final deliverable", markdown)
        self.assertIn("**Scope the objective**: Clear and complete.", markdown)
        self.assertIn("## Scope the objective", markdown)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from models import ResultRecord, TaskRecord


WHAT_I_BUILT_START = "<!-- AUTOGEN:WHAT_I_BUILT:START -->"
WHAT_I_BUILT_END = "<!-- AUTOGEN:WHAT_I_BUILT:END -->"
HOW_I_USED_START = "<!-- AUTOGEN:HOW_I_USED_NOTION_MCP:START -->"
HOW_I_USED_END = "<!-- AUTOGEN:HOW_I_USED_NOTION_MCP:END -->"
REPO_URL = "https://github.com/CommonLayer/notion-blackboard"


def write_run_artifacts(
    objective: str,
    mode: str,
    tasks: list[TaskRecord],
    results: list[ResultRecord],
    reviewed_results: list[ResultRecord],
    final_deliverable_markdown: str | None = None,
    docs_dir: str | Path = "docs",
) -> dict[str, Path]:
    docs_path = Path(docs_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    report_path = docs_path / "latest_run_report.md"
    report_path.write_text(
        build_run_report(objective, mode, tasks, results, reviewed_results),
        encoding="utf-8",
    )

    final_deliverable_path = docs_path / "latest_final_deliverable.md"
    final_deliverable_path.write_text(
        final_deliverable_markdown or build_final_deliverable_markdown(objective, reviewed_results, mode),
        encoding="utf-8",
    )

    submission_path = docs_path / "submission.md"
    existing_submission = submission_path.read_text(encoding="utf-8") if submission_path.exists() else None
    submission_path.write_text(
        build_submission_draft(
            objective=objective,
            mode=mode,
            tasks=tasks,
            results=results,
            reviewed_results=reviewed_results,
            existing_content=existing_submission,
        ),
        encoding="utf-8",
    )

    return {
        "report": report_path,
        "submission": submission_path,
        "final_deliverable": final_deliverable_path,
    }


def build_run_report(
    objective: str,
    mode: str,
    tasks: list[TaskRecord],
    results: list[ResultRecord],
    reviewed_results: list[ResultRecord],
) -> str:
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    approved = sum(1 for result in reviewed_results if result.status == "approved")
    rejected = sum(1 for result in reviewed_results if result.status == "rejected")
    average_score = _average_review_score(reviewed_results)

    lines = [
        "# Latest Run Report",
        "",
        f"- Generated at: {generated_at}",
        f"- Mode: {mode}",
        f"- Objective: {objective}",
        f"- Tasks created: {len(tasks)}",
        f"- Results produced: {len(results)}",
        f"- Approved results: {approved}",
        f"- Rejected results: {rejected}",
    ]
    if average_score is not None:
        lines.append(f"- Average review score: {average_score}")

    lines.extend(
        [
            "",
            "## Task Queue Snapshot",
            "",
        ]
    )
    for task in tasks:
        lines.extend(
            [
                f"### P{task.priority} - {task.title}",
                "",
                f"- Status: {task.status}",
                "- Context:",
                "",
                "```text",
                task.objective,
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## Reviewed Results",
            "",
        ]
    )
    for result in reviewed_results:
        lines.extend(
            [
                f"### {result.title}",
                "",
                f"- Status: {result.status}",
                f"- Review score: {result.review_score if result.review_score is not None else 'n/a'}",
                f"- Review summary: {result.review_summary or 'No review summary available.'}",
                "",
                result.output.strip(),
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def build_submission_draft(
    objective: str,
    mode: str,
    tasks: list[TaskRecord],
    results: list[ResultRecord],
    reviewed_results: list[ResultRecord],
    existing_content: str | None = None,
) -> str:
    return "\n".join(
        [
            "---",
            "title: I Built a Multi-Agent Workflow Where Notion Is the Shared Brain",
            "published: false",
            "tags: ai, notion, mcp, python",
            "---",
            "",
            'I wanted to build something slightly different from the usual "AI writes a page in Notion" demo.',
            "",
            "That pattern is useful, but it is not very interesting after the first five minutes. You send a prompt, the model writes text, the text lands somewhere. Fine.",
            "",
            "For this project, I wanted Notion to be more than the destination.",
            "",
            "I wanted Notion to be the place where the agents coordinate.",
            "",
            "So I built **Notion Blackboard**.",
            "",
            f"GitHub repo: [github.com/CommonLayer/notion-blackboard]({REPO_URL})",
            "",
            "## The Idea",
            "",
            "The concept is simple:",
            "",
            "> Objectives in, final reports out. The rest is the engine room.",
            "",
            "You add an objective in Notion, then a small multi-agent pipeline takes over:",
            "",
            "- a manager agent breaks the objective into tasks",
            "- a worker agent produces intermediate notes",
            "- a reviewer agent validates the outputs",
            "- the system publishes one clean final report back into Notion",
            "",
            "The interesting part is that the agents do not need to talk directly to each other.",
            "",
            "They coordinate through Notion.",
            "",
            "## The Notion Workspace",
            "",
            "The workspace is split into two layers.",
            "",
            "The user-facing layer:",
            "",
            "- `Start Here`",
            "- `Objectives`",
            "- `Final Reports`",
            "",
            "The internal layer:",
            "",
            "- `Task Queue`",
            "- `Results`",
            "- `Audit Log`",
            "- `Agent Registry`",
            "",
            "That split matters. At first, I had all the internal tables visible and it felt messy. It technically worked, but it looked like a machine with all the wires exposed.",
            "",
            "The cleaner version is much easier to understand:",
            "",
            "1. write the objective in `Objectives`",
            "2. run the pipeline",
            "3. read the finished output in `Final Reports`",
            "",
            "If you want to inspect the process, the back-office tables are still there.",
            "",
            "## How the Pipeline Works",
            "",
            "Here is the flow:",
            "",
            "```text",
            "Human",
            "  |",
            "  v",
            "Objectives (Notion)",
            "  |",
            "  v",
            "Manager agent -> Task Queue",
            "  |",
            "  v",
            "Worker agent -> Results",
            "  |",
            "  v",
            "Reviewer agent -> Audit Log",
            "  |",
            "  v",
            "Final Reports (Notion)",
            "```",
            "",
            "The manager creates the work plan.",
            "",
            "The worker executes the tasks.",
            "",
            "The reviewer validates what was produced.",
            "",
            "The final report is the only thing the user really needs to read.",
            "",
            "## Why Notion Works Well Here",
            "",
            "Notion is not just acting as a database in this project.",
            "",
            "It gives the system a few useful properties:",
            "",
            "- the state is visible",
            "- the intermediate work is inspectable",
            "- a human can intervene manually if needed",
            "- the final output stays in a tool people already use",
            "- the audit trail is not hidden in a terminal log",
            "",
            "That is the part I find interesting.",
            "",
            "The agents are not magical. They are just reading and writing structured state. Notion makes that state understandable to a human.",
            "",
            "## What I Built Around It",
            "",
            "The repo includes:",
            "",
            "- a CLI entrypoint in Python",
            "- a Notion API client",
            "- manager / worker / reviewer agents",
            "- OpenRouter / OpenAI-compatible model support",
            "- a bootstrap command to create the Notion databases",
            "- a doctor command to validate the workspace schema",
            "- Markdown-to-Notion block rendering",
            "- local report artifacts in `docs/`",
            "- unit tests",
            "- a MIT license",
            "",
            "Some useful commands:",
            "",
            "```bash",
            "python3 main.py --bootstrap --parent-page-id <NOTION_PARENT_PAGE_ID>",
            "python3 main.py --doctor",
            "python3 main.py --publish-guide",
            "python3 main.py --process-objectives",
            "```",
            "",
            "There is also a dry-run mode:",
            "",
            "```bash",
            'python3 main.py "Prepare a competitive research brief" --dry-run',
            "```",
            "",
            "## What I Would Improve Next",
            "",
            "This is still a prototype, not a polished hosted app.",
            "",
            "The next obvious steps would be:",
            "",
            "- a lightweight web UI for running the pipeline without the terminal",
            "- better per-run grouping inside Notion",
            "- richer reviewer scoring and retry loops",
            "- cleaner final-report templates",
            "- optional source citation and web research support",
            "",
            "But I like the shape of it already because the core pattern is clear:",
            "",
            "> Notion can be the shared workspace between humans and agents, not just the place where outputs are stored.",
            "",
            "## Repo",
            "",
            "The code is here:",
            "",
            f"[github.com/CommonLayer/notion-blackboard]({REPO_URL})",
            "",
            "If you are interested in agent workflows, Notion automations, or MCP-style coordination patterns, this is a small project to explore and modify.",
            "",
        ]
    )


def build_final_deliverable_title(objective: str) -> str:
    compact = objective.strip().rstrip(".")
    if len(compact) <= 90:
        return f"Final Report - {compact}"
    return f"Final Report - {compact[:87].rstrip()}..."


def build_final_deliverable_markdown(
    objective: str,
    reviewed_results: list[ResultRecord],
    mode: str,
) -> str:
    approved_results = [result for result in reviewed_results if result.status == "approved"]
    average_score = _average_review_score(approved_results)

    lines = [
        f"# {objective}",
        "",
        "## Executive Summary",
        "",
        (
            f"This document is the final deliverable generated by the Notion Blackboard pipeline in `{mode}` mode. "
            f"It consolidates {len(approved_results)} approved analysis sections into one human-readable report."
        ),
    ]
    if average_score is not None:
        lines.append(f"The approved sections reached an average reviewer score of **{average_score}**.")

    lines.extend(
        [
            "",
            "## Key Takeaways",
            "",
        ]
    )
    if approved_results:
        for result in approved_results:
            short_title = result.title.replace("Result - ", "", 1)
            summary = result.review_summary or "Approved by the reviewer."
            lines.append(f"- **{short_title}**: {summary}")
    else:
        lines.append("- No approved sections were available for consolidation.")

    lines.extend(
        [
            "",
            "## Consolidated Findings",
            "",
        ]
    )
    if not approved_results:
        lines.extend(
            [
                "No approved result content was available.",
                "",
            ]
        )
    else:
        for result in approved_results:
            short_title = result.title.replace("Result - ", "", 1)
            lines.append(f"## {short_title}")
            lines.append("")
            cleaned_output = _strip_leading_heading(result.output).strip()
            lines.append(cleaned_output or "No content available.")
            lines.append("")

    lines.extend(
        [
            "## Traceability",
            "",
            "This final report was assembled from the approved pages stored in the `Results` database. "
            "The `Task Queue` and `Audit Log` remain available as operational trace, but this page is the main human-facing deliverable.",
            "",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def _average_review_score(reviewed_results: Iterable[ResultRecord]) -> float | None:
    scores = [result.review_score for result in reviewed_results if result.review_score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _has_autogen_markers(content: str) -> bool:
    return all(
        marker in content
        for marker in (
            WHAT_I_BUILT_START,
            WHAT_I_BUILT_END,
            HOW_I_USED_START,
            HOW_I_USED_END,
        )
    )


def _replace_autogen_block(content: str, start_marker: str, end_marker: str, new_body: str) -> str:
    start_index = content.index(start_marker) + len(start_marker)
    end_index = content.index(end_marker)
    return content[:start_index] + "\n" + new_body + "\n" + content[end_index:]


def _strip_leading_heading(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].strip().startswith("# "):
        return "\n".join(lines[1:]).lstrip()
    return markdown

from __future__ import annotations


def build_workspace_guide_markdown(
    *,
    objectives_url: str,
    final_reports_url: str,
    task_queue_url: str,
    results_url: str,
    audit_log_url: str,
    agent_registry_url: str | None = None,
    latest_final_report_title: str | None = None,
    latest_final_report_url: str | None = None,
) -> str:
    lines = [
        "# Start Here",
        "",
        "## What This Workspace Does",
        "",
        "Notion Blackboard turns Notion into a shared workspace for multiple specialized agents:",
        "",
        "- you enter one objective",
        "- the manager breaks it into concrete tasks",
        "- the worker produces intermediate notes",
        "- the reviewer validates them and publishes one final report",
        "",
        "## The Only Two Places You Really Need",
        "",
        f"- [Objectives]({objectives_url}) is where a new mission starts.",
        f"- [Final Reports]({final_reports_url}) is where the human-facing deliverable lands.",
        "",
        "## Recommended Flow",
        "",
        "1. Open `Objectives` and add one row with your goal as the title.",
        "2. Run `python3 main.py --process-objectives` from the project folder.",
        "3. Open `Final Reports` and read the published deliverable.",
        "",
        "## What The Other Tables Mean",
        "",
        f"- [Task Queue]({task_queue_url}) is the internal work plan created by the manager.",
        f"- [Results]({results_url}) contains intermediate notes produced by the worker.",
        f"- [Audit Log]({audit_log_url}) records approvals, rejections, and orchestration events.",
    ]

    if agent_registry_url:
        lines.append(f"- [Agent Registry]({agent_registry_url}) shows which models are active.")

    lines.extend(
        [
            "",
            "## Plain-English Summary",
            "",
            "> Objectives in, final reports out. The rest is the engine room.",
        ]
    )

    if latest_final_report_title and latest_final_report_url:
        lines.extend(
            [
                "",
                "## Latest Published Deliverable",
                "",
                f"- [{latest_final_report_title}]({latest_final_report_url})",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def build_workspace_home_markdown(
    *,
    start_here_url: str,
    objectives_url: str,
    final_reports_url: str,
    task_queue_url: str,
    results_url: str,
    audit_log_url: str,
    agent_registry_url: str | None = None,
    latest_final_report_title: str | None = None,
    latest_final_report_url: str | None = None,
) -> str:
    lines = [
        "This is the main landing page for the demo. If you are reviewing the project, start with the three links below.",
        "",
        "## Product Surface",
        "",
        f"- [Start Here]({start_here_url}) - one-minute overview of how the workspace works",
        f"- [Objectives]({objectives_url}) - enter a new objective for the agents",
        f"- [Final Reports]({final_reports_url}) - read the final human-facing deliverables",
        "",
        "> Objectives in, final reports out. The rest is the engine room.",
        "",
        "## Demo Flow",
        "",
        "1. Open `Start Here`",
        "2. Add one objective in `Objectives`",
        "3. Run `python3 main.py --process-objectives`",
        "4. Open `Final Reports` to read the finished deliverable",
        "",
        "## Back Office",
        "",
        f"- [Task Queue]({task_queue_url}) - task decomposition and execution state",
        f"- [Results]({results_url}) - intermediate worker notes",
        f"- [Audit Log]({audit_log_url}) - approvals, rejections, and orchestration trace",
    ]

    if agent_registry_url:
        lines.append(f"- [Agent Registry]({agent_registry_url}) - active agents and models")

    if latest_final_report_title and latest_final_report_url:
        lines.extend(
            [
                "",
                "## Latest Published Deliverable",
                "",
                f"- [{latest_final_report_title}]({latest_final_report_url})",
            ]
        )

    return "\n".join(lines).strip() + "\n"

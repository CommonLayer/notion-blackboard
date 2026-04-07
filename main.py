from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from agents import BlackboardLLMClient, ManagerAgent, ReviewerAgent, WorkerAgent
from models import AgentDescriptor
from notion import NotionMCPClient
from notion.doctor import run_notion_doctor
from notion.setup import NotionSetupManager
from reporting import (
    build_final_deliverable_title,
    write_run_artifacts,
)
from settings import Settings
from workspace_guide import build_workspace_guide_markdown


def configure_logging(verbose: bool) -> None:
    Path("logs").mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler("logs/blackboard.log"),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Notion Blackboard pipeline.")
    parser.add_argument("objective", nargs="?", help="Objective to decompose and execute.")
    parser.add_argument("--doctor", action="store_true", help="Validate Notion connectivity and schema.")
    parser.add_argument(
        "--process-objectives",
        action="store_true",
        help="Run the pipeline for pending objectives stored in Notion.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the Notion databases under a parent page.",
    )
    parser.add_argument(
        "--publish-guide",
        action="store_true",
        help="Publish or refresh the Start Here guide page in Notion.",
    )
    parser.add_argument(
        "--parent-page-id",
        help="Parent Notion page id used by --bootstrap. Falls back to NOTION_PARENT_PAGE_ID.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without Notion or LLM API calls.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()
    selected_commands = sum(
        bool(value) for value in (args.doctor, args.bootstrap, args.process_objectives, args.publish_guide)
    )
    if selected_commands > 1:
        parser.error("Use only one of --doctor, --bootstrap, --process-objectives or --publish-guide at a time.")
    if not args.objective and not args.doctor and not args.bootstrap and not args.process_objectives and not args.publish_guide:
        parser.error("Provide an objective, or use --doctor / --bootstrap / --process-objectives / --publish-guide.")
    return args


def load_environment() -> None:
    load_dotenv()
    config_env = Path("config/.env")
    if config_env.exists():
        load_dotenv(config_env, override=True)


def register_agents(notion_client: NotionMCPClient, settings: Settings) -> None:
    notion_client.upsert_agent(
        AgentDescriptor(name="manager", agent_type="manager", model=settings.manager_model)
    )
    notion_client.upsert_agent(
        AgentDescriptor(name="worker", agent_type="worker", model=settings.worker_model)
    )
    notion_client.upsert_agent(
        AgentDescriptor(name="reviewer", agent_type="reviewer", model=settings.reviewer_model)
    )


def run_bootstrap(settings: Settings, parent_page_id: str | None) -> int:
    missing = settings.missing_bootstrap_requirements(parent_page_id)
    if missing:
        raise SystemExit(
            "Missing required environment variables for bootstrap: "
            + ", ".join(missing)
            + ". Set them in config/.env or pass --parent-page-id."
        )

    bootstrapper = NotionSetupManager(
        notion_token=settings.notion_token or "",
        notion_version=settings.notion_version,
        timeout_seconds=settings.request_timeout_seconds,
    )
    result = bootstrapper.bootstrap_blackboard(parent_page_id or settings.notion_parent_page_id or "")

    print("Bootstrap completed.")
    print("Copy these values into config/.env:")
    print(f"NOTION_PARENT_PAGE_ID={parent_page_id or settings.notion_parent_page_id}")
    print(f"NOTION_OBJECTIVES_DB={result['objectives']['database_id']}")
    print(f"NOTION_TASK_QUEUE_DB={result['task_queue']['database_id']}")
    print(f"NOTION_AGENT_REGISTRY_DB={result['agent_registry']['database_id']}")
    print(f"NOTION_RESULTS_DB={result['results']['database_id']}")
    print(f"NOTION_AUDIT_LOG_DB={result['audit_log']['database_id']}")
    print(f"NOTION_FINAL_REPORTS_DB={result['final_reports']['database_id']}")
    return 0


def run_doctor(settings: Settings) -> int:
    missing = settings.missing_doctor_requirements()
    if missing:
        raise SystemExit(
            "Missing required environment variables for doctor: "
            + ", ".join(missing)
            + ". Copy config/.env.example to config/.env and fill the values."
        )

    notion_client = NotionMCPClient(
        notion_token=settings.notion_token,
        objectives_db=settings.objectives_db,
        task_queue_db=settings.task_queue_db,
        agent_registry_db=settings.agent_registry_db,
        results_db=settings.results_db,
        audit_log_db=settings.audit_log_db,
        final_reports_db=settings.final_reports_db,
        notion_version=settings.notion_version,
        timeout_seconds=settings.request_timeout_seconds,
        dry_run=False,
    )
    healthy, lines = run_notion_doctor(notion_client)
    print("Notion Doctor")
    for line in lines:
        print(line)
    return 0 if healthy else 1


def publish_workspace_guide(
    notion_client: NotionMCPClient,
    settings: Settings,
    latest_final_report_url: str | None = None,
    latest_final_report_title: str | None = None,
) -> dict[str, str] | None:
    if settings.dry_run or not settings.notion_parent_page_id or not settings.objectives_db or not settings.final_reports_db:
        return None

    if not latest_final_report_url or not latest_final_report_title:
        latest_report = notion_client.get_latest_final_report()
        if latest_report:
            latest_final_report_url = latest_final_report_url or latest_report.url
            latest_final_report_title = latest_final_report_title or latest_report.title

    guide_markdown = build_workspace_guide_markdown(
        objectives_url=notion_client.get_database_url("objectives"),
        final_reports_url=notion_client.get_database_url("final_reports"),
        task_queue_url=notion_client.get_database_url("task_queue"),
        results_url=notion_client.get_database_url("results"),
        audit_log_url=notion_client.get_database_url("audit_log"),
        agent_registry_url=(
            notion_client.get_database_url("agent_registry") if settings.agent_registry_db else None
        ),
        latest_final_report_title=latest_final_report_title,
        latest_final_report_url=latest_final_report_url,
    )
    return notion_client.upsert_child_page(
        parent_page_id=settings.notion_parent_page_id,
        title="Start Here",
        body_markdown=guide_markdown,
        icon_emoji="🧭",
    )


def run_publish_guide(settings: Settings) -> int:
    missing = settings.missing_guide_requirements()
    if missing:
        raise SystemExit(
            "Missing required environment variables for guide publishing: "
            + ", ".join(missing)
            + "."
        )

    notion_client = NotionMCPClient(
        notion_token=settings.notion_token,
        objectives_db=settings.objectives_db,
        task_queue_db=settings.task_queue_db,
        agent_registry_db=settings.agent_registry_db,
        results_db=settings.results_db,
        audit_log_db=settings.audit_log_db,
        final_reports_db=settings.final_reports_db,
        notion_version=settings.notion_version,
        timeout_seconds=settings.request_timeout_seconds,
        dry_run=False,
    )
    guide_page = publish_workspace_guide(notion_client, settings)
    print(f"Guide page: {guide_page['url'] if guide_page else 'skipped'}")
    return 0


def run_pipeline_for_objective(
    *,
    objective: str,
    notion_client: NotionMCPClient,
    llm_client: BlackboardLLMClient,
    settings: Settings,
    objective_record_id: str | None = None,
) -> dict[str, str | int | float | None]:
    register_agents(notion_client, settings)

    manager = ManagerAgent("manager", settings.manager_model, llm_client, notion_client)
    worker = WorkerAgent("worker", settings.worker_model, llm_client, notion_client)
    reviewer = ReviewerAgent("reviewer", settings.reviewer_model, llm_client, notion_client)

    if objective_record_id:
        notion_client.update_objective_status(objective_record_id, "in_progress")
    try:
        created_tasks = manager.run(objective)
        produced_results = worker.run(created_tasks)
        reviewed_results = reviewer.run(produced_results)
        mode = "dry-run" if settings.dry_run else "live"
        final_deliverable_markdown = llm_client.synthesize_final_report(
            settings.reviewer_model,
            objective,
            reviewed_results,
        )
        artifact_paths = write_run_artifacts(
            objective=objective,
            mode=mode,
            tasks=created_tasks,
            results=produced_results,
            reviewed_results=reviewed_results,
            final_deliverable_markdown=final_deliverable_markdown,
        )

        approved = sum(1 for result in reviewed_results if result.status == "approved")
        rejected = sum(1 for result in reviewed_results if result.status == "rejected")
        scored_results = [result.review_score for result in reviewed_results if result.review_score is not None]
        average_score = round(sum(scored_results) / len(scored_results), 1) if scored_results else None

        final_summary = (
            reviewed_results[0].review_summary
            if len(reviewed_results) == 1 and reviewed_results[0].review_summary
            else f"{approved} approved sections consolidated into one final report."
        )

        final_report = notion_client.create_final_report(
            title=build_final_deliverable_title(objective),
            objective=objective,
            summary=final_summary,
            score=average_score,
            body_markdown=final_deliverable_markdown,
        )
        notion_client.create_audit_log(
            action="created",
            agent="system",
            details=(
                f"Published final report '{final_report.title}' for objective '{objective}'. "
                f"URL: {final_report.url or 'n/a'}"
            ),
        )

        if objective_record_id:
            notion_client.attach_final_report_to_objective(objective_record_id, final_report.url)
            notion_client.update_objective_status(objective_record_id, "done")

        guide_page = publish_workspace_guide(
            notion_client,
            settings,
            latest_final_report_url=final_report.url,
            latest_final_report_title=final_report.title,
        )
        return {
            "mode": mode,
            "objective": objective,
            "tasks_created": len(created_tasks),
            "results_produced": len(produced_results),
            "approved": approved,
            "rejected": rejected,
            "average_score": average_score,
            "run_report": str(artifact_paths["report"]),
            "final_deliverable": str(artifact_paths["final_deliverable"]),
            "submission_draft": str(artifact_paths["submission"]),
            "final_report_url": final_report.url,
            "final_report_title": final_report.title,
        }
    except Exception as exc:
        if objective_record_id:
            notion_client.update_objective_status(objective_record_id, "failed")
        notion_client.create_audit_log(
            action="rejected",
            agent="system",
            details=f"Pipeline failed for objective '{objective}': {exc}",
        )
        raise


def run_pending_objectives(settings: Settings) -> int:
    missing = settings.missing_objectives_requirements()
    if missing:
        raise SystemExit(
            "Missing required environment variables for objective processing: "
            + ", ".join(missing)
            + "."
        )

    notion_client = NotionMCPClient(
        notion_token=settings.notion_token,
        objectives_db=settings.objectives_db,
        task_queue_db=settings.task_queue_db,
        agent_registry_db=settings.agent_registry_db,
        results_db=settings.results_db,
        audit_log_db=settings.audit_log_db,
        final_reports_db=settings.final_reports_db,
        notion_version=settings.notion_version,
        timeout_seconds=settings.request_timeout_seconds,
        dry_run=False,
    )
    llm_client = BlackboardLLMClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        referer=settings.openrouter_referer,
        title=settings.openrouter_title,
        timeout_seconds=settings.request_timeout_seconds,
        dry_run=False,
    )

    objectives = notion_client.get_pending_objectives()
    if not objectives:
        print("No pending objectives found.")
        return 0

    for objective_record in objectives:
        summary = run_pipeline_for_objective(
            objective=objective_record.title,
            notion_client=notion_client,
            llm_client=llm_client,
            settings=settings,
            objective_record_id=objective_record.id,
        )
        print(f"Processed objective: {summary['objective']}")
        print(f"Final report: {summary['final_report_url'] or summary['final_report_title']}")
    return 0


def main() -> int:
    args = parse_args()
    load_environment()
    settings = Settings.from_env(dry_run_override=args.dry_run)
    configure_logging(args.verbose)

    if args.bootstrap:
        return run_bootstrap(settings, args.parent_page_id)

    if args.doctor:
        return run_doctor(settings)

    if args.process_objectives:
        return run_pending_objectives(settings)

    if args.publish_guide:
        return run_publish_guide(settings)

    if not settings.dry_run:
        missing = settings.missing_live_requirements()
        if missing:
            raise SystemExit(
                "Missing required environment variables for live mode: "
                + ", ".join(missing)
                + ". Copy config/.env.example to config/.env and fill the values."
            )

    notion_client = NotionMCPClient(
        notion_token=settings.notion_token,
        objectives_db=settings.objectives_db,
        task_queue_db=settings.task_queue_db,
        agent_registry_db=settings.agent_registry_db,
        results_db=settings.results_db,
        audit_log_db=settings.audit_log_db,
        final_reports_db=settings.final_reports_db,
        notion_version=settings.notion_version,
        timeout_seconds=settings.request_timeout_seconds,
        dry_run=settings.dry_run,
    )
    llm_client = BlackboardLLMClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        referer=settings.openrouter_referer,
        title=settings.openrouter_title,
        timeout_seconds=settings.request_timeout_seconds,
        dry_run=settings.dry_run,
    )

    objective_record_id = None
    if not settings.dry_run and settings.objectives_db:
        objective_record = notion_client.create_objective(args.objective)
        objective_record_id = objective_record.id

    summary = run_pipeline_for_objective(
        objective=args.objective,
        notion_client=notion_client,
        llm_client=llm_client,
        settings=settings,
        objective_record_id=objective_record_id,
    )

    print(f"Mode: {summary['mode']}")
    print(f"Objective: {summary['objective']}")
    print(f"Tasks created: {summary['tasks_created']}")
    print(f"Results produced: {summary['results_produced']}")
    print(f"Approved: {summary['approved']}")
    print(f"Rejected: {summary['rejected']}")
    if summary["average_score"] is not None:
        print(f"Average review score: {summary['average_score']}")
    print(f"Run report: {summary['run_report']}")
    print(f"Final deliverable: {summary['final_deliverable']}")
    print(f"Submission draft: {summary['submission_draft']}")
    print(f"Final report: {summary['final_report_url'] or summary['final_report_title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

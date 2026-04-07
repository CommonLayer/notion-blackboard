from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    notion_token: str | None
    notion_parent_page_id: str | None
    objectives_db: str | None
    task_queue_db: str | None
    agent_registry_db: str | None
    results_db: str | None
    audit_log_db: str | None
    final_reports_db: str | None
    openrouter_api_key: str | None
    openrouter_base_url: str
    openrouter_referer: str | None
    openrouter_title: str | None
    manager_model: str
    worker_model: str
    reviewer_model: str
    notion_version: str
    request_timeout_seconds: float
    dry_run: bool

    @classmethod
    def from_env(cls, dry_run_override: bool | None = None) -> "Settings":
        env_dry_run = _as_bool(os.getenv("BLACKBOARD_DRY_RUN"), default=False)
        dry_run = env_dry_run if dry_run_override is None else dry_run_override
        return cls(
            notion_token=os.getenv("NOTION_TOKEN"),
            notion_parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID"),
            objectives_db=os.getenv("NOTION_OBJECTIVES_DB"),
            task_queue_db=os.getenv("NOTION_TASK_QUEUE_DB"),
            agent_registry_db=os.getenv("NOTION_AGENT_REGISTRY_DB"),
            results_db=os.getenv("NOTION_RESULTS_DB"),
            audit_log_db=os.getenv("NOTION_AUDIT_LOG_DB"),
            final_reports_db=os.getenv("NOTION_FINAL_REPORTS_DB"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            openrouter_referer=os.getenv("OPENROUTER_REFERER"),
            openrouter_title=os.getenv("OPENROUTER_TITLE", "Notion Blackboard"),
            manager_model=os.getenv("MANAGER_MODEL", "anthropic/claude-opus-4-5"),
            worker_model=os.getenv("WORKER_MODEL", "openai/gpt-4o"),
            reviewer_model=os.getenv("REVIEWER_MODEL", "google/gemini-2.5-flash-lite"),
            notion_version=os.getenv("NOTION_VERSION", "2025-09-03"),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "45")),
            dry_run=dry_run,
        )

    def missing_live_requirements(self) -> list[str]:
        missing: list[str] = []
        required = {
            "NOTION_TOKEN": self.notion_token,
            "NOTION_OBJECTIVES_DB": self.objectives_db,
            "NOTION_TASK_QUEUE_DB": self.task_queue_db,
            "NOTION_RESULTS_DB": self.results_db,
            "NOTION_AUDIT_LOG_DB": self.audit_log_db,
            "NOTION_FINAL_REPORTS_DB": self.final_reports_db,
            "OPENROUTER_API_KEY": self.openrouter_api_key,
        }
        for env_name, value in required.items():
            if not value:
                missing.append(env_name)
        return missing

    def missing_doctor_requirements(self) -> list[str]:
        missing: list[str] = []
        required = {
            "NOTION_TOKEN": self.notion_token,
            "NOTION_TASK_QUEUE_DB": self.task_queue_db,
            "NOTION_RESULTS_DB": self.results_db,
            "NOTION_AUDIT_LOG_DB": self.audit_log_db,
        }
        for env_name, value in required.items():
            if not value:
                missing.append(env_name)
        return missing

    def missing_objectives_requirements(self) -> list[str]:
        missing: list[str] = []
        required = {
            "NOTION_TOKEN": self.notion_token,
            "NOTION_OBJECTIVES_DB": self.objectives_db,
            "NOTION_FINAL_REPORTS_DB": self.final_reports_db,
            "NOTION_TASK_QUEUE_DB": self.task_queue_db,
            "NOTION_RESULTS_DB": self.results_db,
            "NOTION_AUDIT_LOG_DB": self.audit_log_db,
            "OPENROUTER_API_KEY": self.openrouter_api_key,
        }
        for env_name, value in required.items():
            if not value:
                missing.append(env_name)
        return missing

    def missing_guide_requirements(self) -> list[str]:
        missing: list[str] = []
        required = {
            "NOTION_TOKEN": self.notion_token,
            "NOTION_PARENT_PAGE_ID": self.notion_parent_page_id,
            "NOTION_OBJECTIVES_DB": self.objectives_db,
            "NOTION_TASK_QUEUE_DB": self.task_queue_db,
            "NOTION_RESULTS_DB": self.results_db,
            "NOTION_AUDIT_LOG_DB": self.audit_log_db,
            "NOTION_FINAL_REPORTS_DB": self.final_reports_db,
        }
        for env_name, value in required.items():
            if not value:
                missing.append(env_name)
        return missing

    def missing_bootstrap_requirements(self, parent_page_id: str | None = None) -> list[str]:
        missing: list[str] = []
        required = {
            "NOTION_TOKEN": self.notion_token,
            "NOTION_PARENT_PAGE_ID": parent_page_id or self.notion_parent_page_id,
        }
        for env_name, value in required.items():
            if not value:
                missing.append(env_name)
        return missing

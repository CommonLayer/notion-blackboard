from __future__ import annotations

from typing import Any

import requests


class NotionSetupManager:
    def __init__(self, notion_token: str, notion_version: str = "2025-09-03", timeout_seconds: float = 45.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {notion_token}",
                "Content-Type": "application/json",
                "Notion-Version": notion_version,
            }
        )

    def bootstrap_blackboard(self, parent_page_id: str) -> dict[str, dict[str, str]]:
        objectives = self._create_database(
            parent_page_id=parent_page_id,
            title="Objectives",
            icon="🎯",
            properties={
                "Title": {"title": {}},
                "Status": self._select_property(
                    [
                        ("pending", "yellow"),
                        ("in_progress", "blue"),
                        ("done", "green"),
                        ("failed", "red"),
                    ]
                ),
                "Created": {"date": {}},
                "Final Report URL": {"url": {}},
            },
        )
        task_queue = self._create_database(
            parent_page_id=parent_page_id,
            title="Task Queue",
            icon="📋",
            properties={
                "Title": {"title": {}},
                "Status": self._select_property(
                    [
                        ("pending", "yellow"),
                        ("in_progress", "blue"),
                        ("done", "green"),
                        ("rejected", "red"),
                    ]
                ),
                "Priority": {"number": {"format": "number"}},
                "Objective": {"rich_text": {}},
                "Created": {"date": {}},
            },
        )
        agent_registry = self._create_database(
            parent_page_id=parent_page_id,
            title="Agent Registry",
            icon="🤖",
            properties={
                "Title": {"title": {}},
                "Type": self._select_property(
                    [
                        ("manager", "purple"),
                        ("worker", "blue"),
                        ("reviewer", "green"),
                    ]
                ),
                "Model": {"rich_text": {}},
                "Status": self._select_property(
                    [
                        ("active", "green"),
                        ("paused", "yellow"),
                    ]
                ),
                "Last Heartbeat": {"date": {}},
            },
        )
        results = self._create_database(
            parent_page_id=parent_page_id,
            title="Results",
            icon="✅",
            properties={
                "Title": {"title": {}},
                "Task": {
                    "relation": {
                        "data_source_id": task_queue["data_source_id"],
                        "single_property": {},
                    }
                },
                "Output": {"rich_text": {}},
                "Status": self._select_property(
                    [
                        ("pending_review", "yellow"),
                        ("approved", "green"),
                        ("rejected", "red"),
                    ]
                ),
                "Agent": {"rich_text": {}},
            },
        )
        audit_log = self._create_database(
            parent_page_id=parent_page_id,
            title="Audit Log",
            icon="🧾",
            properties={
                "Title": {"title": {}},
                "Agent": {"rich_text": {}},
                "Action": self._select_property(
                    [
                        ("created", "blue"),
                        ("updated", "gray"),
                        ("approved", "green"),
                        ("rejected", "red"),
                    ]
                ),
                "Timestamp": {"date": {}},
                "Details": {"rich_text": {}},
            },
        )
        final_reports = self._create_database(
            parent_page_id=parent_page_id,
            title="Final Reports",
            icon="📘",
            properties={
                "Title": {"title": {}},
                "Objective": {"rich_text": {}},
                "Summary": {"rich_text": {}},
                "Score": {"number": {"format": "number"}},
                "Status": self._select_property(
                    [
                        ("published", "green"),
                        ("draft", "yellow"),
                    ]
                ),
                "Created": {"date": {}},
            },
        )
        return {
            "objectives": objectives,
            "task_queue": task_queue,
            "agent_registry": agent_registry,
            "results": results,
            "audit_log": audit_log,
            "final_reports": final_reports,
        }

    def _create_database(
        self,
        parent_page_id: str,
        title: str,
        icon: str,
        properties: dict[str, Any],
    ) -> dict[str, str]:
        response = self._request(
            "POST",
            "/v1/databases",
            json={
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "icon": {"type": "emoji", "emoji": icon},
                "title": self._title(title),
                "initial_data_source": {"properties": properties},
            },
        )
        data_sources = response.get("data_sources") or []
        if not data_sources:
            raise RuntimeError(f"Database '{title}' was created without an attached data source.")
        return {
            "database_id": response["id"],
            "data_source_id": data_sources[0]["id"],
            "url": response.get("url", ""),
            "title": title,
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.session.request(
            method=method,
            url=f"https://api.notion.com{path}",
            timeout=self.timeout_seconds,
            **kwargs,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Notion API error {response.status_code} on {path}: {response.text}")
        return response.json()

    @staticmethod
    def _title(content: str) -> list[dict[str, Any]]:
        return [{"type": "text", "text": {"content": content}}]

    @staticmethod
    def _select_property(options: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "select": {
                "options": [{"name": name, "color": color} for name, color in options],
            }
        }

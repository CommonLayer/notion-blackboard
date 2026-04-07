from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import uuid4

import requests

from models import AgentDescriptor, FinalReportRecord, ObjectiveRecord, ResultRecord, TaskRecord
from notion.markdown_blocks import markdown_to_notion_blocks, markdown_to_preview, notion_blocks_to_markdown


DEFAULT_SCHEMAS: dict[str, dict[str, str]] = {
    "objectives": {
        "Title": "title",
        "Status": "select",
        "Created": "date",
        "Final Report URL": "url",
    },
    "task_queue": {
        "Title": "title",
        "Status": "select",
        "Priority": "number",
        "Objective": "rich_text",
        "Created": "date",
    },
    "agent_registry": {
        "Title": "title",
        "Type": "select",
        "Model": "rich_text",
        "Status": "select",
        "Last Heartbeat": "date",
    },
    "results": {
        "Title": "title",
        "Task": "relation",
        "Output": "rich_text",
        "Status": "select",
        "Agent": "rich_text",
    },
    "audit_log": {
        "Title": "title",
        "Agent": "rich_text",
        "Action": "select",
        "Timestamp": "date",
        "Details": "rich_text",
    },
    "final_reports": {
        "Title": "title",
        "Objective": "rich_text",
        "Summary": "rich_text",
        "Score": "number",
        "Status": "select",
        "Created": "date",
    },
}


class NotionMCPClient:
    def __init__(
        self,
        notion_token: str | None,
        objectives_db: str | None,
        task_queue_db: str | None,
        results_db: str | None,
        audit_log_db: str | None,
        final_reports_db: str | None = None,
        agent_registry_db: str | None = None,
        notion_version: str = "2025-09-03",
        timeout_seconds: float = 45.0,
        dry_run: bool = False,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self._database_ids = {
            "objectives": objectives_db,
            "task_queue": task_queue_db,
            "agent_registry": agent_registry_db,
            "results": results_db,
            "audit_log": audit_log_db,
            "final_reports": final_reports_db,
        }
        self._objective_cache: dict[str, ObjectiveRecord] = {}
        self._data_source_cache: dict[str, str] = {}
        self._data_source_response_cache: dict[str, dict[str, Any]] = {}
        self._schema_cache: dict[str, dict[str, str]] = {}
        self._task_cache: dict[str, TaskRecord] = {}
        self._result_cache: dict[str, ResultRecord] = {}
        self._audit_cache: list[dict[str, Any]] = []
        self._agent_cache: dict[str, dict[str, Any]] = {}

        self._session: requests.Session | None = None
        if not self.dry_run:
            if not notion_token:
                raise ValueError("NOTION_TOKEN is required when dry_run is disabled.")
            session = requests.Session()
            session.headers.update(
                {
                    "Authorization": f"Bearer {notion_token}",
                    "Content-Type": "application/json",
                    "Notion-Version": notion_version,
                }
            )
            self._session = session

    def get_pending_tasks(self) -> list[TaskRecord]:
        if self.dry_run:
            return sorted(
                [task for task in self._task_cache.values() if task.status == "pending"],
                key=lambda item: item.priority,
            )

        payload = {
            "filter": self._status_filter("task_queue", "Status", "pending"),
            "sorts": [{"property": "Priority", "direction": "ascending"}],
            "page_size": 100,
        }
        response = self._request(
            "POST",
            f"/v1/data_sources/{self._resolve_data_source_id('task_queue')}/query",
            json=payload,
        )
        return [self._task_from_page(page) for page in response.get("results", [])]

    def get_pending_objectives(self) -> list[ObjectiveRecord]:
        if not self._database_ids.get("objectives"):
            return []
        if self.dry_run:
            return [item for item in self._objective_cache.values() if item.status == "pending"]

        payload = {
            "filter": self._status_filter("objectives", "Status", "pending"),
            "sorts": [{"property": "Created", "direction": "ascending"}],
            "page_size": 100,
        }
        response = self._request(
            "POST",
            f"/v1/data_sources/{self._resolve_data_source_id('objectives')}/query",
            json=payload,
        )
        return [self._objective_from_page(page) for page in response.get("results", [])]

    def update_objective_status(self, objective_id: str, status: str) -> None:
        if self.dry_run:
            objective = self._objective_cache.get(objective_id)
            if objective:
                objective.status = status
            return

        self._request(
            "PATCH",
            f"/v1/pages/{objective_id}",
            json={
                "properties": {
                    "Status": self._choice_property("objectives", "Status", status),
                }
            },
        )

    def attach_final_report_to_objective(self, objective_id: str, final_report_url: str) -> None:
        if self.dry_run:
            objective = self._objective_cache.get(objective_id)
            if objective:
                objective.final_report_url = final_report_url
            return

        if self._property_type("objectives", "Final Report URL") != "url":
            return

        self._request(
            "PATCH",
            f"/v1/pages/{objective_id}",
            json={
                "properties": {
                    "Final Report URL": {"url": final_report_url},
                }
            },
        )

    def get_task(self, task_id: str) -> TaskRecord:
        if self.dry_run:
            task = self._task_cache.get(task_id)
            if not task:
                raise KeyError(f"Unknown task id: {task_id}")
            return task

        response = self._request("GET", f"/v1/pages/{task_id}")
        return self._task_from_page(response)

    def create_objective(self, title: str) -> ObjectiveRecord:
        created_at = self._iso_now()
        if self.dry_run:
            objective = ObjectiveRecord(
                id=self._new_id(),
                title=title,
                status="pending",
                created=created_at,
            )
            self._objective_cache[objective.id] = objective
            return objective

        properties: dict[str, Any] = {
            "Title": self._text_property("objectives", "Title", title),
            "Status": self._choice_property("objectives", "Status", "pending"),
        }
        created_property = self._date_property("objectives", "Created", created_at)
        if created_property is not None:
            properties["Created"] = created_property
        response = self._request(
            "POST",
            "/v1/pages",
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": self._resolve_data_source_id("objectives"),
                },
                "properties": properties,
            },
        )
        return self._objective_from_page(response)

    def create_task(self, title: str, priority: int, objective: str) -> TaskRecord:
        created_at = self._iso_now()
        if self.dry_run:
            task = TaskRecord(
                id=self._new_id(),
                title=title,
                priority=priority,
                objective=objective,
                status="pending",
                created=created_at,
            )
            self._task_cache[task.id] = task
            return task

        properties: dict[str, Any] = {
            "Title": self._text_property("task_queue", "Title", title),
            "Status": self._choice_property("task_queue", "Status", "pending"),
            "Priority": self._number_property(priority),
            "Objective": self._text_property("task_queue", "Objective", objective),
        }
        created_property = self._date_property("task_queue", "Created", created_at)
        if created_property is not None:
            properties["Created"] = created_property
        response = self._request(
            "POST",
            "/v1/pages",
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": self._resolve_data_source_id("task_queue"),
                },
                "properties": properties,
            },
        )
        return self._task_from_page(response)

    def update_task_status(self, task_id: str, status: str) -> None:
        if self.dry_run:
            task = self.get_task(task_id)
            task.status = status
            return

        self._request(
            "PATCH",
            f"/v1/pages/{task_id}",
            json={
                "properties": {
                    "Status": self._choice_property("task_queue", "Status", status),
                }
            },
        )

    def create_result(
        self,
        title: str,
        task_id: str,
        output: str,
        agent: str,
        body_markdown: str | None = None,
    ) -> ResultRecord:
        stored_output = markdown_to_preview(body_markdown) if body_markdown else output
        if self.dry_run:
            result = ResultRecord(
                id=self._new_id(),
                title=title,
                task_id=task_id,
                output=body_markdown or output,
                agent=agent,
                status="pending_review",
            )
            self._result_cache[result.id] = result
            return result

        response = self._request(
            "POST",
            "/v1/pages",
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": self._resolve_data_source_id("results"),
                },
                "properties": {
                    "Title": self._text_property("results", "Title", title),
                    "Task": self._relation_property(task_id),
                    "Output": self._text_property("results", "Output", stored_output),
                    "Status": self._choice_property("results", "Status", "pending_review"),
                    "Agent": self._text_property("results", "Agent", agent),
                },
            },
        )
        result = self._result_from_page(response)
        if body_markdown:
            self._replace_page_body_with_markdown(result.id, body_markdown)
            result.output = body_markdown
        return result

    def create_final_report(
        self,
        title: str,
        objective: str,
        summary: str,
        score: float | None,
        body_markdown: str,
    ) -> FinalReportRecord:
        created_at = self._iso_now()
        if self.dry_run:
            return FinalReportRecord(
                id=self._new_id(),
                title=title,
                objective=objective,
                summary=summary,
                score=score,
                status="published",
                url="",
            )

        properties: dict[str, Any] = {
            "Title": self._text_property("final_reports", "Title", title),
            "Objective": self._text_property("final_reports", "Objective", objective),
            "Summary": self._text_property("final_reports", "Summary", summary),
            "Status": self._choice_property("final_reports", "Status", "published"),
        }
        if score is not None and self._property_type("final_reports", "Score") == "number":
            properties["Score"] = self._number_property(score)
        created_property = self._date_property("final_reports", "Created", created_at)
        if created_property is not None:
            properties["Created"] = created_property

        response = self._request(
            "POST",
            "/v1/pages",
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": self._resolve_data_source_id("final_reports"),
                },
                "properties": properties,
            },
        )
        page_id = response["id"]
        self._replace_page_body_with_markdown(page_id, body_markdown)
        return FinalReportRecord(
            id=page_id,
            title=title,
            objective=objective,
            summary=summary,
            score=score,
            status="published",
            url=response.get("url", ""),
        )

    def get_pending_results(self) -> list[ResultRecord]:
        if self.dry_run:
            return [result for result in self._result_cache.values() if result.status == "pending_review"]

        payload = {
            "filter": self._status_filter("results", "Status", "pending_review"),
            "page_size": 100,
        }
        response = self._request(
            "POST",
            f"/v1/data_sources/{self._resolve_data_source_id('results')}/query",
            json=payload,
        )
        results: list[ResultRecord] = []
        for page in response.get("results", []):
            result = self._result_from_page(page)
            body_markdown = self._page_body_as_markdown(result.id)
            if body_markdown:
                result.output = body_markdown
            results.append(result)
        return results

    def get_latest_final_report(self) -> FinalReportRecord | None:
        if not self._database_ids.get("final_reports"):
            return None
        if self.dry_run:
            return None

        payload = {
            "sorts": [{"property": "Created", "direction": "descending"}],
            "page_size": 1,
        }
        response = self._request(
            "POST",
            f"/v1/data_sources/{self._resolve_data_source_id('final_reports')}/query",
            json=payload,
        )
        results = response.get("results", [])
        if not results:
            return None
        return self._final_report_from_page(results[0])

    def update_result_status(self, result_id: str, status: str) -> None:
        if self.dry_run:
            result = self._result_cache.get(result_id)
            if not result:
                raise KeyError(f"Unknown result id: {result_id}")
            result.status = status
            return

        self._request(
            "PATCH",
            f"/v1/pages/{result_id}",
            json={
                "properties": {
                    "Status": self._choice_property("results", "Status", status),
                }
            },
        )

    def create_audit_log(self, action: str, agent: str, details: str) -> None:
        title = f"{action} by {agent}"
        entry = {
            "title": title,
            "agent": agent,
            "action": action,
            "timestamp": self._iso_now(),
            "details": details,
        }
        if self.dry_run:
            self._audit_cache.append(entry)
            return

        properties: dict[str, Any] = {
            "Title": self._text_property("audit_log", "Title", title),
            "Agent": self._text_property("audit_log", "Agent", agent),
            "Action": self._choice_property("audit_log", "Action", action),
            "Details": self._text_property("audit_log", "Details", details),
        }
        timestamp_property = self._date_property("audit_log", "Timestamp", entry["timestamp"])
        if timestamp_property is not None:
            properties["Timestamp"] = timestamp_property

        self._request(
            "POST",
            "/v1/pages",
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": self._resolve_data_source_id("audit_log"),
                },
                "properties": properties,
            },
        )

    def upsert_agent(self, agent: AgentDescriptor) -> None:
        if not self._database_ids.get("agent_registry"):
            self.logger.debug("Agent Registry database is not configured; skipping heartbeat.")
            return

        if self.dry_run:
            self._agent_cache[agent.name] = {
                "type": agent.agent_type,
                "model": agent.model,
                "status": agent.status,
                "last_heartbeat": self._iso_now(),
            }
            return

        existing_id = self._find_agent_page_id(agent.name, agent.agent_type)
        payload = {
            "Title": self._text_property("agent_registry", "Title", agent.name),
            "Type": self._choice_property("agent_registry", "Type", agent.agent_type),
            "Model": self._text_property("agent_registry", "Model", agent.model),
            "Status": self._choice_property("agent_registry", "Status", agent.status),
        }
        heartbeat_property = self._date_property(
            "agent_registry",
            "Last Heartbeat",
            self._iso_now(),
        )
        if heartbeat_property is not None:
            payload["Last Heartbeat"] = heartbeat_property

        if existing_id:
            self._request("PATCH", f"/v1/pages/{existing_id}", json={"properties": payload})
            return

        self._request(
            "POST",
            "/v1/pages",
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": self._resolve_data_source_id("agent_registry"),
                },
                "properties": payload,
            },
        )

    def _find_agent_page_id(self, name: str, agent_type: str) -> str | None:
        payload = {
            "filter": {
                "and": [
                    self._text_equals_filter("agent_registry", "Title", name),
                    self._choice_equals_filter("agent_registry", "Type", agent_type),
                ]
            },
            "page_size": 1,
        }
        response = self._request(
            "POST",
            f"/v1/data_sources/{self._resolve_data_source_id('agent_registry')}/query",
            json=payload,
        )
        results = response.get("results", [])
        if not results:
            return None
        return results[0]["id"]

    def get_database_id(self, database_key: str) -> str | None:
        return self._database_ids.get(database_key)

    def get_database_url(self, database_key: str) -> str:
        database_id = self._database_ids.get(database_key)
        if not database_id:
            raise ValueError(f"Missing Notion database id for {database_key}.")
        return self._canonical_notion_url(database_id)

    def get_page_url(self, page_id: str) -> str:
        return self._canonical_notion_url(page_id)

    def get_data_source_id(self, database_key: str) -> str:
        return self._resolve_data_source_id(database_key)

    def describe_data_source(self, database_key: str) -> dict[str, Any]:
        cached = self._data_source_response_cache.get(database_key)
        if cached:
            return cached
        if self.dry_run:
            properties: dict[str, dict[str, Any]] = {}
            for name, property_type in DEFAULT_SCHEMAS[database_key].items():
                property_data: dict[str, Any] = {"name": name, "type": property_type}
                if property_type == "select":
                    property_data["select"] = {
                        "options": [{"name": option} for option in self._dry_run_options(database_key, name)]
                    }
                if property_type == "relation":
                    property_data["relation"] = {
                        "data_source_id": self._resolve_data_source_id_for_dry_run("task_queue"),
                    }
                properties[name] = property_data
            description = {
                "id": self._resolve_data_source_id_for_dry_run(database_key),
                "properties": properties,
            }
            self._data_source_response_cache[database_key] = description
            return description

        description = self._request(
            "GET",
            f"/v1/data_sources/{self._resolve_data_source_id(database_key)}",
        )
        self._data_source_response_cache[database_key] = description
        return description

    def _task_from_page(self, page: dict[str, Any]) -> TaskRecord:
        properties = page.get("properties", {})
        created_property = properties.get("Created")
        created = self._date_value(created_property) if created_property else page.get("created_time")
        return TaskRecord(
            id=page["id"],
            title=self._text_value(properties.get("Title")),
            priority=int(self._number_value(properties.get("Priority")) or 0),
            objective=self._text_value(properties.get("Objective")),
            status=self._choice_value(properties.get("Status")) or "pending",
            created=created,
        )

    def _objective_from_page(self, page: dict[str, Any]) -> ObjectiveRecord:
        properties = page.get("properties", {})
        created_property = properties.get("Created")
        created = self._date_value(created_property) if created_property else page.get("created_time")
        return ObjectiveRecord(
            id=page["id"],
            title=self._text_value(properties.get("Title")),
            status=self._choice_value(properties.get("Status")) or "pending",
            created=created,
            final_report_url=self._url_value(properties.get("Final Report URL")),
        )

    def _result_from_page(self, page: dict[str, Any]) -> ResultRecord:
        properties = page.get("properties", {})
        task_ids = self._relation_value(properties.get("Task"))
        return ResultRecord(
            id=page["id"],
            title=self._text_value(properties.get("Title")),
            task_id=task_ids[0] if task_ids else "",
            output=self._text_value(properties.get("Output")),
            agent=self._text_value(properties.get("Agent")),
            status=self._choice_value(properties.get("Status")) or "pending_review",
        )

    def _final_report_from_page(self, page: dict[str, Any]) -> FinalReportRecord:
        properties = page.get("properties", {})
        return FinalReportRecord(
            id=page["id"],
            title=self._text_value(properties.get("Title")),
            objective=self._text_value(properties.get("Objective")),
            summary=self._text_value(properties.get("Summary")),
            score=self._number_value(properties.get("Score")),
            status=self._choice_value(properties.get("Status")) or "published",
            url=page.get("url", self._canonical_notion_url(page["id"])),
        )

    def update_result_output(self, result_id: str, preview: str, body_markdown: str | None = None) -> None:
        if self.dry_run:
            result = self._result_cache.get(result_id)
            if result:
                result.output = body_markdown or preview
            return

        self._request(
            "PATCH",
            f"/v1/pages/{result_id}",
            json={
                "properties": {
                    "Output": self._text_property("results", "Output", preview),
                }
            },
        )
        if body_markdown:
            self._replace_page_body_with_markdown(result_id, body_markdown)

    def replace_page_body(self, page_id: str, body_markdown: str) -> None:
        if self.dry_run:
            return
        self._replace_page_body_with_markdown(page_id, body_markdown)

    def create_child_page(
        self,
        parent_page_id: str,
        title: str,
        body_markdown: str,
        icon_emoji: str | None = None,
    ) -> dict[str, str]:
        if self.dry_run:
            return {
                "id": self._new_id(),
                "url": "",
                "title": title,
            }

        payload: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {
                "title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": self._chunk_text(title, 1)[0]},
                        }
                    ]
                }
            },
        }
        if icon_emoji:
            payload["icon"] = {"type": "emoji", "emoji": icon_emoji}

        blocks = markdown_to_notion_blocks(body_markdown)
        if blocks:
            payload["children"] = blocks[:100]
        response = self._request("POST", "/v1/pages", json=payload)
        if len(blocks) > 100:
            for index in range(100, len(blocks), 100):
                self._request(
                    "PATCH",
                    f"/v1/blocks/{response['id']}/children",
                    json={"children": blocks[index : index + 100]},
                )
        return {
            "id": response["id"],
            "url": response.get("url", self._canonical_notion_url(response["id"])),
            "title": title,
        }

    def upsert_child_page(
        self,
        parent_page_id: str,
        title: str,
        body_markdown: str,
        icon_emoji: str | None = None,
    ) -> dict[str, str]:
        if self.dry_run:
            return {
                "id": self._new_id(),
                "url": "",
                "title": title,
            }

        existing_page_id = self._find_child_page_id(parent_page_id, title)
        if not existing_page_id:
            return self.create_child_page(
                parent_page_id=parent_page_id,
                title=title,
                body_markdown=body_markdown,
                icon_emoji=icon_emoji,
            )

        payload: dict[str, Any] = {
            "properties": {
                "title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": self._chunk_text(title, 1)[0]},
                        }
                    ]
                }
            }
        }
        if icon_emoji:
            payload["icon"] = {"type": "emoji", "emoji": icon_emoji}

        self._request("PATCH", f"/v1/pages/{existing_page_id}", json=payload)
        self._replace_page_body_with_markdown(existing_page_id, body_markdown)
        return {
            "id": existing_page_id,
            "url": self._canonical_notion_url(existing_page_id),
            "title": title,
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("Notion session is not configured.")
        response = self._session.request(
            method=method,
            url=f"https://api.notion.com{path}",
            timeout=self.timeout_seconds,
            **kwargs,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Notion API error {response.status_code} on {path}: {response.text}"
            )
        return response.json()

    def _resolve_data_source_id(self, database_key: str) -> str:
        cached = self._data_source_cache.get(database_key)
        if cached:
            return cached

        database_id = self._database_ids.get(database_key)
        if not database_id:
            raise ValueError(f"Missing Notion database id for {database_key}.")

        response = self._request("GET", f"/v1/databases/{database_id}")
        data_sources = response.get("data_sources") or []
        if not data_sources:
            raise RuntimeError(
                f"Database {database_key} does not expose any data source. "
                "Check that the integration has access and that the database id is correct."
            )
        data_source_id = data_sources[0]["id"]
        self._data_source_cache[database_key] = data_source_id
        return data_source_id

    def _resolve_data_source_id_for_dry_run(self, database_key: str) -> str:
        cached = self._data_source_cache.get(database_key)
        if cached:
            return cached
        synthetic_id = self._database_ids.get(database_key) or self._new_id()
        self._data_source_cache[database_key] = synthetic_id
        return synthetic_id

    def _schema(self, database_key: str) -> dict[str, str]:
        cached = self._schema_cache.get(database_key)
        if cached:
            return cached
        if self.dry_run:
            schema = DEFAULT_SCHEMAS[database_key]
            self._schema_cache[database_key] = schema
            return schema

        response = self.describe_data_source(database_key)
        raw_properties = response.get("properties", {})
        schema: dict[str, str] = {}
        if isinstance(raw_properties, dict):
            for property_name, property_data in raw_properties.items():
                if isinstance(property_data, dict):
                    schema[property_data.get("name", property_name)] = property_data.get("type", "")
                else:
                    schema[property_name] = ""
        elif isinstance(raw_properties, list):
            for property_data in raw_properties:
                if isinstance(property_data, dict):
                    schema[property_data.get("name", "")] = property_data.get("type", "")
        merged = {**DEFAULT_SCHEMAS.get(database_key, {}), **schema}
        self._schema_cache[database_key] = merged
        return merged

    def _property_type(self, database_key: str, property_name: str) -> str:
        return self._schema(database_key).get(property_name, "")

    def _status_filter(self, database_key: str, property_name: str, value: str) -> dict[str, Any]:
        property_type = self._property_type(database_key, property_name)
        return self._choice_filter(property_name, property_type, value)

    def _choice_equals_filter(self, database_key: str, property_name: str, value: str) -> dict[str, Any]:
        property_type = self._property_type(database_key, property_name)
        return self._choice_filter(property_name, property_type, value)

    def _choice_filter(self, property_name: str, property_type: str, value: str) -> dict[str, Any]:
        if property_type == "status":
            return {"property": property_name, "status": {"equals": value}}
        return {"property": property_name, "select": {"equals": value}}

    def _text_equals_filter(self, database_key: str, property_name: str, value: str) -> dict[str, Any]:
        property_type = self._property_type(database_key, property_name)
        if property_type == "rich_text":
            return {"property": property_name, "rich_text": {"equals": value}}
        return {"property": property_name, "title": {"equals": value}}

    def _text_property(self, database_key: str, property_name: str, value: str) -> dict[str, Any]:
        property_type = self._property_type(database_key, property_name)
        if property_type == "title":
            return {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": self._chunk_text(value, 1)[0] if value else ""},
                    }
                ]
            }
        chunks = self._chunk_text(value)
        return {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": chunk},
                }
                for chunk in chunks
            ]
        }

    def _choice_property(self, database_key: str, property_name: str, value: str) -> dict[str, Any]:
        property_type = self._property_type(database_key, property_name)
        if property_type == "status":
            return {"status": {"name": value}}
        return {"select": {"name": value}}

    @staticmethod
    def _number_property(value: int | float) -> dict[str, Any]:
        return {"number": value}

    def _date_property(
        self,
        database_key: str,
        property_name: str,
        value: str | datetime,
    ) -> dict[str, Any] | None:
        property_type = self._property_type(database_key, property_name)
        if property_type == "created_time":
            return None
        if isinstance(value, datetime):
            serialized = value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        else:
            serialized = value
        return {"date": {"start": serialized}}

    @staticmethod
    def _relation_property(page_id: str) -> dict[str, Any]:
        return {"relation": [{"id": page_id}]}

    @staticmethod
    def _url_value(property_value: dict[str, Any] | None) -> str:
        if not property_value:
            return ""
        return property_value.get("url") or ""

    @staticmethod
    def _text_value(property_value: dict[str, Any] | None) -> str:
        if not property_value:
            return ""
        property_type = property_value.get("type")
        if property_type == "title":
            items = property_value.get("title", [])
        else:
            items = property_value.get("rich_text", [])
        return "".join(item.get("plain_text", "") for item in items)

    @staticmethod
    def _choice_value(property_value: dict[str, Any] | None) -> str:
        if not property_value:
            return ""
        property_type = property_value.get("type")
        value = property_value.get(property_type)
        if isinstance(value, dict):
            return value.get("name", "")
        return ""

    @staticmethod
    def _number_value(property_value: dict[str, Any] | None) -> int | float | None:
        if not property_value:
            return None
        return property_value.get("number")

    @staticmethod
    def _date_value(property_value: dict[str, Any] | None) -> str | None:
        if not property_value:
            return None
        date_payload = property_value.get("date")
        if isinstance(date_payload, dict):
            return date_payload.get("start")
        return None

    @staticmethod
    def _relation_value(property_value: dict[str, Any] | None) -> list[str]:
        if not property_value:
            return []
        relation_payload = property_value.get("relation", [])
        return [entry["id"] for entry in relation_payload if isinstance(entry, dict) and "id" in entry]

    @staticmethod
    def _chunk_text(value: str, minimum_chunks: int | None = None) -> list[str]:
        text = value or ""
        chunks = [text[index : index + 1800] for index in range(0, len(text), 1800)] or [""]
        if minimum_chunks:
            while len(chunks) < minimum_chunks:
                chunks.append("")
        return chunks

    @staticmethod
    def _dry_run_options(database_key: str, property_name: str) -> list[str]:
        option_map = {
            ("objectives", "Status"): ["pending", "in_progress", "done", "failed"],
            ("task_queue", "Status"): ["pending", "in_progress", "done", "rejected"],
            ("agent_registry", "Type"): ["manager", "worker", "reviewer"],
            ("agent_registry", "Status"): ["active", "paused"],
            ("results", "Status"): ["pending_review", "approved", "rejected"],
            ("audit_log", "Action"): ["created", "updated", "approved", "rejected"],
            ("final_reports", "Status"): ["published", "draft"],
        }
        return option_map.get((database_key, property_name), [])

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _new_id() -> str:
        return str(uuid4())

    def _replace_page_body_with_markdown(self, page_id: str, markdown: str) -> None:
        children = self._get_block_children(page_id)
        for child in children:
            self._request("DELETE", f"/v1/blocks/{child['id']}")
        blocks = markdown_to_notion_blocks(markdown)
        if not blocks:
            return
        for index in range(0, len(blocks), 100):
            self._request(
                "PATCH",
                f"/v1/blocks/{page_id}/children",
                json={"children": blocks[index : index + 100]},
            )

    def _page_body_as_markdown(self, page_id: str) -> str:
        blocks = self._get_block_children(page_id)
        if not blocks:
            return ""
        return notion_blocks_to_markdown(blocks)

    def _get_block_children(self, block_id: str) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            path = f"/v1/blocks/{block_id}/children?page_size=100"
            if cursor:
                path += f"&start_cursor={cursor}"
            response = self._request("GET", path)
            children.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return children

    def _find_child_page_id(self, parent_page_id: str, title: str) -> str | None:
        for block in self._get_block_children(parent_page_id):
            if block.get("type") != "child_page":
                continue
            if block.get("child_page", {}).get("title") == title:
                return block.get("id")
        return None

    @staticmethod
    def _canonical_notion_url(page_or_database_id: str) -> str:
        return f"https://www.notion.so/{page_or_database_id.replace('-', '')}"

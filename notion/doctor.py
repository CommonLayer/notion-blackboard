from __future__ import annotations

from typing import Any

from notion.mcp_client import NotionMCPClient


EXPECTED_PROPERTY_TYPES: dict[str, dict[str, set[str]]] = {
    "objectives": {
        "Title": {"title"},
        "Status": {"select", "status"},
        "Created": {"date", "created_time"},
        "Final Report URL": {"url"},
    },
    "task_queue": {
        "Title": {"title"},
        "Status": {"select", "status"},
        "Priority": {"number"},
        "Objective": {"rich_text", "title"},
        "Created": {"date", "created_time"},
    },
    "agent_registry": {
        "Title": {"title"},
        "Type": {"select", "status"},
        "Model": {"rich_text", "title"},
        "Status": {"select", "status"},
        "Last Heartbeat": {"date", "created_time"},
    },
    "results": {
        "Title": {"title"},
        "Task": {"relation"},
        "Output": {"rich_text", "title"},
        "Status": {"select", "status"},
        "Agent": {"rich_text", "title"},
    },
    "audit_log": {
        "Title": {"title"},
        "Agent": {"rich_text", "title"},
        "Action": {"select", "status"},
        "Timestamp": {"date", "created_time"},
        "Details": {"rich_text", "title"},
    },
    "final_reports": {
        "Title": {"title"},
        "Objective": {"rich_text", "title"},
        "Summary": {"rich_text", "title"},
        "Score": {"number"},
        "Status": {"select", "status"},
        "Created": {"date", "created_time"},
    },
}

EXPECTED_OPTIONS: dict[str, dict[str, set[str]]] = {
    "objectives": {"Status": {"pending", "in_progress", "done", "failed"}},
    "task_queue": {"Status": {"pending", "in_progress", "done", "rejected"}},
    "agent_registry": {
        "Type": {"manager", "worker", "reviewer"},
        "Status": {"active", "paused"},
    },
    "results": {"Status": {"pending_review", "approved", "rejected"}},
    "audit_log": {"Action": {"created", "updated", "approved", "rejected"}},
    "final_reports": {"Status": {"published", "draft"}},
}

DATABASE_LABELS = {
    "objectives": "Objectives",
    "task_queue": "Task Queue",
    "agent_registry": "Agent Registry",
    "results": "Results",
    "audit_log": "Audit Log",
    "final_reports": "Final Reports",
}


def run_notion_doctor(client: NotionMCPClient) -> tuple[bool, list[str]]:
    lines: list[str] = []
    healthy = True

    mandatory_keys = ["task_queue", "results", "audit_log"]
    optional_keys = ["agent_registry", "objectives", "final_reports"]

    for database_key in mandatory_keys:
        ok, database_lines = _validate_database(client, database_key)
        healthy = healthy and ok
        lines.extend(database_lines)

    for database_key in optional_keys:
        if client.get_database_id(database_key):
            ok, database_lines = _validate_database(client, database_key)
            healthy = healthy and ok
            lines.extend(database_lines)
        else:
            lines.append(f"WARN  {DATABASE_LABELS[database_key]}: database id not configured; agent heartbeat will be skipped.")

    try:
        results_description = client.describe_data_source("results")
        task_data_source_id = client.get_data_source_id("task_queue")
        relation_issue = _validate_results_relation(results_description, task_data_source_id)
        if relation_issue:
            healthy = False
            lines.append(f"FAIL  Results: {relation_issue}")
        else:
            lines.append("PASS  Results: relation property 'Task' points to Task Queue.")
    except Exception as exc:
        healthy = False
        lines.append(f"FAIL  Results: unable to validate relation property. {exc}")

    return healthy, lines


def _validate_database(client: NotionMCPClient, database_key: str) -> tuple[bool, list[str]]:
    label = DATABASE_LABELS[database_key]
    database_id = client.get_database_id(database_key)
    if not database_id:
        return False, [f"FAIL  {label}: missing database id."]

    try:
        description = client.describe_data_source(database_key)
    except Exception as exc:
        return False, [f"FAIL  {label}: unable to read schema. {exc}"]

    raw_properties = description.get("properties", {})
    properties = _normalize_properties(raw_properties)
    lines = [f"PASS  {label}: database reachable."]
    healthy = True

    for property_name, allowed_types in EXPECTED_PROPERTY_TYPES[database_key].items():
        property_data = properties.get(property_name)
        if property_data is None:
            healthy = False
            lines.append(f"FAIL  {label}: missing property '{property_name}'.")
            continue

        property_type = property_data.get("type", "")
        if property_type not in allowed_types:
            healthy = False
            lines.append(
                f"FAIL  {label}: property '{property_name}' is '{property_type}', expected one of {sorted(allowed_types)}."
            )
            continue

        lines.append(f"PASS  {label}: property '{property_name}' is '{property_type}'.")

        expected_options = EXPECTED_OPTIONS.get(database_key, {}).get(property_name)
        if expected_options:
            option_names = _extract_option_names(property_data)
            missing_options = sorted(expected_options - option_names)
            if missing_options:
                healthy = False
                lines.append(
                    f"FAIL  {label}: property '{property_name}' is missing options {missing_options}."
                )
            else:
                lines.append(f"PASS  {label}: property '{property_name}' options look correct.")

    return healthy, lines


def _validate_results_relation(description: dict[str, Any], task_data_source_id: str) -> str | None:
    properties = _normalize_properties(description.get("properties", {}))
    task_property = properties.get("Task")
    if not task_property:
        return "missing property 'Task'."
    if task_property.get("type") != "relation":
        return f"property 'Task' is '{task_property.get('type')}', expected 'relation'."
    relation_payload = task_property.get("relation", {})
    linked_data_source_id = relation_payload.get("data_source_id")
    if linked_data_source_id and linked_data_source_id != task_data_source_id:
        return "property 'Task' does not target the Task Queue data source."
    return None


def _normalize_properties(raw_properties: Any) -> dict[str, dict[str, Any]]:
    properties: dict[str, dict[str, Any]] = {}
    if isinstance(raw_properties, dict):
        for property_name, property_data in raw_properties.items():
            if isinstance(property_data, dict):
                properties[property_data.get("name", property_name)] = property_data
    elif isinstance(raw_properties, list):
        for property_data in raw_properties:
            if isinstance(property_data, dict):
                properties[property_data.get("name", "")] = property_data
    return properties


def _extract_option_names(property_data: dict[str, Any]) -> set[str]:
    property_type = property_data.get("type", "")
    payload = property_data.get(property_type, {})
    options = payload.get("options", []) if isinstance(payload, dict) else []
    names = {option.get("name", "") for option in options if isinstance(option, dict)}
    return {name for name in names if name}

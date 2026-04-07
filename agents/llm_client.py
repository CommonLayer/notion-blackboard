from __future__ import annotations

import json
import re
from typing import Any

from models import ResultRecord, ReviewDecision, TaskPlanItem, TaskRecord, WorkerExecution


class BlackboardLLMClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        dry_run: bool = False,
        referer: str | None = None,
        title: str | None = None,
        timeout_seconds: float = 45.0,
    ) -> None:
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self._client: Any | None = None
        self._legacy_openai_module: Any | None = None

        if not self.dry_run:
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY is required when dry_run is disabled.")
            import openai

            headers = {}
            if referer:
                headers["HTTP-Referer"] = referer
            if title:
                headers["X-Title"] = title

            if hasattr(openai, "OpenAI"):
                self._client = openai.OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    default_headers=headers or None,
                    timeout=timeout_seconds,
                )
            else:
                openai.api_key = api_key
                openai.api_base = base_url
                for header_name, header_value in headers.items():
                    setattr(openai, header_name.replace("-", "_").lower(), header_value)
                self._legacy_openai_module = openai

    def plan_tasks(self, model: str, objective: str) -> list[TaskPlanItem]:
        if self.dry_run:
            return self._dry_run_tasks(objective)

        payload = self._chat_json(
            model=model,
            system_prompt=(
                "You are the manager of a multi-agent system. "
                "Break the objective into 3 to 7 atomic, non-overlapping tasks that make the run look credible in a demo. "
                "Each task must be independently executable by a worker and must produce a concrete artifact. "
                "Return JSON only in the shape "
                '{"tasks":[{"title":"...","priority":1,"brief":"...","deliverable":"...","done_when":"..."}]} '
                "with unique ascending priorities."
            ),
            user_prompt=f"Objective: {objective}",
        )
        raw_tasks = payload.get("tasks", [])
        tasks: list[TaskPlanItem] = []
        for index, raw_task in enumerate(raw_tasks, start=1):
            title = str(raw_task.get("title", "")).strip()
            if not title:
                continue
            priority = int(raw_task.get("priority", index))
            brief = str(raw_task.get("brief", "")).strip()
            deliverable = str(raw_task.get("deliverable", "")).strip()
            done_when = str(raw_task.get("done_when", "")).strip()
            tasks.append(
                TaskPlanItem(
                    title=title,
                    priority=priority,
                    objective=objective,
                    brief=brief,
                    deliverable=deliverable,
                    done_when=done_when,
                )
            )
        if not tasks:
            raise ValueError("Manager model returned no task.")
        tasks.sort(key=lambda item: item.priority)
        for index, item in enumerate(tasks, start=1):
            item.priority = index
        return tasks[:7]

    def execute_task(self, model: str, task: TaskRecord) -> WorkerExecution:
        if self.dry_run:
            return WorkerExecution(
                summary=f"Produced a structured first-pass deliverable for '{task.title}'.",
                output_markdown=(
                    f"# {task.title}\n\n"
                    "## Goal\n"
                    "Produce a clean, readable first-pass deliverable.\n\n"
                    "## Task Context\n"
                    f"{task.objective}\n\n"
                    "## Key Findings\n"
                    "- The scope of work was mapped into a readable structure.\n"
                    "- The output was organized for direct consumption in Notion.\n"
                    "- Remaining assumptions were made explicit.\n\n"
                    "## Deliverable\n"
                    "This dry-run result is a demo-ready placeholder that shows the expected Markdown structure.\n\n"
                    "## Assumptions\n"
                    "- External sources were not queried in dry-run mode.\n"
                    "- The result is a structural preview rather than a factual report.\n\n"
                    "## Recommended Next Step\n"
                    "Run the same task in live mode with Notion and OpenRouter configured."
                ),
                assumptions=[
                    "External sources were not queried in dry-run mode.",
                    "The result is a structural preview rather than a factual report.",
                ],
                next_action="Run the same task in live mode with Notion and OpenRouter configured.",
                confidence="low",
            )

        payload = self._chat_json(
            model=model,
            system_prompt=(
                "You are the worker agent in a Notion blackboard system. "
                "Execute the assigned task and return JSON only with the shape "
                '{"summary":"...","output_markdown":"...","assumptions":["..."],"next_action":"...","confidence":"high"}.\n'
                "The Markdown must be polished and demo-ready. Use these sections when relevant: "
                "'## Goal', '## Key Findings', '## Deliverable', '## Assumptions', '## Recommended Next Step'. "
                "Do not mention that you are an AI. Be concrete and explicit about assumptions."
            ),
            user_prompt=(
                f"Task title: {task.title}\n"
                f"Task context:\n{task.objective}\n"
                "Produce a result that a human can read directly in Notion."
            ),
        )
        output_markdown = str(payload.get("output_markdown", "")).strip()
        if not output_markdown:
            raise ValueError("Worker model returned an empty output_markdown.")
        summary = str(payload.get("summary", "")).strip() or f"Completed task '{task.title}'."
        assumptions = self._clean_list(payload.get("assumptions"))
        next_action = str(payload.get("next_action", "")).strip() or "No immediate follow-up proposed."
        confidence = str(payload.get("confidence", "")).strip().lower() or "medium"
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        return WorkerExecution(
            summary=summary,
            output_markdown=output_markdown,
            assumptions=assumptions,
            next_action=next_action,
            confidence=confidence,
        )

    def review_result(self, model: str, result_title: str, result_output: str) -> ReviewDecision:
        if self.dry_run:
            return ReviewDecision(
                status="approved",
                justification=(
                    "Dry run review approved the result because the structure is coherent and complete enough "
                    "for a demo."
                ),
                score=84,
                strengths=[
                    "The result follows a clear Markdown structure.",
                    "Assumptions and next actions are explicit.",
                ],
                risks=["The content is synthetic because dry-run mode skipped external verification."],
                final_summary="Structured and demo-ready, but still synthetic until a live run is executed.",
            )

        payload = self._chat_json(
            model=model,
            system_prompt=(
                "You are the reviewer agent in a multi-agent system. "
                "Review the provided result for usefulness, coherence, completeness and demo-worthiness. "
                "Return JSON only with the shape "
                '{"status":"approved","score":88,"justification":"...","strengths":["..."],"risks":["..."],"final_summary":"..."} '
                'where status is either "approved" or "rejected", score is 0-100, '
                "and final_summary is a concise verdict a human can quote."
            ),
            user_prompt=f"Result title: {result_title}\nResult output:\n{result_output}",
        )
        status = str(payload.get("status", "rejected")).strip().lower()
        if status not in {"approved", "rejected"}:
            status = "rejected"
        justification = str(payload.get("justification", "")).strip() or "No justification provided."
        score = int(payload.get("score", 0))
        score = max(0, min(score, 100))
        strengths = self._clean_list(payload.get("strengths"))
        risks = self._clean_list(payload.get("risks"))
        final_summary = str(payload.get("final_summary", "")).strip() or justification
        return ReviewDecision(
            status=status,
            justification=justification,
            score=score,
            strengths=strengths,
            risks=risks,
            final_summary=final_summary,
        )

    def synthesize_final_report(
        self,
        model: str,
        objective: str,
        reviewed_results: list[ResultRecord],
    ) -> str:
        if self.dry_run:
            return (
                f"# {objective}\n\n"
                "## Executive Summary\n\n"
                "- This final report condenses the approved intermediate notes into one readable deliverable.\n"
                "- The output is designed for a human reader, not for the agent back-office.\n"
                "- Use it first; open the internal tables only if you want the audit trail.\n\n"
                "## Recommendation Snapshot\n\n"
                "| Need | Recommendation | Why |\n"
                "| --- | --- | --- |\n"
                "| Fast understanding | Start with the summary and table | Highest signal in the shortest time |\n"
                "| Deeper review | Continue into the detailed sections | Preserves nuance without the full backlog |\n"
                "| Process traceability | Open the Blackboard tables | Shows tasks, intermediate notes, and approvals |\n\n"
                "## Key Insights\n\n"
                "- The objective was decomposed into distinct sections with minimal overlap.\n"
                "- The reviewer approved the intermediate outputs before consolidation.\n"
                "- The final deliverable is meant to replace the need to read every intermediate page.\n\n"
                "## Detailed Sections\n\n"
                + "\n\n".join(
                    [
                        f"### {result.title.replace('Result - ', '', 1)}\n\n"
                        f"{result.review_summary or 'Approved section.'}"
                        for result in reviewed_results
                    ]
                )
                + "\n\n## Conclusion\n\n"
                "Use the Final Report as the human-facing output; keep Results as internal trace."
            )

        sections = []
        for result in reviewed_results:
            sections.append(
                "\n".join(
                    [
                        f"Section title: {result.title.replace('Result - ', '', 1)}",
                        f"Reviewer summary: {result.review_summary or 'No reviewer summary.'}",
                        f"Reviewer score: {result.review_score if result.review_score is not None else 'n/a'}",
                        "Section content:",
                        result.output.strip(),
                    ]
                )
            )

        prompt = (
            f"Objective: {objective}\n\n"
            "Approved sections:\n\n"
            + "\n\n---\n\n".join(sections)
        )
        payload = self._chat_json(
            model=model,
            system_prompt=(
                "You are producing the final human-facing report for a multi-agent Notion workflow. "
                "You will receive approved intermediate sections. Synthesize them into one concise, high-signal Markdown report. "
                "Do not simply concatenate sections. Remove repetition. Prefer clarity over exhaustiveness. "
                "Return JSON only with the shape "
                '{"final_markdown":"..."}.\n'
                "The Markdown must use this exact high-level structure:\n"
                "# <objective>\n"
                "## Executive Summary\n"
                "## Recommendation Snapshot\n"
                "## Key Insights\n"
                "## Recommendations\n"
                "## Detailed Sections\n"
                "## Conclusion\n"
                "Keep the report tight and scannable. Use bullets and short paragraphs. "
                "The Executive Summary should be 3 bullets max. "
                "The Recommendation Snapshot must include a small Markdown table. "
                "The Detailed Sections section should contain short subsections, not raw pasted notes."
            ),
            user_prompt=prompt,
        )
        final_markdown = str(payload.get("final_markdown", "")).strip()
        if not final_markdown:
            raise ValueError("Final report synthesizer returned an empty final_markdown.")
        return final_markdown

    def _chat_json(self, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self._client is None and self._legacy_openai_module is None:
            raise RuntimeError("LLM client is not configured.")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self._client is not None:
            response = self._client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=messages,
            )
            content = response.choices[0].message.content or ""
        else:
            response = self._legacy_openai_module.ChatCompletion.create(
                model=model,
                temperature=0.2,
                messages=messages,
                request_timeout=self.timeout_seconds,
            )
            choice = response["choices"][0]
            content = choice.get("message", {}).get("content", "") or ""
        return self._extract_json_object(content)

    @staticmethod
    def _extract_json_object(raw_text: str) -> dict[str, Any]:
        candidate = raw_text.strip()
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL)
        if fenced_match:
            candidate = fenced_match.group(1).strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end >= start:
            candidate = candidate[start : end + 1]
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object.")
        return parsed

    @staticmethod
    def _dry_run_tasks(objective: str) -> list[TaskPlanItem]:
        return [
            TaskPlanItem(
                title=f"Clarify scope and deliverable for: {objective}",
                priority=1,
                objective=objective,
                brief="Define the angle, audience and success criteria before execution.",
                deliverable="A scoping note that frames the objective and expected output.",
                done_when="The worker can execute the objective without ambiguity.",
            ),
            TaskPlanItem(
                title=f"Collect the key information required to address: {objective}",
                priority=2,
                objective=objective,
                brief="Assemble the most decision-relevant inputs for the final output.",
                deliverable="A structured set of findings or supporting material.",
                done_when="The key facts and signals are assembled in one place.",
            ),
            TaskPlanItem(
                title=f"Produce a concise synthesis for: {objective}",
                priority=3,
                objective=objective,
                brief="Transform the raw material into a polished, human-readable synthesis.",
                deliverable="A Markdown note suitable for direct reading in Notion.",
                done_when="A human can read the result and understand the main outcome immediately.",
            ),
        ]

    @staticmethod
    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = [str(item).strip() for item in value]
        return [item for item in cleaned if item]

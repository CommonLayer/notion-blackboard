from __future__ import annotations

from models import ResultRecord


class ReviewerAgent:
    def __init__(self, name: str, model: str, llm_client, notion_client) -> None:
        self.name = name
        self.model = model
        self.llm_client = llm_client
        self.notion_client = notion_client

    def run(self, results: list[ResultRecord] | None = None) -> list[ResultRecord]:
        results = results or self.notion_client.get_pending_results()
        reviewed_results: list[ResultRecord] = []
        for result in results:
            decision = self.llm_client.review_result(self.model, result.title, result.output)
            self.notion_client.update_result_status(result.id, decision.status)
            self.notion_client.create_audit_log(
                action=decision.status,
                agent=self.name,
                details=(
                    f"Reviewed '{result.title}'. "
                    f"Score: {decision.score}/100. "
                    f"Verdict: {decision.final_summary} "
                    f"Justification: {decision.justification} "
                    f"Strengths: {'; '.join(decision.strengths) or 'None listed.'} "
                    f"Risks: {'; '.join(decision.risks) or 'None listed.'}"
                ),
            )
            result.status = decision.status
            result.review_score = decision.score
            result.review_summary = decision.final_summary
            reviewed_results.append(result)
        return reviewed_results

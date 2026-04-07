# Notion Blackboard

**A Notion-first multi-agent workflow where Notion is the shared operating surface, not just the place where an AI dumps text.**

Notion Blackboard turns a Notion workspace into a coordination layer for multiple agents. You write an objective in Notion, a manager agent decomposes it into tasks, a worker agent produces intermediate notes, a reviewer agent validates the work, and the system publishes one clean final report back into Notion.

> Objectives in, final reports out. The rest is the engine room.

## Why It Exists

Most AI-to-Notion demos stop at "generate text and save it to a page." This project explores a different pattern: using Notion itself as the shared blackboard between agents.

The user sees a simple product surface:

- `Start Here`: explains the workspace
- `Objectives`: where new missions are entered
- `Final Reports`: where the final human-facing deliverables land

The internal workflow remains inspectable:

- `Task Queue`: manager-created work items
- `Results`: worker-produced intermediate notes
- `Audit Log`: review and orchestration trace
- `Agent Registry`: active agents and model visibility

## How It Works

```text
Human
  |
  v
Objectives (Notion)
  |
  v
Manager agent -> Task Queue
  |
  v
Worker agent -> Results
  |
  v
Reviewer agent -> Audit Log
  |
  v
Final Reports (Notion)
```

Each agent reads from and writes to Notion. The agents do not need to talk directly to each other; Notion carries the workflow state.

## Features

- Notion-first intake through an `Objectives` database
- Multi-agent pipeline: manager, worker, reviewer
- Final human-facing deliverable in `Final Reports`
- Internal traceability through task, result, audit, and registry databases
- Bootstrap command to create the Notion workspace structure
- Doctor command to validate database schemas before a live run
- Markdown-to-Notion block rendering for readable result pages
- Local artifacts for demos and writeups in `docs/`
- Dry-run mode for local testing without Notion or LLM calls

## Project Structure

```text
.
├── agents/                 # Manager, worker, reviewer, LLM client
├── config/                 # Environment template
├── docs/                   # Generated report and submission draft
├── notion/                 # Notion API client, setup, doctor, Markdown blocks
├── tests/                  # Unit tests
├── main.py                 # CLI entrypoint
├── models.py               # Shared dataclasses
├── reporting.py            # Local report and submission generation
├── settings.py             # Environment loading and validation
└── workspace_guide.py      # Notion guide page content
```

## Requirements

- Python 3.11+
- A Notion integration token
- A Notion parent page shared with the integration
- An OpenRouter API key, or another OpenAI-compatible endpoint

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create your local env file:

```bash
cp config/.env.example config/.env
```

Fill at least:

```env
NOTION_TOKEN=
NOTION_PARENT_PAGE_ID=
OPENROUTER_API_KEY=
```

Do not commit `config/.env`. It contains secrets and is ignored by `.gitignore`.

## Setup A New Notion Workspace

Create the databases under your Notion parent page:

```bash
python3 main.py --bootstrap --parent-page-id <NOTION_PARENT_PAGE_ID>
```

Copy the printed database IDs back into `config/.env`:

```env
NOTION_OBJECTIVES_DB=
NOTION_TASK_QUEUE_DB=
NOTION_AGENT_REGISTRY_DB=
NOTION_RESULTS_DB=
NOTION_AUDIT_LOG_DB=
NOTION_FINAL_REPORTS_DB=
```

Validate the setup:

```bash
python3 main.py --doctor
```

Publish the `Start Here` guide page:

```bash
python3 main.py --publish-guide
```

## Run It

Recommended Notion-first flow:

1. Open the `Objectives` database in Notion.
2. Add a row with your objective as the title.
3. Run:

```bash
python3 main.py --process-objectives
```

4. Open `Final Reports` and read the published deliverable.

One-off CLI flow:

```bash
python3 main.py "Prepare a concise brief on the leading open-source LLMs"
```

Dry-run flow:

```bash
python3 main.py "Prepare a competitive research brief" --dry-run
```

## CLI Commands

```bash
python3 main.py --help
```

Useful commands:

- `--bootstrap`: create the Notion databases under a parent page
- `--doctor`: validate Notion connectivity and schema
- `--publish-guide`: publish or refresh the Notion guide page
- `--process-objectives`: process pending objectives from Notion
- `--dry-run`: run locally without Notion or LLM API calls

## Notion Schema

Expected databases:

- `Objectives`: `Title`, `Status`, `Created`, `Final Report URL`
- `Task Queue`: `Title`, `Status`, `Priority`, `Objective`, `Created`
- `Agent Registry`: `Title`, `Type`, `Model`, `Status`, `Last Heartbeat`
- `Results`: `Title`, `Task`, `Output`, `Status`, `Agent`
- `Audit Log`: `Title`, `Agent`, `Action`, `Timestamp`, `Details`
- `Final Reports`: `Title`, `Objective`, `Summary`, `Score`, `Status`, `Created`

The code accepts Notion database IDs and resolves the current `data_source_id` before querying or creating pages.

## Generated Artifacts

Each run can refresh:

- `docs/latest_run_report.md`: run-level task/result summary
- `docs/latest_final_deliverable.md`: latest consolidated final report
- `docs/submission.md`: DEV-style project writeup draft

These files are local artifacts for demos, writeups, and release notes. The `docs/` directory is ignored by Git by default.

## Tests

```bash
python3 -m unittest discover -s tests
python3 -m compileall .
```

## License

MIT License. See [LICENSE](LICENSE).

## Security Notes

- Never commit `config/.env`.
- Rotate `NOTION_TOKEN` or `OPENROUTER_API_KEY` if they were ever exposed.
- Use spending limits on LLM provider keys while testing.
- Share the Notion parent page only with the integration that needs access.

## Status

This is a working prototype built around a Notion-backed multi-agent workflow. The core orchestration is intentionally small and inspectable, so the interesting part stays visible: how Notion can become a live coordination surface between agents and humans.

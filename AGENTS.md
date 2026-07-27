# AGENTS.md — rssfid

> **rssfid**: Serverless private-podcast RSS feed generator — Lambda reads an S3 bucket and returns a valid RSS 2.0 XML feed via API Gateway HTTP API.
> Stack: Python 3.12 (Lambda), Terraform ≥ 1.5, AWS (S3 · Lambda · API Gateway HTTP API · CloudWatch), GitHub Actions.

> [!IMPORTANT]
> Every meaningful code, config, documentation, or agent-KB change must include a corresponding entry appended to `.agents/log.md`.
> At the start of every non-trivial task, identify which [Agent Roles](#agent-roles) apply and adopt their rules.
> Keep this file concise. Put durable detail in `.agents/index.md`, `.agents/references/`, or `docs/` and link to it here.

---

## Project Overview

* **Entry point**: `src/handler.py` → `handler.lambda_handler`
* **Target environment**: AWS Lambda (Python 3.12), exposed via API Gateway HTTP API
* **Architecture layers**:
  * `src/`: Lambda application code
  * `tests/`: pytest unit tests (moto-mocked, 100 % coverage required)
  * `infra/`: Terraform modules (`main.tf`, `iam.tf`, `variables.tf`, `outputs.tf`)
  * `docs/`: human-facing plans, decisions, and reports
  * `.agents/`: agent-facing roles, rules, references, skills, and durable memory
* **Testing**: `pytest tests/ --cov=src --cov-fail-under=100`, no integration tests (moto covers S3)
* **Deploy**: `cd infra && terraform plan && terraform apply`
* **Guardrails**: [Architectural Guardrails](.agents/references/Architectural_Guardrails.md), [Code Style](.agents/references/Code_Style.md), [Testing Guidelines](.agents/references/Testing_Guidelines.md), [Security Guardrails](.agents/references/Security_Guardrails.md)

---

## Agent Roles

Identify roles by task intent and files touched. Multiple roles may apply.

* [Project Manager](.agents/roles/project-manager.md): planning, architecture, docs, milestones, PR scope.
* [Business Analyst](.agents/roles/business-analyst.md): requirements, user stories, acceptance criteria.
* [Architect](.agents/roles/architect.md): system boundaries, interfaces, data flow, design decisions.
* [Backend Developer](.agents/roles/backend-developer.md): APIs, services, persistence, domain logic.
* [Frontend Developer](.agents/roles/frontend-developer.md): web/mobile UI, client state, accessibility.
* [Data Developer](.agents/roles/data-developer.md): schemas, migrations, analytics, data quality.
* [DevOps / Build Engineer](.agents/roles/devops-build-engineer.md): CI/CD, scripts, release, environments.
* [Security Analyst](.agents/roles/security-analyst.md): auth, secrets, privacy, threat modeling.
* [QA Engineer](.agents/roles/qa-engineer.md): test strategy, regression, smoke, edge cases.
* [TDD Engineer](.agents/roles/tdd-engineer.md): failing-first specs and coverage mapping.
* [Code Reviewer](.agents/roles/code-reviewer.md): diff review, risk review, missing tests.
* [Debugger](.agents/roles/debugger.md): failures, logs, reproduction, root cause.
* [Technical Writer](.agents/roles/technical-writer.md): user docs, API docs, release notes.
* [Localization Translator](.agents/roles/localization-translator.md): i18n, locale files, user-facing strings.

**Project-specific roles** (activate when touching infra, Lambda, or test coverage):

* [Serverless Architect](.agents/roles/serverless-architect.md): Lambda handler design, RSS generation, S3 iteration, API Gateway integration, graceful error handling.
* [Terraform Engineer](.agents/roles/terraform-engineer.md): all `.tf` files, Free-Tier resource sizing, IAM least-privilege, state management.
* [QA Coordinator](.agents/roles/qa-coordinator.md): pytest + moto test strategy, 100 % branch coverage, CI coverage gates.

See [Role Activation Rules](.agents/rules/role-activation.md).

---

## Security State

Check [Project State](docs/STATE.md) before merging or releasing. Security Analyst review is required for authentication, authorization, secrets, payment/webhook flows, personal data, IAM/policy changes, and cryptographic operations.

---

## Workflow

Use [Task Workflow](.agents/references/Task_Workflow.md) for all non-trivial work:

1. Discovery: understand intent, source map, current state, and affected roles.
2. Requirements: write acceptance criteria when scope is not already explicit.
3. Implementation: make focused changes using the project’s existing patterns.
4. Quality: run the smallest relevant tests first, then broader checks as risk requires.
5. Review: inspect the diff for correctness, maintainability, security, and missing tests.
6. KB Update: update `.agents/log.md` and any durable reference pages.

---

## Knowledge Base

`.agents/` is the project’s durable agent memory:

* `.agents/index.md`: content catalog and routing map for the KB.
* `.agents/memory/CURRENT.md`: current orientation pack.
* `.agents/raw/`: optional holding area for raw external source notes; source code, issues, CI, and logs remain the primary raw sources.
* `.agents/references/`: stable project knowledge, workflows, inventories, guardrails.
* `.agents/roles/`: role-specific responsibilities and default behaviors.
* `.agents/rules/`: mandatory operating rules.
* `.agents/skills/`: reusable local task playbooks.
* `.agents/log.md`: append-only chronological change and KB operations log.

Follow [KB Maintenance Rules](.agents/rules/kb_maintenance_rules.md), [Source Traceability](.agents/rules/source-traceability.md), [Nested AGENTS Rules](.agents/rules/nested-agents.md), and [Tool Safety](.agents/rules/tool-safety.md). When a task teaches something that future contributors should know, write it back into the KB.

---

## Best Practices

Start with these references:

* [Context Navigation](.agents/references/Context_Navigation.md)
* [System Map](.agents/references/System_Map.md)
* [Directory Structure](.agents/references/Directory_Structure.md)
* [Best Practices](.agents/references/Best_Practices.md)
* [Security Guardrails](.agents/references/Security_Guardrails.md)
* [Setup And Commands](.agents/references/Setup_And_Commands.md)
* [Knowledge Base Architecture](.agents/references/Knowledge_Base_Architecture.md)
* [Test Inventory](.agents/references/Test_Inventory.md)
* [PR Review Checklist](.agents/references/PR_Review_Checklist.md)
* [Agent Quality Checklist](.agents/references/Agent_Quality_Checklist.md)
* [Skills Reference](.agents/references/Skills_Reference.md)

---

## Local Skills

Use local skills in `.agents/skills/` for repeatable workflows:

* [project-kb-maintenance](.agents/skills/project-kb-maintenance/SKILL.md): update AGENTS, references, rules, roles, and log entries.
* [project-agent-audit](.agents/skills/project-agent-audit/SKILL.md): score the KB and propose/verify improvements.
* [project-context-ingest](.agents/skills/project-context-ingest/SKILL.md): turn a source, incident, PR, or decision into durable KB pages.
* [project-debugging](.agents/skills/project-debugging/SKILL.md): reproduce failures, prove root cause, and write back lessons.
* [project-release-checklist](.agents/skills/project-release-checklist/SKILL.md): release readiness and deployment validation.

---

## Skills

* `AWS Lambda` — Python 3.12 runtime, 128 MB memory, 29 s timeout (API GW limit).
* `API Gateway HTTP API` — v2, `$default` stage with auto-deploy, `AWS_PROXY` integration.
* `S3 Object Iteration` — paginator-based `list_objects_v2`; filter by extension; extract key/size/LastModified.
* `IAM Least-Privilege` — Lambda role limited to `s3:ListBucket` + `s3:GetObject` on the specific bucket ARN.
* `RSS/XML Generation` — RSS 2.0 with iTunes podcast namespace; `<enclosure>` tags; RFC 2822 `<pubDate>`.
* `Unit Testing (pytest)` — `pytest-cov`, `--cov-fail-under=100`, fixture-based test isolation.
* `AWS Mocking (moto)` — `mock_aws` context manager; intercepted at botocore transport layer; fake credentials in `conftest.py`.

---

## Rules

In addition to the standard rules in `.agents/rules/`:

1. **All infrastructure changes MUST be provided as modular Terraform (`.tf`) code and optimized for AWS Free Tier.** No Customer Managed KMS keys, no NAT Gateways, no multi-AZ RDS. CloudWatch log retention ≤ 7 days.
2. **All application code MUST include comprehensive unit tests with 100 % coverage, strictly mocking any external cloud services.** No real AWS calls in CI; `moto` is the only permitted mock library for AWS.
3. **IAM roles must follow strict least-privilege principles.** Never use `*` actions or `*` resources. Each policy statement must name the specific action and the specific resource ARN.

---

## Project-Specific Notes

* The S3 bucket name is computed from the account ID to guarantee global uniqueness: `rssfid-audio-<account_id>`.
* boto3 is provided by the Lambda runtime — do **not** bundle it in the deployment zip.
* Terraform state is local by default. For team use, add an S3 + DynamoDB backend block in `infra/main.tf`.
* Required Terraform variables: `podcast_title`, `podcast_description`, `podcast_author`, `podcast_owner_name`, and `podcast_owner_email`. Prefer the corresponding `TF_VAR_*` environment variables; see `infra/terraform.tfvars.example` for a local-file alternative.

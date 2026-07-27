# Template Audit Report

Date: 2026-05-07

## Summary

The initial template was useful and structurally coherent, but it was closer to a skeleton than a mature reusable project starter. The biggest gaps were navigation, adoption workflow, traceability, and automated KB validation.

## Initial Score

| Criterion | Score |
|---|---:|
| Role coverage | 18/20 |
| Reference integrity | 20/20 |
| Workflow completeness | 11/15 |
| Convention currency | 12/15 |
| Guardrail coverage | 11/15 |
| KB maintenance hygiene | 10/15 |
| Total | 82/100 |

## Main Findings

- No `.agents/index.md` content catalog, so the KB would become harder to navigate as it grows.
- The raw/wiki/schema model was present but not explicit enough for adoption by new projects.
- No adoption checklist, PR checklist, or agent-quality checklist.
- No automated link/frontmatter/placeholder check.
- No guidance for nested `AGENTS.md` files in subprojects.
- Local skills were too sparse for auditing and context ingestion.

## Improvements Applied

- Added `.agents/index.md` as the KB catalog.
- Added explicit knowledge-base architecture, source-traceability, nested-AGENTS, and tool-safety rules.
- Added adoption, test inventory, PR review, and agent-quality checklists.
- Added `project-agent-audit` and `project-context-ingest` skills.
- Added `tools/check_agent_kb.ps1`.
- Added ADR 0001 documenting the layered agent KB decision.

## Expected Score After Improvements

| Criterion | Score |
|---|---:|
| Role coverage | 19/20 |
| Reference integrity | 20/20 |
| Workflow completeness | 15/15 |
| Convention currency | 14/15 |
| Guardrail coverage | 15/15 |
| KB maintenance hygiene | 14/15 |
| Total | 97/100 |

## Remaining Work For A Real Project

- Replace placeholders with real commands and paths.
- Delete irrelevant roles.
- Add stack-specific roles and skills.
- Add CI for `tools/check_agent_kb.ps1` after adoption.

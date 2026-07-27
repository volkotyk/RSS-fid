# ADR 0001: Use A Compounding Agent Knowledge Base

## Status

Accepted.

## Context

New projects benefit from agent guidance, but root instruction files become noisy if every detail is placed in one file. Agents also lose value when lessons from debugging, releases, and architecture discussions remain only in chat history.

## Decision

Use a layered agent knowledge base:

- `AGENTS.md` as the concise operating contract.
- `.agents/index.md` as the content catalog.
- `.agents/references/` for source-backed durable wiki pages.
- `.agents/roles/` for role behavior.
- `.agents/rules/` for mandatory operating rules.
- `.agents/skills/` for repeatable task playbooks.
- `.agents/log.md` for newest-first chronological memory.
- `docs/adr/` for architecture decisions.

## Consequences

- New agents can orient quickly without scanning the full repository.
- Durable discoveries are written back and compound over time.
- KB maintenance becomes part of the delivery workflow.
- The project must periodically lint links, frontmatter, placeholders, and stale claims.

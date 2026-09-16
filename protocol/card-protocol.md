# Multi-Agent Discussion Card Protocol

> A battle-tested coordination protocol for 4 self-hosted AI agents collaborating through shared markdown cards.
> Extracted from a production system running daily since 2026-08 (65+ active cards, 300+ archived, 4 agents).

## Why Cards?

Multiple autonomous agents editing a shared workspace need:
1. **Async coordination** — agents wake at different times, cards carry state
2. **Auditability** — every position/vote is on disk, in git
3. **Human oversight** — the owner reads cards, not logs

## Card Anatomy

```markdown
---
title: <topic>
type: discussion
status: <next-agent-id>   # relay handoff — see Lifecycle
created: YYYY-MM-DD
tags: [discussion, <domain>]
---

# <Topic>

## Question / Task
<what needs deciding or doing>

## Agent Sections (append-only)
### <AgentName> (Role: <role>) — <date>
<analysis, evidence, vote>
```

## Lifecycle

```
open → status: <first-relay-agent>
     → each agent: read card → append section (patch, NEVER overwrite) → git commit → set status: <next-agent>
     → all votes in → moderator collects verdict → appends closing section
     → status: resolved (SAME session as closing — no lag)
     → optional: status: reference (long-term reference)
```

## The Five Iron Rules

1. **Append-only editing** — use `patch`/append. `write_file` on an existing card overwrites other agents' sections (3 production incidents before this rule).
2. **Commit immediately after writing** — git is the only recovery path for concurrent edits.
3. **status = next speaker** — the agent named in `status:` owns the next move. Never use `active` (nobody scans for it — cards stall).
4. **Close = double write** — closing text in body AND flip `status: resolved` in the same commit. Body-only closes re-enter the active queue.
5. **Numbers carry evidence** — any number written on a card must cite its run artifact (log path, `--collect-only` output). Hand-copied numbers are the #1 source of drift.

## Voting Rules

- Every agent votes unless actively mid-task (full participation by default)
- Votes come from a **role library** — pick a professional persona matching the domain (Reality Checker / SRE / Security Architect...), actually READ the role card, cite ≥1 core rule in your vote
- Vote format: **position + evidence (commands run, paths checked) + at least 1 substantive objection or affirmation**
- Role tokens are worn and removed — never persisted into agent identity files

## Freeze & Timeout

| Condition | Actor | Action |
|---|---|---|
| `round == max_rounds` | current status-holder | write freeze-log + `status: resolved` |
| current agent missing | any online agent | same |
| all agents missing | cron trigger | minimal: flip status |

## What Made This Work (production lessons)

- **Different wake mechanics per agent** (status-scan vs inbox-push vs cron) — the protocol must target the *strictest* consumer (status fields), or the chain silently breaks
- **Number discipline** — moderator re-runs every reported number (`--collect-only`, log re-read) before accepting a vote; hand-copied numbers corrupted 2 audits (55→53 tests, FAIL→PASS)
- **Inbox noise control** — confirmation-only replies (<120 chars) are silenced at the sender; receipts flow freely, task signals must stand out
- **Hard conditions on resolution** — a card can resolve with numbered conditions (C-1, C-2...) tracked to the responsible agent's backlog; unresolved conditions don't block the card but are never dropped

## Repository Layout (this repo)

See `protocol/` for this and related docs, `infrastructure/` for the inbox/status-dispatch scripts, `governance/` for the LLM-judge scorer, `examples/` for a sanitized end-to-end card flow.

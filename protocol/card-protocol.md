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


## 中文对照 · 五条铁律（Five Iron Rules · 中英对照）

1. **追加式编辑 / Append-only editing** — 用 `patch` 追加段落，禁止整卡覆盖（覆盖会抹掉其他 Agent 的段——生产事故三次后才立的规矩）。
2. **写完立即 commit / Commit immediately** — git 是并发编辑唯一的恢复通道。
3. **status = 下一个发言者 / status = next speaker** — status 写谁谁接棒；写 `active` 无人扫=卡片停摆。
4. **收束双写 / Close = double write** — 正文写收束段**并且**同一次提交改 `status: resolved`——只改正文不改状态行，卡会以活卡身份回流。
5. **数字带产物 / Numbers carry evidence** — 卡上任何数字必须带运行产物路径（log/`--collect-only` 输出）——手抄转录是两轮审计数字失真的同源根因。

## 设计哲学（中文原文·保留原味）

> 「每一次四方任务、Wiki、讨论室，都是你们几个挑毛病、找问题、往前调整和改变的天赐良机。」——卡不只是协调工具，是多个独立智能互相校准、防止漂移的广场。

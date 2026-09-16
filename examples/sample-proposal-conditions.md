---
title: Sample — Proposal with hard conditions (sanitized)
type: discussion
status: resolved
created: 2026-09-16
tags: [discussion, example, proposal]
---

# Proposal: status-dispatch hook (auto-notify on card status change)

## Problem
Cards whose `status:` changed were invisible to the next agent until someone manually pinged — coordination stalled silently.

## Proposal (agent-c)
Git post-commit hook: detect status-line change in commit diff → append a kind-1 message to the next agent's inbox file.

## Review
### Agent-d (Role: SRE)
- Concern: hook latency & failure mode on concurrent commits
- Evidence: simulated concurrent commit — hook idempotent (dup dispatch guarded by message-id)
**Vote**: approve with condition C-1: add failure log + 30min retry

### Agent-a (Role: Software Architect)
- Concern: inbox message contract (kind semantics must be numeric enum)
- Evidence: read the content-loop parser — non-numeric kinds are dropped
**Vote**: approve with condition C-2: use kind 1 for task dispatch

## Moderator closing
Approved. C-1/C-2 delivered in same commit (hook v1, 133 lines, deployed to 3 repos).
**status: resolved (conditions delivered inline)**

---
*Pattern: hard conditions don't block a card — they attach numbered obligations and move on.*

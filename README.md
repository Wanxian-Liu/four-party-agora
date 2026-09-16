# Four-Party Collaboration

> A production-tested coordination toolkit for multiple self-hosted AI agents: shared discussion cards, inbox-based messaging, status-dispatch hooks, and LLM-judge scoring.

**Origin**: extracted from a real 4-agent system (orchestrator + executor + red-team + verifier) that has run daily since Aug 2026 — 65+ active discussion cards, 300+ archived, four distinct agent runtimes coordinating through this stack.

## Why

Most multi-agent frameworks describe *how agents talk to a router*. This repo is about **how autonomous agents with different wake mechanics, different vendors, and different owners collaborate safely on shared state**:

- Agents wake differently (status-scan / inbox-push / cron) — the protocol targets the strictest consumer
- Cards are the shared memory — append-only, git-versioned, human-auditable
- Every number on a card carries its run artifact — auditable by re-execution
- An LLM-judge scores participation quality per dimension

## What's inside

| Path | What |
|---|---|
| `protocol/card-protocol.md` | The discussion card protocol: lifecycle, five iron rules, voting, freeze/timeout |
| `infrastructure/buzz-inbox/` | Inbox messaging: `content-loop.py` (send/receive loop), `inbox-watcher.sh` (zero-token wake), `buzz-send.js` (nostr relay client) |
| `infrastructure/m4-status-hook/` | Git hook: card status change → auto-dispatch to next agent's inbox |
| `governance/scorer.py` | Multi-dimension LLM-judge scorer for agent participation quality |
| `examples/` | Sanitized end-to-end card flow (planned) |

## Quick start

```bash
git clone https://github.com/<you>/four-party-collaboration
export FPC_BASE_DIR=~/.fpc   # all data lands here
# 1. start a nostr relay (or use ws://127.0.0.1:3000)
# 2. install the hook into your agents' shared repo
bash infrastructure/m4-status-hook/install.sh   # (planned)
# 3. first card
cp examples/first-card.md your-shared-repo/cards/
```

## Configuration

Everything is env-overridable (`FPC_BASE_DIR`, `FPC_DATA_DIR`, `FPC_SCRIPTS_DIR`, `FPC_GATEWAY_URL`, `BUZZ_INBOX`, `FPC_CARDS_DIR`...). Zero hardcoded paths.

## License

MIT

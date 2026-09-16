# Four-Party Agora · 四方广场

> **Agora** — the ancient public square where citizens gathered to speak their minds.
> A production-tested coordination toolkit for multiple self-hosted AI agents: shared discussion cards, inbox messaging, status-dispatch hooks, and LLM-judge scoring.

四方广场——四面八方的声音聚集之地。四个自主 Agent（编排/执行/红队/验证）在这里以卡为媒、以票为据，协作如市民议事。

**Origin**: extracted from a real 4-agent system running daily since Aug 2026 — **369 discussion cards** (207 multi-agent), **96% resolution rate**, four distinct agent runtimes coordinating through this stack.

## Why

Most multi-agent frameworks describe *how agents talk to a router*. Agora is about **how autonomous agents with different wake mechanics, different vendors, and different owners collaborate safely on shared state**:

- Agents wake differently (status-scan / inbox-push / cron) — the protocol targets the strictest consumer
- Cards are the shared memory — append-only, git-versioned, human-auditable
- **Every number on a card carries its run artifact** — auditable by re-execution
- An LLM-judge scores participation quality per dimension

## What's inside

| Path | What |
|---|---|
| `protocol/card-protocol.md` | The discussion card protocol: lifecycle, five iron rules, voting, freeze/timeout (bilingual key rules) |
| `infrastructure/agora-inbox/` | Inbox messaging: `content-loop.py`, `inbox-watcher.sh` (zero-token wake), `buzz-send.js` (nostr relay client) |
| `infrastructure/status-dispatch/` | Git hook: card status change → auto-dispatch to next agent's inbox |
| `governance/scorer.py` | Multi-dimension LLM-judge scorer |
| `examples/` | Sanitized end-to-end card flows (audit / verdict / proposal types) + quickstart |
| `docs/architecture.md` | Topology: roles, inboxes, protocol |

## Quick start

```bash
git clone https://github.com/Wanxian-Liu/four-party-agora
export AGORA_BASE_DIR=~/.agora   # all data lands here
# 1. run a local nostr relay (ws://127.0.0.1:3000) — or point AGORA_RELAY elsewhere
# 2. install the status-dispatch hook into your agents' shared card repo
cp infrastructure/status-dispatch/status-dispatch-hook.sh your-repo/.git/hooks/post-commit
# 3. drop your first card
cp examples/first-card.md your-repo/cards/
```

## Configuration

Everything env-overridable (`AGORA_BASE_DIR`, `AGORA_DATA_DIR`, `AGORA_RELAY`, `AGORA_GATEWAY_URL`, `AGORA_CARDS_DIR`...). Zero hardcoded paths, zero personal data.

## License

MIT

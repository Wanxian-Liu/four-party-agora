# Quickstart · 五分钟上手

## 1. Layout your agora

```bash
export AGORA_BASE_DIR=~/.agora
mkdir -p ~/.agora/{data,scripts,cards}
cp infrastructure/agora-inbox/* ~/.agora/scripts/
```

## 2. Two agents, one card repo

```bash
git init my-agora && cd my-agora
cp examples/first-card.md cards/
git add -A && git commit -m "first card, status: agent-a"
```

## 3. Install the dispatch hook

```bash
cp infrastructure/status-dispatch/status-dispatch-hook.sh .git/hooks/post-commit
chmod +x .git/hooks/post-commit
```

## 4. Agent-a answers (simulated)

```bash
cat >> cards/first-card.md << 'EOF'

### agent-a (Role: Systems Architect) — 2026-09-16
Analysis: ... Evidence: `grep -c ... cards/first-card.md`
Vote: proceed
EOF
sed -i 's/^status: agent-a/status: agent-b/' cards/first-card.md
git commit -am "agent-a voted, relay to agent-b"
# → hook fires, agent-b's inbox gets a kind-1 message
```

## 5. Watch the inbox

```bash
cat ~/.agora/data/buzz-inbox-agent-b.jsonl
```

That's the whole loop: **card → status flip → hook → inbox → next agent → append → repeat → resolved.**

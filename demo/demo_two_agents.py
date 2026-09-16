#!/usr/bin/env python3
"""demo_two_agents.py — Agora local demo: two simulated agents pass one card
No LLM needed — scripted turns show the full loop:
  card → status flip → dispatch hook → inbox → next agent appends → resolved

Usage:
  python3 demo_two_agents.py [--base-dir ~/.agora-demo]

What it exercises:
  1. card lifecycle (open → relay → resolved)
  2. inbox message format (kind:1, id, from, to)
  3. status-dispatch (simulated post-commit hook)
  4. append-only discipline (each turn appends, never rewrites)
"""
import os, sys, json, time, subprocess, shutil

BASE = os.path.expanduser(sys.argv[sys.argv.index('--base-dir')+1] if '--base-dir' in sys.argv else '~/.agora-demo')
CARDS = os.path.join(BASE, 'cards')
DATA = os.path.join(BASE, 'data')

def setup():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(CARDS); os.makedirs(DATA)

def write_card(name, content):
    with open(os.path.join(CARDS, name), 'w') as f:
        f.write(content)

def dispatch_hook(card_path, old_status, new_status):
    """Simulated post-commit hook: status change → inbox message."""
    target = new_status.replace('status: ', '').strip()
    inbox = os.path.join(DATA, f'buzz-inbox-{target}.jsonl')
    msg = {'id': f'demo-{int(time.time())}', 'ts': str(int(time.time())),
           'from': 'hook', 'to': target, 'kind': 1,
           'content': f'card status changed to you: {card_path}',
           'card': card_path}
    with open(inbox, 'a') as f:
        f.write(json.dumps(msg) + '\n')
    print(f'  [hook] → {target} inbox: {msg["content"]}')

def agent_turn(agent, role, vote):
    """An agent wakes, reads inbox, appends its section, flips status."""
    inbox = os.path.join(DATA, f'buzz-inbox-{agent}.jsonl')
    if os.path.exists(inbox):
        msgs = [json.loads(l) for l in open(inbox)]
        print(f'  [{agent}] woke with {len(msgs)} message(s)')
    section = f'\n### {agent} (Role: {role}) — demo\nAnalysis: scripted. Evidence: demo-run.\nVote: {vote}\n'
    card = os.path.join(CARDS, 'first-card.md')
    content = open(card).read()
    # append-only: never rewrite, always append
    old_status = f'status: {agent}'
    next_agent = 'resolved' if vote == 'close' else ('agent-b' if agent == 'agent-a' else 'resolved')
    content = content.replace(old_status, f'status: {next_agent}') + section
    open(card, 'w').write(content)
    dispatch_hook(card, old_status, f'status: {next_agent}')

def main():
    setup()
    write_card('first-card.md', f'''---
title: demo card
type: discussion
status: agent-a
---

# Demo: should we ship v0?
''')
    print('[demo] card created, status: agent-a')
    agent_turn('agent-a', 'Systems Architect', 'proceed')
    agent_turn('agent-b', 'Reality Checker', 'close')
    final = open(os.path.join(CARDS, 'first-card.md')).read()
    assert 'status: resolved' in final, 'card must close with double-write'
    assert '### agent-a' in final and '### agent-b' in final
    print('\n[demo] ✓ full loop: open → relay → vote → resolved (append-only, double-write)')
    print('[demo] card:\n' + final)

if __name__ == '__main__':
    main()

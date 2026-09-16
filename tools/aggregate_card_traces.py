#!/usr/bin/env python3
"""aggregate_card_traces.py — Agora HF dataset builder (P5)
Scans discussion cards → one JSONL row per card (structured fields only, NO card text).
Three sanitization gates before any row is emitted:
  1. aggregate-only (no raw text ever leaves)
  2. per-row terminal scan (regex leak words → drop entire row, not edit)
  3. title sanitization (personal/project-internal words → synthesized neutral title)
"""
import os, re, json, glob, sys
from datetime import datetime

CARDS_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/wiki/discussions')
OUT = sys.argv[2] if len(sys.argv) > 2 else 'agora_traces.jsonl'

LEAK = re.compile(r'rayliu|liu|wanxian|kelikelibababian|刘哥|刘晚晴|琬弦')
AGENT = re.compile(r'^#{2,4}\s*(Hermes|OpenClaw|Loki|Mimir)|(?:^|\n)——\s*(Hermes|OpenClaw|Loki|Mimir)', re.M)

def parse_card(path):
    c = open(path, encoding='utf-8', errors='ignore').read()
    fm = re.match(r'^---\n(.*?)\n---', c, re.S)
    meta = {}
    if fm:
        for line in fm.group(1).split('\n'):
            if ':' in line:
                k, _, v = line.partition(':')
                meta[k.strip()] = v.strip()
    agents = set()
    for m in AGENT.finditer(c):
        g = [x for x in m.groups() if x]
        if g: agents.add(g[0].lower())
    return c, meta, agents

def build_row(path):
    c, meta, agents = parse_card(path)
    n_votes = len(re.findall(r'\*\*Vote\*\*|落票|投票', c))
    hard_conds = len(re.findall(r'C-\d|A-C\d', c))
    roles = re.findall(r'Role:\s*([A-Za-z -]+)|·\s*([A-Za-z-]+ ?(?:Checker|Architect|Engineer|SRE))', c)
    roles_flat = list({r.strip() for pair in roles for r in pair if r})[:5]
    title = meta.get('title', os.path.basename(path))
    # Gate 3: title sanitization
    if LEAK.search(title):
        title = f"discussion-{meta.get('type','card')}-{meta.get('created','unknown')}"
    row = {
        'card_id': os.path.basename(path).replace('.md',''),
        'title': title,
        'type': meta.get('type','discussion'),
        'tags': meta.get('tags','')[:120],
        'created': meta.get('created',''),
        'resolved': 'resolved' in meta.get('status',''),
        'participants': sorted(agents),
        'n_participants': len(agents),
        'n_votes': n_votes,
        'hard_conditions': hard_conds,
        'roles_used': roles_flat,
        'bytes': len(c.encode('utf-8')),
        'schema_version': '1.0',
    }
    # Gate 2: terminal row scan
    s = json.dumps(row, ensure_ascii=False)
    if LEAK.search(s):
        return None
    return row

def main():
    files = glob.glob(os.path.join(CARDS_DIR, '*.md')) + glob.glob(os.path.join(CARDS_DIR, 'archive', '**', '*.md'), recursive=True)
    files = [f for f in files if os.path.basename(f) not in ('讨论室规则.md',)]
    rows, dropped = [], 0
    for f in files:
        try:
            r = build_row(f)
            if r: rows.append(r)
            else: dropped += 1
        except Exception:
            dropped += 1
    with open(OUT, 'w') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    multi = sum(1 for r in rows if r['n_participants'] >= 2)
    resolved = sum(1 for r in rows if r['resolved'])
    print(f'[aggregate] {len(rows)} rows · dropped {dropped} · multi-agent {multi} · resolved {resolved} ({resolved/max(len(rows),1)*100:.0f}%)')
    print(f'[aggregate] → {OUT}')

if __name__ == '__main__':
    main()

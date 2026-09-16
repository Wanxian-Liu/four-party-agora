#!/usr/bin/env bash
# M4 status 派发机制 · git post-commit hook（批1会议裁决 #4 采纳 · M4 立项 A' 合并案）
# 安装：ln -sf ~/.openclaw/workspace/scripts/m4-status-hook.sh /path/to/wiki/.git/hooks/post-commit
# 触发：commit 后扫描变更的 .md 文件 frontmatter status= 行 → 按 owner 映射投信箱
# 满足 Mimir 三不：不人触发（自动 hook）· 不广播（按 owner 映射）· 无 SLO 不立项（hermes 端到端演练决定 SLO）
# 满足 SR-2 Default deny：仅处理 status 变更 + 仅投 owner 对应 inbox + 写时 tmp+fsync+rename 原子

set -eu

# 1. 检测仓（脚本必须在 wiki 仓根或子仓运行）
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
if [ -z "$REPO_ROOT" ]; then
    exit 0  # 非 git 仓·no-op
fi

# 2. 找变更的 .md 文件（commit 后用 HEAD~1..HEAD diff）
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD~1..HEAD 2>/dev/null | grep '\.md$' || true)
if [ -z "$CHANGED_FILES" ]; then
    # 首次 commit 没有 HEAD~1
    CHANGED_FILES=$(git show --name-only --format= HEAD 2>/dev/null | grep '\.md$' || true)
fi
[ -z "$CHANGED_FILES" ] && exit 0  # 无 .md 变更·no-op

# 3. 解析每个 .md 的 status 与 owner，检测变更
STATUS_EVENTS=""
for f in $CHANGED_FILES; do
    # 跳过非 status 行（用 awk 仅读 frontmatter 段内的 status 行）
    NEW_STATUS=$(awk '/^---$/{f++; next} f==1 && /^status:/{sub(/^status: */,""); print; exit}' "$REPO_ROOT/$f" 2>/dev/null || echo "")
    OLD_STATUS=$(git show "HEAD~1:$f" 2>/dev/null | awk '/^---$/{f++; next} f==1 && /^status:/{sub(/^status: */,""); print; exit}' 2>/dev/null || echo "")
    OWNER=$(awk '/^---$/{f++; next} f==1 && /^owner:/{sub(/^owner: */,""); print; exit}' "$REPO_ROOT/$f" 2>/dev/null || echo "")

    # 仅 status 真正变更 + 新 status 非空时触发
    if [ -n "$NEW_STATUS" ] && [ "$NEW_STATUS" != "$OLD_STATUS" ]; then
        STATUS_EVENTS="${STATUS_EVENTS}${f}|${OLD_STATUS:-<none>}|${NEW_STATUS}|${OWNER:-<none>}|"
    fi
done
[ -z "$STATUS_EVENTS" ] && exit 0  # 无 status 变更·no-op

# 4. 投信箱（按 owner 映射·不广播·原子写入）
TS=$(date +%s.%N)
ID_BASE="m4-status-$(date +%s%N | cut -c1-13)"

COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
python3 - "$REPO_ROOT" "$STATUS_EVENTS" "$TS" "$ID_BASE" "$COMMIT_SHA" <<'PYEOF'
import json
import os
import sys
import time
from pathlib import Path

repo_root, events_blob, ts_str, id_base = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
commit_sha = sys.argv[5] if len(sys.argv) > 5 else "unknown"

# owner → inbox 路径映射（CR7 Dependency Direction：固定映射表·禁广播）
OWNER_INBOX = {
    "agent-a": "$HOME/.agora/data/buzz-inbox-agent-a.jsonl",
    "agent-b":   "$HOME/.agora/data/buzz-inbox-agent-b.jsonl",
    "agent-c":    "$HOME/.agora/data/buzz-inbox-agent-c.jsonl",
    "agent-d":     "$HOME/.agora/data/buzz-inbox-agent-d.jsonl",
}
# hermes 永远收一份（orchestrator 追踪）
HERMES_INBOX = OWNER_INBOX["hermes"]

def parse_event(blob_item: str):
    parts = [p for p in blob_item.split("|")]  # bash 末尾带 | 会产生空尾段
    if len(parts) >= 4 and parts[0] and parts[2]:
        return {"file": parts[0], "old": parts[1], "new": parts[2], "owner": parts[3]}
    return None

def write_atomic(inbox_path: str, line: str):
    """追加一行到信箱（jsonl 是追加型日志——禁止 rename 整文件覆盖）
    SR-3 Fail securely：append + flush + fsync；失败不留半行（jsonl 按行解析，半行会被跳过）
    """
    inbox = Path(inbox_path)
    inbox.parent.mkdir(parents=True, exist_ok=True)
    with open(inbox, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())

# bash 侧格式：file|old|new|owner|（每事件4字段·|分隔·末尾多一个|）
# 正确解析：整串切字段后按4个一组重组事件（此前按"每字段=一事件"切是bug·字段内无|恒None）
_flat = [p for p in events_blob.split("|") if p != ""]
events = []
for _i in range(0, len(_flat) - 3, 4):
    _ev = parse_event("|".join(_flat[_i:_i+4]) + "|")
    if _ev:
        events.append(_ev)

for ev in events:
    owner = ev["owner"]
    file_path = ev["file"]
    new_status = ev["new"]
    old_status = ev["old"]

    # 仅给 owner 对应方投递（CR4 + 不广播）
    target_inbox = OWNER_INBOX.get(owner)
    if not target_inbox:
        # owner 未识别·只给 hermes 投（异常信号）
        target_inbox = HERMES_INBOX
        to_field = "hermes"
        from_field = "m4-hook"
    else:
        to_field = owner
        from_field = "m4-hook"

    msg = {
        "ts": float(ts_str),
        "from": from_field,
        "full_from": "m4-hook",
        "to": to_field,
        "kind": 9,  # channel message
        "content": (
            f"【M4 status 派发】file={file_path} · "
            f"status: {old_status} → {new_status} · owner={owner} · "
            f"commit={commit_sha}"
        ),
        "id": f"{id_base}-{owner}",
        "source": "m4-hook",
    }
    line = json.dumps(msg, ensure_ascii=False)
    write_atomic(target_inbox, line + "\n")

    # hermes 永远收一份（orchestrator 追踪）
    if target_inbox != HERMES_INBOX:
        hermes_msg = dict(msg)
        hermes_msg["to"] = "hermes"
        hermes_msg["id"] = f"{id_base}-hermes-trace"
        write_atomic(HERMES_INBOX, json.dumps(hermes_msg, ensure_ascii=False) + "\n")

PYEOF

echo "[m4-hook] status 派发完成：$(( $(echo "$STATUS_EVENTS" | tr -cd '|' | wc -c) / 4 )) 条事件"

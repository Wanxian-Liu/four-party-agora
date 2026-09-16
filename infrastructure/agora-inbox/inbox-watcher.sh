#!/bin/bash
# Mimir Buzz收件箱增量唤醒——零token预扫描
# 原理: 收件箱jsonl行数 > offset → 有新消息 → POST /v1/runs 唤醒Mimir处理 → 成功才推进offset
# 无新消息 → 静默退出(零消耗)
# 修复「webhook盲区: 无人说话=agent永远不醒」——最后一公里(收件箱→运行)

AGENT="${AGORA_AGENT:-agent1}"
INBOX="${BUZZ_INBOX:-$HOME/.fpc/data/buzz-inbox-$AGENT.jsonl}"
OFFSET_FILE="${BUZZ_INBOX_OFFSET:-$HOME/.fpc/data/buzz-inbox-$AGENT.offset}"
LOCK="${BUZZ_INBOX_LOCK:-$HOME/.fpc/data/buzz-inbox-$AGENT.waking}"
# 2026-09-08 D4收件箱统一（四方审计卡）：从 ~/.buzz-nostr/state/ 迁至 ~/.openclaw/data/（四方唯一目录）
# 迁移逻辑：若新路径不存在且旧路径存在 → 合并旧文件内容到新路径（保历史·offset同名迁移）
GATEWAY="${AGORA_GATEWAY_URL:-http://127.0.0.1:18999}"  # 可覆写：测试指向死端口以免真实派发

# 收件箱不存在=从没收到过消息 → 静默
[ -f "$INBOX" ] || exit 0

# 防重入: 上一轮唤醒还没跑完(锁<30min) → 不重复触发
if [ -f "$LOCK" ]; then
    lock_age=$(( $(date +%s) - $(stat -c %Y "$LOCK") ))
    [ $lock_age -lt 1800 ] && exit 0
    rm -f "$LOCK"  # 超30min视为死锁,清掉继续
fi

total=$(wc -l < "$INBOX")
[ -f "$OFFSET_FILE" ] && offset=$(cat "$OFFSET_FILE") || offset=0

# 无增量 → 静默
[ "$total" -le "$offset" ] && exit 0

# ── RS2① 派发前查账（U15 账本级幂等 · 四方裁决 2026-09-13）─────────────────
# 治 INC-10：watcher 只看 offset，不看「已处理到哪」⇒ 同批新行被重复派发。
# 判据取账本**最后一次** `up to N`（非 grep -c 计数），N >= total 即视为已处理。
LEDGER="${BUZZ_INBOX_LEDGER:-$HOME/.fpc/data/inbox-processed.log}"
LEDGER_HWM="${LEDGER}.hwm"
DEGRADE_MARK=""
if [ -f "$LEDGER" ]; then
    ledger_last=$(grep -ao 'up to [0-9][0-9]*' "$LEDGER" | tail -1 | grep -o '[0-9][0-9]*')
    ledger_lines=$(wc -l < "$LEDGER")
    hwm=0
    [ -f "$LEDGER_HWM" ] && hwm=$(cat "$LEDGER_HWM" 2>/dev/null || echo 0)
    [ -z "$hwm" ] && hwm=0
    if [ "$ledger_lines" -gt "$hwm" ]; then
        echo "$ledger_lines" > "$LEDGER_HWM" 2>/dev/null || true
    elif [ "$hwm" -gt 10 ] && [ "$ledger_lines" -lt $(( hwm / 2 )) ]; then
        echo "$(date '+%F %T') 账本损坏(fail-closed): 行数 $ledger_lines 低于高水位 $hwm 一半, 暂停派发等人工"
        exit 3
    fi
    if [ -n "$ledger_last" ] && [ "$ledger_last" -ge "$total" ]; then
        echo "$(date '+%F %T') 账本已处理到 $ledger_last >= total $total → 不重复派发"
        exit 0
    fi
else
    # 降级放行：自主唤醒通路不得因账本缺失而整体停摆（P0-2 立项初衷）；
    # 重复派发由 run 侧语义去重兜底（INC-10 实证）。同流写可见标记行供度量窗计数。
    DEGRADE_MARK=" [降级: 未经账本去重]"
    echo "$(date '+%F %T') DEGRADED dispatch (ledger missing: $LEDGER, dedup not applied)" >> "$LEDGER" 2>/dev/null || true
fi

new_count=$(( total - offset ))

# 唤醒Mimir: 处理收件箱新消息(offset+1 到 total)
resp=$(curl -s -m 10 -X POST "$GATEWAY/v1/runs" \
    -H "Content-Type: application/json" \
    -d "{\"input\": \"【自动唤醒】Buzz收件箱有 ${new_count} 条新消息${DEGRADE_MARK}(第 $((offset+1)) 到 ${total} 行)。请读取 $INBOX 的新消息并处理: 需要行动的执行(四方接棒/查证/落盘), 纯通知的跳过。处理完成后在 ~/.mimiraether/logs/inbox-processed.log 追加一行: $(date '+%F %T') processed $new_count lines (up to $total)。\", \"metadata\": {\"source\": \"buzz-inbox-watcher\"}}")

# 202/200 = 接受 → 推进offset+落锁防重入
if echo "$resp" | grep -qE '"(status)":\s*"(started|running|completed)"'; then
    echo "$total" > "$OFFSET_FILE"
    date +%s > "$LOCK"
    echo "$(date '+%F %T') 唤醒成功: ${new_count}条新消息 → Mimir (offset $offset→$total)"
else
    echo "$(date '+%F %T') 唤醒失败(gateway未接受), offset不推进下次重试: ${resp:0:120}"
fi

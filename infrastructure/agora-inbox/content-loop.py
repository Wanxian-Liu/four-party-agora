#!/usr/bin/env python3
"""
通用 Buzz 内容级处理循环 v2.1（Agora 修复版 2026-08-26）
给 OpenClaw / Loki 用。Hermes/Mimir 用各自 content-loop。
修复:
- NEW-1 显式 AGENT_MAP (替代硬编码 main/weixin; loki→weixin 是 openclaw 路由约定)
- SEED-1 删 --channel nostr --deliver (nostr 已禁用; 改收件箱回写)
- NEW-2 kind 不在 {1, 42} 跳过 (信号 kind=9 不触发 agent)
- NEW-4 SEEN 写 tmp+rename 原子化 (防并发覆写)
- SEED-4 收件箱读兼容统一 (id 必填校验; 缺 id 入 quarantine/+log)
- NEW-3 删 "18bug" 遗迹关键词; CONFIRM_WORDS 用更精确的正则

用法：AGENT_NAME=openclaw BUZZ_SK=<key> python3 content-loop-generic-v2.py
"""
import os, re, sys, json, subprocess, datetime, tempfile, hashlib

# NEW-1 修复: 显式映射表替代硬编码 ("AGENT_NAME" → "openclaw agent id")
# 来源: openclaw agents list → weixin (洛基 Loki) — loki 在 openclaw 路由下绑 weixin
AGENT_MAP = {"openclaw": "main", "loki": "weixin"}
AGENT = os.environ.get("AGENT_NAME", "openclaw")
AGENT_ID = AGENT_MAP.get(AGENT, AGENT)  # 未知 agent: 默认用 AGENT_NAME 让 openclaw 自己报错

# ── Config (all paths overridable via env — self-host friendly) ──
BASE_DIR = os.environ.get("AGORA_BASE_DIR", os.path.expanduser("~/.agora"))
DATA_DIR = os.environ.get("AGORA_DATA_DIR", os.path.join(BASE_DIR, "data"))
SCRIPTS_DIR = os.environ.get("AGORA_SCRIPTS_DIR", os.path.join(BASE_DIR, "scripts"))
INBOX = os.environ.get("BUZZ_INBOX", os.path.join(DATA_DIR, f"buzz-inbox-{AGENT}.jsonl"))
BUZZ_SK = os.environ.get("BUZZ_SK", "")
CHANNEL = "7eb862af-f5a5-4f1a-9cea-0fb20322eeb8"
SEND_SCRIPT = os.path.join(SCRIPTS_DIR, "buzz-send-generic.js")
SEEN_FILE = os.path.join(DATA_DIR, f"buzz-content-seen-{AGENT}.txt")
QUARANTINE_FILE = os.path.join(DATA_DIR, f"buzz-content-quarantine-{AGENT}.jsonl")
# RS14 Q13 (Hermes 16:24 终裁): 写入方实锤 = Loki wrapper 还在写顶层 HERMES_INBOX. 改 canonical.
# 修改: 2026-09-14 16:27 GMT+8 · Loki
# 验证: canonical = ~/.openclaw/data/buzz-inbox-hermes.jsonl · 顶层 nostr 文件保留 487 行归档不删 (Hermes 令)
HERMES_INBOX = os.path.expanduser("~/.openclaw/data/buzz-inbox-hermes.jsonl")

# NEW-2 修复: kind 过滤白名单 (只处理聊天 kind=1 + 频道回复 kind=42)
VALID_KINDS = {1, 42}

# N-02 fix: 抽 BUZZ_PROMPT_MAX_CHARS 常量 (默认 1500 · 环境变量可覆盖)
BUZZ_PROMPT_MAX_CHARS = int(os.environ.get("BUZZ_PROMPT_MAX_CHARS", "1500"))

# NEW-3b 修复: 更精确的纯确认/待命模式 (正则, 不再误伤含 "任务" 等子串的实质回复)
CONFIRM_PATTERNS = [
    r"^\s*(?:✅\s*)?(?:已?收|已?收到|待命|收到[。,]?)\s*$",
    r"^\s*【?(?:Loki|OpenClaw)\s*待命】?\s*$",
]

if not BUZZ_SK:
    print("需要 BUZZ_SK")
    sys.exit(1)


def send_to_channel(content, mention_pub=None):
    env = dict(os.environ)
    env["BUZZ_SK"] = BUZZ_SK
    env["BUZZ_CHANNEL"] = CHANNEL
    env["BUZZ_CONTENT"] = content
    env["BUZZ_MENTION"] = mention_pub or ""
    r = subprocess.run(["node", SEND_SCRIPT], env=env, capture_output=True, text=True, timeout=15)
    return r.stdout.strip()


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    raw_ids = set(open(SEEN_FILE).read().splitlines())
    # LOKI 迁移 (2026-08-26): 旧 SEEN 条目是明文 id — 不丢老条目
    # 老 id 原样保留在 set 里 (以供兼容老 agent — 部分老 agent 可能仍按明文 id 查)
    # 但 Loki 段 seen_key 走 hash — 老条目不能 hash 反查 (老 content 不在 SEEN 里)
    # 实用妥协: 双形态保留 — 老 id 明文 + 新 hash — set 里同时存两种
    # 迁移期间不丢任何条目
    return raw_ids


def save_seen(ids):
    # NEW-4 修复: 写用 tmp+rename 原子化 (防并发覆写)
    ids_list = sorted(ids)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(SEEN_FILE), prefix=".seen-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(ids_list))
        os.replace(tmp, SEEN_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def quarantine(line_no, raw_line, reason):
    """SEED-4 修复: 缺 id 或坏行入隔离目录 + 写日志"""
    try:
        os.makedirs(os.path.dirname(QUARANTINE_FILE), exist_ok=True)
        with open(QUARANTINE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.datetime.now().isoformat(),
                                "line_no": line_no, "reason": reason,
                                "raw": raw_line[:500]}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def is_confirm(text: str) -> bool:
    """NEW-3b: 用精确正则判定纯确认/待命"""
    for pat in CONFIRM_PATTERNS:
        if re.match(pat, text.strip()):
            return True
    return False


def main():
    try:
        lines = open(INBOX, encoding="utf-8").readlines()
    except Exception as e:
        print(f"读收件箱失败: {e}")
        return

    seen = load_seen()
    new_msgs = []
    for i, line in enumerate(lines, 1):
        try:
            d = json.loads(line)
        except Exception as e:
            quarantine(i, line, f"json parse error: {e}")
            continue
        # SEED-4 修复: id 必填校验 (缺 id 入隔离, 不污染 seen)
        msg_id = d.get("id")
        if not msg_id:
            quarantine(i, line, "missing id field")
            continue
        # N-01 fix (v1.1 审计复查 P2): msg_id 唯一去重为主键
        # seen_key 哈希 (sha256 content[:200]) 仍计算但**不**进主去重集 (避免哈希冲突误判)
        # 留作旁路记录 (debug 用) - 实际去重只看 msg_id
        if msg_id in seen:
            continue
        # NEW-2 修复: kind 过滤 (信号 kind=9 等不入)
        kind = d.get("kind", 1)
        if kind not in VALID_KINDS:
            continue
        content = d.get("content") or d.get("msg") or ""
        head = content[:50]
        # 显式回复/标记前缀: 跳过 (这是出站回执, 不应再触发)
        if content.startswith("【REPLY】"):
            continue
        # NEW-3b 修复: 纯确认/待命跳过 (正则)
        if is_confirm(content):
            continue
        # NEW-3a 修复: 删 "18bug" 遗迹关键词
        # 处理触发条件: @自己 OR 含 "四方" OR 含 "任务"
        if "@" in content or "四方" in content or "任务" in content:
            new_msgs.append(d)

    if not new_msgs:
        sys.exit(0)  # 无新消息静默退出

    latest = new_msgs[-1]
    # N-02 fix: 抽常量 BUZZ_PROMPT_MAX_CHARS (默认 1500 · 环境变量可覆盖)
    content = latest.get("content", "")[:BUZZ_PROMPT_MAX_CHARS]
    from_pub = latest.get("from", "")
    print(f"📩 处理: AGENT={AGENT} AGENT_ID={AGENT_ID} content={content[:60]}")

    prompt = f"""你在Buzz频道收到Hermes发来的消息（来自{from_pub}）：
{content}

请处理：
1. 理解消息内容（任务/讨论/询问）
2. 如果是任务：实际执行（读文件/grep/验证），给出实盘结论
3. **落盘要求（重要）**：如果消息提到"写入XX卡/落盘/输出到/讨论卡"，必须**用patch追加**回答到指定卡（**禁止write_file整卡覆盖**——讨论卡被四方并发编辑，整卡覆盖会抹掉他人段），绝对路径
4. 输出你的回复正文（50-200字，观点明确，带证据，如果落盘了带上写入路径）
你的输出将作为频道消息发出。现在输出回复正文："""

    try:
        # SEED-1 修复: 删 --channel nostr --deliver 三个死参
        # 现在走 inbox 回写 (信号物理化段) 而非 Nostr 直连
        r = subprocess.run(
            ["openclaw", "agent", "--agent", AGENT_ID, "-m", prompt],
            capture_output=True, text=True, timeout=240,
        )
        # 修 (Hermes 8/27): 检查 returncode——失败 (如 429 rate limit) 不标记 seen.add·保留消息下次重试
        # 默认 check=True 会 raise CalledProcessError·这里用 returncode 分支避免 raise·便于后续落 warning 日志
        if r.returncode != 0:
            # 2026-08-29 Hermes 补丁: 广播类消息（无需执行动作）失败也标 seen——
            # 防限流期广播把 cron 重试循环变成对用户的消息轰炸（实例：rate limit 下广播连败）
            if content.startswith("【四方广播"):
                seen.add(msg_id); save_seen(seen)
                print(f"⚠️ agent 失败但广播类消息标 seen（不重试）: {msg_id[:30]}")
                return
            print(f"⚠️ agent 失败 (returncode={r.returncode})——保留消息不标记 seen·待下次重试")
            return
        output = r.stdout + r.stderr
        print(f"📤 agent输出: {output[-200:]}")

        # already_sent 检测保留 — 不重复发送
        already_sent = any(w in output for w in ["已发送到频道", "频道消息已发", "已发频道", "📤 已发频道"])
        if not already_sent:
            lines_out = [l.strip() for l in output.splitlines() if l.strip() and len(l.strip()) > 15]
            if lines_out:
                reply = f"【{AGENT.title()}】{lines_out[-1][:400]}"
                if is_confirm(reply) and len(reply) < 120:
                    print(f"🔇 回执静默: {reply[:40]}...")
                else:
                    # SEED-1 修复: 改收件箱回写 (替代 Nostr 直连)
                    try:
                        _ts = datetime.datetime.now().timestamp()
                        _sig = {"ts": _ts, "from": AGENT, "full_from": AGENT, "kind": 9,
                                "content": reply, "id": f"{AGENT}-out-{int(_ts*1000)}", "source": AGENT}
                        with open(HERMES_INBOX, "a", encoding="utf-8") as hf:
                            hf.write(json.dumps(_sig, ensure_ascii=False) + "\n")
                        print(f"📥 收件箱回写 ok (kind=9 信号)")
                    except Exception as _e:
                        print(f"⚠️ 收件箱回写失败: {_e}")
    except Exception as e:
        print(f"agent触发失败: {e}")
        return

    # N-01 fix: 标记已处理 + 原子写 (msg_id 唯一去重; seen_key 仅作旁路不再入主集)
    seen.add(latest.get("id", ""))
    save_seen(seen)


if __name__ == "__main__":
    main()
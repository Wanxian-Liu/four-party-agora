#!/usr/bin/env python3
"""
四方评分器 v3——Anthropic式（6维度×每维度独立LLM-judge）
设计原则：简易版不过重——评估是激励——做完回项目
"""
import json, os, sys, re, urllib.request

def load_key():
    try:
        for line in open(os.path.expanduser('~/.hermes/.env')):
            if 'DEEPSEEK' in line.upper() and '=' in line:
                return line.strip().split('=', 1)[1].strip()
    except Exception:
        pass
    return ''

def judge(system, user):
    """DeepSeek当Judge——每维度独立调用"""
    data = json.dumps({
        'model': 'deepseek-v4-flash',
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user}
        ],
        'reasoning_effort': 'low',
    }).encode()
    req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {load_key()}'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())['choices'][0]['message']['content']
    except Exception as e:
        return f'{{"分数": 0, "理由": "judge失败: {e}"}}'

def score_one(name, section, dim, criteria):
    system = """你是四方协作行为评分裁判（Anthropic式——每维度独立judge）。
只基于落盘内容证据评分。输出严格JSON：{"分数": 0-100的整数, "理由": 一句话}。
分数标准：0-40不合格(糊弄/无证据) 50-70及格(有内容浅) 75-100优秀(有依据/有细节/可执行)"""
    user = f'评 {name} 的维度"{dim}"。\nRubric: {criteria}\n\n落盘内容:\n---\n{section[:1500]}\n---\n\n输出JSON。'
    result = judge(system, user)
    try:
        start, end = result.find('{'), result.rfind('}') + 1
        d = json.loads(result[start:end])
        return d.get('分数', 0), d.get('理由', '')
    except Exception:
        nums = re.findall(r'\d+', result)
        return (int(nums[0]) if nums else 0), result[:60]

DIMS = {
    '真读原文': '有没有读PDF/arXiv/源码原文？落盘或过程证据显示真读了吗？还是只看地图卡/二手卡？',
    '证据锚点': '落盘里有论文ID/Table数据/arXiv引用/具体数字/验证动作吗？还是概念空谈？',
    '角色使用': '标注角色了吗？角色名是库里的真实角色吗（从库找）？还是随手编的？',
    '落盘完整': '写盘了吗？是完整发言还是占位/只读不写？',
    '建议可执行': '建议具体可落地吗？有步骤/路径吗？还是空泛口号？',
    '独立碰撞': '有自己观点吗？和前面人发言碰撞/补充了吗？还是跟风/重复？',
}

def main():
    card = sys.argv[1] if len(sys.argv) > 1 else './sample-card.md'
    content = open(card, encoding='utf-8').read()
    
    # 提取各方段
    sections = {}
    current = None
    for line in content.split('\n'):
        if line.startswith('### '):
            header = line[4:]
            matched = False
            for name in ['Hermes', 'Mimir', 'Loki', 'OpenClaw']:
                if header.startswith(name) or name in header.split('）')[0]:
                    current = name
                    sections.setdefault(name, []).append('')
                    matched = True
                    break
            if not matched:
                current = None
        elif current and line.strip():
            sections[current][-1] += line + '\n'
    sections = {k: '\n'.join(v) for k, v in sections.items()}
    
    print('=' * 55)
    print('四方评分器 v3——Anthropic式（6维度×独立judge）')
    print(f'卡: {os.path.basename(card)}')
    print('=' * 55)
    for name, section in sections.items():
        if not section.strip():
            print(f'\n【{name}】未落盘——0分')
            continue
        scores = {}
        for dim, crit in DIMS.items():
            s, r = score_one(name, section, dim, crit)
            scores[dim] = (s, r)
        avg = sum(s for s, _ in scores.values()) / len(DIMS)
        status = '✅合格' if avg >= 75 else '⚠️需补做'
        print(f'\n【{name}】平均 {avg:.0f}/100 — {status}')
        for dim, (s, r) in scores.items():
            print(f'  {dim}: {s} ({r[:40]})')
    print('\n' + '=' * 55)

if __name__ == '__main__':
    main()

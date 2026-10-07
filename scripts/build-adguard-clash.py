# -*- coding: utf-8 -*-
"""把 QX 分流规则转换成 AdGuard Home / Clash(FlClash) 格式，并与已有规则去重。

数据源：qx-rules-repo/output/QX-AllInOne-Filter.conf（15747 条，源为
        AWAvenue / fmz200 / NobyDa / Adblock4limbo / BanAD / easylistchina 等）

去重基准（AdGuard Home 现有过滤列表，需联网拉取）：
        AdGuard DNS filter、AdAway、AWAvenue、HALF、anti-AD、AdRules DNS、AWAvenue(重复源)

产出：
  output/adguard/adguard-qx.txt      AdGuard 语法（||domain^），供 AdGuard Home 订阅
  output/adguard/clash-qx.yaml       Clash 语法（DOMAIN-SUFFIX），供 FlClash / Mihomo
  output/adguard/dedup-report.json   去重统计
"""
import json
import os
import re
import sys
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (compatible; qx-rules-dedup/1.0)'}
BASE = 'C:/Users/Administrator/Documents/deepseek-harness/default-workspace/iOS-QX规则集'
SRC = os.path.join(BASE, 'qx-rules-repo', 'output', 'QX-AllInOne-Filter.conf')
OUT = os.path.join(BASE, 'qx-rules-repo', 'output', 'adguard')

# AdGuard Home 现用的 7 个列表（去重基准）
EXISTING = [
    'https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt',
    'https://adguardteam.github.io/HostlistsRegistry/assets/filter_2.txt',
    'https://adguardteam.github.io/HostlistsRegistry/assets/filter_53.txt',
    'https://adguard.yojigen.tech/HalfLifeList.txt',
    'https://anti-ad.net/easylist.txt',
    'https://raw.githubusercontent.com/Cats-Team/AdRules/main/dns.txt',
    'https://github.boki.moe/https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/AWAvenue-Ads-Rule.txt',
]


def get(url, timeout=120):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read().decode('utf-8', 'replace')


def host_of_rule(line):
    """从 AdGuard 规则行里提取主机名（用于去重比较）"""
    s = line.strip()
    if not s or s.startswith(('!', '#', '[', '@')):
        return None
    # ||domain^ / ||domain^$mod  / 0.0.0.0 domain / domain / @@||domain^
    m = re.match(r'^@@\|\|([a-z0-9.*_-]+)\^?', s, re.I)
    if m:
        return m.group(1).lower().rstrip('.')
    m = re.match(r'^\|\|([a-z0-9.*_-]+)\^?', s, re.I)
    if m:
        return m.group(1).lower().rstrip('.')
    m = re.match(r'^(?:0\.0\.0\.0|127\.0\.0\.1)\s+([a-z0-9.*_-]+)', s, re.I)
    if m:
        return m.group(1).lower().rstrip('.')
    m = re.match(r'^([a-z0-9][a-z0-9.*_-]*\.[a-z]{2,})$', s, re.I)
    if m:
        return m.group(1).lower().rstrip('.')
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    print('==== 1. 读取 QX 分流规则')
    qx_rules = []
    for l in open(SRC, encoding='utf-8'):
        s = l.strip()
        if not s or s.startswith(('#', ';', '[')):
            continue
        p = [x.strip() for x in s.split(',')]
        if len(p) < 3:
            continue
        qx_rules.append((p[0].lower(), p[1].strip()))
    print(f'  {len(qx_rules)} 条')

    print('==== 2. 拉取 AdGuard 现有列表作为去重基准')
    existing = set()
    for u in EXISTING:
        try:
            t = get(u)
            n = 0
            for line in t.splitlines():
                h = host_of_rule(line)
                if h:
                    existing.add(h)
                    n += 1
            print(f'  {u.split("/")[-1][:44]:<46} {n:>7} 条')
        except Exception as e:
            print(f'  [WARN] {u[:56]} 拉取失败: {str(e)[:50]}')
    print(f'  去重基准合计 {len(existing)} 个唯一主机名')

    print('==== 3. 转换 + 去重')
    ag_out, clash_out = [], []
    seen = set()
    stats = {'total': len(qx_rules), 'dup_in_existing': 0, 'dup_internal': 0,
             'converted': 0, 'skipped': 0}
    for typ, val in qx_rules:
        v = val.lower().strip().lstrip('.')
        if not v:
            stats['skipped'] += 1
            continue
        if v in existing:
            stats['dup_in_existing'] += 1
            continue
        if v in seen:
            stats['dup_internal'] += 1
            continue
        seen.add(v)
        if typ in ('domain-suffix', 'host-suffix'):
            ag_out.append(f'||{v}^')
            clash_out.append(f'DOMAIN-SUFFIX,{v}')
        elif typ in ('domain', 'host'):
            ag_out.append(f'||{v}^')
            clash_out.append(f'DOMAIN,{v}')
        elif typ in ('domain-keyword', 'host-keyword'):
            ag_out.append(f'{v}')
            clash_out.append(f'DOMAIN-KEYWORD,{v}')
        elif typ in ('domain-wildcard', 'host-wildcard'):
            ag_out.append(f'||{v.replace("*", "")}^')
            clash_out.append(f'DOMAIN-WILDCARD,{v}')
        elif typ in ('ip-cidr', 'ip6-cidr'):
            # AdGuard 用 IP 规则需 $network，这里保守处理为 Clash 侧
            clash_out.append(f'{typ.upper().replace("IP6-CIDR","IP-CIDR6")},{val},no-resolve')
            ag_out.append(f'||{v}^') if re.match(r'^[\w.-]+\.[a-z]{2,}$', v) else None
        elif typ == 'user-agent':
            stats['skipped'] += 1
            continue
        else:
            stats['skipped'] += 1
            continue
        stats['converted'] += 1

    print(f'  转出 AdGuard {len(ag_out)} 条 / Clash {len(clash_out)} 条')
    print(f'  与现有列表重复 {stats["dup_in_existing"]} 条（已剔除）')
    print(f'  内部重复 {stats["dup_internal"]} 条（已剔除）')
    print(f'  跳过（无法转换）{stats["skipped"]} 条')

    # 输出
    p1 = os.path.join(OUT, 'adguard-qx.txt')
    with open(p1, 'w', encoding='utf-8', newline='\n') as f:
        f.write('! QX 分流规则转换 · AdGuard 语法 · 已与 AdGuard Home 现有列表去重\n')
        f.write(f'! 原始 {stats["total"]} 条 → 输出 {len(ag_out)} 条\n')
        f.write('\n'.join(ag_out) + '\n')

    p2 = os.path.join(OUT, 'clash-qx.yaml')
    with open(p2, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# QX 分流规则转换 · Clash 语法（FlClash / Mihomo / Stash）\n')
        f.write(f'# 原始 {stats["total"]} 条 → 输出 {len(clash_out)} 条\n')
        f.write('payload:\n')
        for r in clash_out:
            f.write(f'  - {r}\n')

    stats['adguard_out'] = len(ag_out)
    stats['clash_out'] = len(clash_out)
    with open(os.path.join(OUT, 'dedup-report.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)

    print(f'\n已写出:')
    print(f'  {p1}  ({os.path.getsize(p1)/1024:.1f} KB)')
    print(f'  {p2}  ({os.path.getsize(p2)/1024:.1f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

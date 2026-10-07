#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取墨鱼（ddgksf2013.top）全部复写规则并分类整合。

背景：
  ddgksf2013.top 是 SPA，直接猜路径会拿到首页 HTML。
  真实资源清单在 https://ddgksf2013.top/data.json。
  各 .js / .conf 文件自带 rewrite 规则行（`... url script-response-body ...`）
  以及 `hostname = ...`（MITM 主机名）。

产出（output/moyu-full/）：
  ★VIP解锁-全部.conf      23 个 App 的解锁规则合并（含分节注释）
  广告净化-全部.conf        全部广告净化规则合并
  其他功能.conf            去开屏等
  _index.json              明细索引
  _mitm-hostnames.txt      合并后的 MITM 主机名

用法：python3 scripts/fetch-moyu-full.py
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import urllib.request

UA = {'User-Agent': 'Quantumult X/1.5.0', 'Accept': '*/*'}
DATA_URL = 'https://ddgksf2013.top/data.json'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'output', 'moyu-full')


def fetch(url, timeout=30):
    b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
    return b.decode('utf-8', 'replace')


def main():
    print('==== 1. 读取资源清单')
    try:
        data = urllib.request.urlopen(
            urllib.request.Request(DATA_URL, headers={'User-Agent': 'Mozilla/5.0'}),
            timeout=60).read().decode('utf-8', 'replace')
    except Exception as e:
        print(f'[ERROR] data.json 不可达: {e}', file=sys.stderr)
        return 1
    links = sorted(set(re.findall(
        r'https://ddgksf2013\.top/(?:rewrite|scripts)/[^"\s,]+', data)))
    print(f'  链接 {len(links)} 个')
    if not links:
        print('[ERROR] 清单为空', file=sys.stderr)
        return 1

    print('==== 2. 下载并解析')
    results = {}

    def one(u):
        try:
            t = fetch(u)
            if '<!DOCTYPE' in t[:200] or '<html' in t[:200]:
                return u, None
            return u, t
        except Exception:
            return u, None

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for u, t in ex.map(one, links):
            if t:
                results[u] = t
    print(f'  成功 {len(results)}/{len(links)}')

    print('==== 3. 提取规则与主机名')
    items, all_hosts = [], []
    for u, t in sorted(results.items()):
        name = u.rsplit('/', 1)[-1]
        tag = re.sub(r'\.(js|conf)$', '', name)
        rules, hosts = [], []
        for line in t.replace('\r\n', '\n').split('\n'):
            s = line.strip()
            if not s:
                continue
            m = re.match(r'^hostname\s*=\s*(.+)$', s, re.I)
            if m:
                hosts += [h.strip() for h in m.group(1).split(',') if h.strip()]
                continue
            if s.startswith(('//', '#', '/*', '*')):
                continue
            if re.search(r'\surl(-and-header)?\s+\S', s):
                rules.append(s)
        all_hosts += hosts
        if rules:
            items.append({'file': name, 'tag': tag, 'rules': rules, 'hosts': hosts})

    # 分类
    def is_vip(it):
        return 'vip' in it['file'].lower() or 'unlock' in it['file'].lower()

    vip = [x for x in items if is_vip(x)]
    ads = [x for x in items if not is_vip(x)]

    os.makedirs(OUT, exist_ok=True)

    def write_group(path, group, header):
        seen, lines = set(), [f'; {header}', f'; 共 {len(group)} 个来源']
        for it in sorted(group, key=lambda y: -len(y['rules'])):
            fresh = [r for r in it['rules'] if r not in seen]
            if not fresh:
                continue
            seen.update(fresh)
            lines.append('')
            lines.append(f';【{it["tag"]}】{len(fresh)} 条')
            lines.extend(fresh)
        data = '\n'.join(lines) + '\n'
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(data)
        os.chmod(path, 0o644)
        return len(seen)

    n_vip = write_group(os.path.join(OUT, '★VIP解锁-全部.conf'), vip,
                        '墨鱼会员解锁合集（每个 App 一节，可整段注释掉）')
    n_ads = write_group(os.path.join(OUT, '广告净化-全部.conf'), ads,
                        '墨鱼广告净化合集')

    hosts = sorted(set(h for h in all_hosts if h and not h.startswith('<')))
    with open(os.path.join(OUT, '_mitm-hostnames.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(', '.join(hosts) + '\n')
    os.chmod(os.path.join(OUT, '_mitm-hostnames.txt'), 0o644)

    with open(os.path.join(OUT, '_index.json'), 'w', encoding='utf-8') as f:
        json.dump({'vip': [{'tag': x['tag'], 'rules': len(x['rules'])} for x in vip],
                   'ads': [{'tag': x['tag'], 'rules': len(x['rules'])} for x in ads],
                   'hosts': len(hosts), 'sources': len(items)}, f,
                  ensure_ascii=False, indent=1)

    print(f'  VIP 解锁 {len(vip)} 个来源 → {n_vip} 条')
    print(f'  广告净化 {len(ads)} 个来源 → {n_ads} 条')
    print(f'  MITM 主机名 {len(hosts)} 个')
    print(f'  已写出 {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

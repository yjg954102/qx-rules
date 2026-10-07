# -*- coding: utf-8 -*-
"""生成 QX 策略组（可用版）：国家组支持「自动优选」。

核心设计 —— 双定义模式：
  1) 选择组（static）：把国家组列出，让别的组能引用它
       static=🚀 节点选择, 美国-自动, 香港-自动, ...
  2) 测速组（url-latency-benchmark）：同名再定义一次，作用于节点
       url-latency-benchmark=美国-自动, <该地区所有节点>, check-interval=...

QX 取第一次出现作为「可选策略」，benchmark 定义提供「组内自动优选最快节点」。

节点名必须列举（该 QX 版本 server-tag-regex 实测不生效）。
"""
import os
import re
import sys
import urllib.request

UA = {'User-Agent': 'Quantumult X'}
BASE = 'C:/Users/Administrator/Documents/deepseek-harness/default-workspace/iOS-QX规则集'
SRC = os.path.join(BASE, 'qx-分类版.conf')
NODES_URL = 'http://192.168.50.2:8109/output/qx-compatible-all.txt'

REGIONS = [
    ('美国', r'美国|US|United States|圣何塞|洛杉矶|西雅图|芝加哥'),
    ('香港', r'香港|HK|Hong Kong|hkt|i-Cable|HGC'),
    ('日本-专线', r'日本-专线'),
    ('日本', r'日本|JP|Japan|东京|大阪'),
    ('新加坡-专线', r'新加坡-专线'),
    ('新加坡', r'新加坡|SG|Singapore'),
    ('台湾', r'台湾|TW|Taiwan|中華電信|中华电信'),
    ('韩国', r'韩国|KR|Korea|首尔'),
    ('英国', r'英国|UK|Britain|伦敦'),
    ('加拿大', r'加拿大|CA|Canada|多伦多|温哥华'),
    ('越南', r'越南|VN|Vietnam'),
    ('印度', r'印度|IN|India|孟买'),
    ('德国', r'德国|DE|Germany|法兰克福'),
    ('俄罗斯', r'俄罗斯|RU|Russia|莫斯科'),
    ('土耳其', r'土耳其|TR|Turkey|伊斯坦布尔'),
    ('意大利', r'意大利|IT|Italy|米兰'),
    ('澳大利亚', r'澳大利亚|澳洲|AU|Australia|悉尼'),
    ('法国', r'法国|FR|France|巴黎'),
    ('荷兰', r'荷兰|NL|Netherlands|阿姆斯特丹'),
]
STREAM_RE = r'媒体流|流媒体|专线|原生|AWS|日本东京0[6-9]'

GENERAL = [
    'server_check_url=http://developers.google.cn/generate_204',
    'network_check_url=http://www.google.cn',
    'dns_exclusion_list=*.local, *.lan',
    'icmp_auto_reply=true',
    'server_check_timeout=2000',
    'udp_whitelist=1-65535',
    'fallback_udp_policy=direct',
]


def main():
    t = urllib.request.urlopen(
        urllib.request.Request(NODES_URL, headers=UA), timeout=60).read().decode('utf-8', 'replace')
    tags = []
    for l in t.splitlines():
        m = re.search(r'tag=([^,]+)$', l.strip())
        if m:
            tags.append(m.group(1).strip())
    if not tags:
        print('未取到节点')
        return 1
    print(f'节点 {len(tags)} 个')

    buckets = {}
    used = set()
    for name, pat in REGIONS:
        rx = re.compile(pat, re.I)
        v = [x for x in tags if rx.search(x) and x not in used]
        if v:
            buckets[name] = v
            used.update(v)
            print(f'  {name:<12} {len(v):>3} 个')
    stream = [x for x in tags if re.search(STREAM_RE, x, re.I)]
    print(f'  {"流媒体":<12} {len(stream):>3} 个')
    leftovers = [x for x in tags if x not in used]
    if leftovers:
        buckets['其他'] = leftovers
        print(f'  {"其他":<12} {len(leftovers):>3} 个')

    auto_names = [n + '-自动' for n in buckets]
    manual_names = [n + '-手动' for n in buckets]

    L = []
    L.append('; ================= 零、选择组（供其它组引用 / 界面手动选择）=================')
    L.append('; QX 取同名策略的第一次定义作为「可选策略」，下面的 benchmark 定义提供组内自动优选')
    L.append('static=🚀 节点选择, ' + ', '.join(auto_names + ['🎵 流媒体', '🎯 全球直连']))
    L.append('static=🐟 兜底分流, 🚀 节点选择, 🎯 全球直连')
    L.append('static=🎯 全球直连, direct')
    L.append('static=🛑 广告拦截, reject')
    L.append('')
    L.append('; ================= 一、测速组（组内自动优选最快节点）=================')
    L.append('url-latency-benchmark=♻️ 所有节点, ' + ', '.join(tags) +
             ', check-interval=600, tolerance=50, alive-checking=true')
    L.append('url-latency-benchmark=🎵 流媒体, ' + ', '.join(stream or tags[:5]) +
             ', check-interval=300, tolerance=30, alive-checking=true')
    L.append('')
    L.append('; ================= 二、国家/地区分组（自动优选 + 手动）=================')
    for name, v in buckets.items():
        # url-latency-benchmark 至少需要 2 个节点，否则语法错误；单节点组用 static
        if len(v) >= 2:
            L.append(f'url-latency-benchmark={name}-自动, ' + ', '.join(v) +
                     ', check-interval=600, tolerance=50, alive-checking=true')
        else:
            L.append(f'static={name}-自动, ' + ', '.join(v))
        L.append(f'static={name}-手动, ' + ', '.join(v) + ', 🎯 全球直连')

    policy = L
    n_def = len([l for l in policy if l.strip() and not l.startswith(';')])
    print(f'\n策略定义 {n_def} 行（{len(auto_names)} 个国家组 × 2）')

    txt = open(SRC, encoding='utf-8').read().replace('\r\n', '\n')
    lines = txt.split('\n')
    out, i = [], 0
    while i < len(lines):
        s = lines[i].strip()
        if s in ('[general]', '[policy]'):
            out.append(lines[i])
            out.extend(GENERAL if s == '[general]' else policy)
            i += 1
            while i < len(lines) and not lines[i].startswith('['):
                i += 1
            continue
        out.append(lines[i])
        i += 1

    with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out))
    body = '\n'.join(out)
    print(f'已写入 {SRC}  {os.path.getsize(SRC)} 字节')
    print(f'  段头 {len(re.findall(r"(?m)^\[.+\]$", body))}')
    print(f'  static {len(re.findall(r"(?m)^static=", body))}  '
          f'benchmark {len(re.findall(r"(?m)^url-latency-benchmark=", body))}')
    print(f'  CR {open(SRC,"rb").read().count(13)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

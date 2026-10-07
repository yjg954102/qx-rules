# -*- coding: utf-8 -*-
"""重建 QX 策略组：完整国家分组（对齐路由器 Shadowrocket 的 40 组结构）。

QX 用 server-tag-regex 匹配节点（而非列举节点名）——因为 QX 会对同名节点去重，
列举节点名会导致「未知策略或节点」错误。

组结构：
  核心：🚀 节点选择 / ♻️ 所有-自动 / 📋 所有-手动 / 🎯 全球直连 / 🛑 广告拦截 / 🎵 流媒体 / 🐟 兜底分流
  国家：14 个地区 × (自动/手动)，日本与新加坡另加「专线」
"""
import os
import re
import sys

BASE = 'C:/Users/Administrator/Documents/deepseek-harness/default-workspace/iOS-QX规则集'
SRC = os.path.join(BASE, 'qx-分类版.conf')

# 国家/地区：显示名 -> 匹配节点的正则片段（QX 的 server-tag-regex 是 (?i) 大小写不敏感）
REGIONS = [
    ('美国', '美国|US|United States'),
    ('香港', '香港|HK|Hong Kong'),
    ('日本', r'日本(?!-专线)'),
    ('日本-专线', '日本-专线'),
    ('新加坡', r'新加坡(?!-专线)'),
    ('新加坡-专线', '新加坡-专线'),
    ('台湾', '台湾|TW|Taiwan'),
    ('韩国', '韩国|KR|Korea'),
    ('英国', '英国|UK|Britain'),
    ('加拿大', '加拿大|CA|Canada'),
    ('越南', '越南|VN|Vietnam'),
    ('印度', '印度|IN|India'),
    ('德国', '德国|DE|Germany'),
    ('俄罗斯', '俄罗斯|RU|Russia'),
    ('土耳其', '土耳其|TR|Turkey'),
    ('意大利', '意大利|IT|Italy'),
    ('澳大利亚', '澳大利亚|澳洲|AU|Australia'),
    ('法国', '法国|FR|France'),
    ('荷兰', '荷兰|NL|Netherlands'),
    ('其他', '其他|Other'),
]

# 流媒体组：优先放吞吐高的节点（聚合器实测新加坡-媒体流/香港-流媒体最高）
STREAM_RE = (r'媒体流|流媒体|专线|原生|AWS|日本东京0[6-9]')


def build_policy():
    lines = []
    lines.append('; ================= 核心策略组 =================')
    # 🚀 节点选择：手动选择，可切到任意国家组
    region_groups = []
    for name, _ in REGIONS:
        region_groups += [name + '-自动', name + '-手动']
    lines.append(
        'static=🚀 节点选择, ♻️ 所有-自动, ' + ', '.join(region_groups) +
        ', 🎯 全球直连, 🎵 流媒体')
    # 所有节点自动（排除机场广告类 tag）
    lines.append(
        'url-latency-benchmark=♻️ 所有-自动, server-tag-regex=(?i)^((?!过期|剩余|流量|官网|到期|'
        '订阅|群组|网址|客服).)*$, check-interval=900, tolerance=50, alive-checking=true')
    # 流媒体专用：只测吞吐高的节点
    lines.append(
        f'url-latency-benchmark=🎵 流媒体, server-tag-regex=(?i).*({STREAM_RE}).*, '
        'check-interval=600, tolerance=30, alive-checking=true')
    lines.append('static=🎯 全球直连, direct')
    lines.append('static=🛑 广告拦截, reject')
    lines.append('static=🐟 兜底分流, 🚀 节点选择, ♻️ 所有-自动, 🎯 全球直连')
    lines.append('')
    lines.append('; ================= 国家/地区分组 =================')
    for name, pat in REGIONS:
        auto = f'{name}-自动'
        manual = f'{name}-手动'
        # 自动：延迟测速
        lines.append(
            f'url-latency-benchmark={auto}, server-tag-regex=(?i).*({pat}).*, '
            'check-interval=900, tolerance=50, alive-checking=true')
        # 手动：静态选择（引用自动组 + 直连，避免列举节点名）
        lines.append(f'static={manual}, {auto}, 🎯 全球直连')
    return lines


def main():
    if not os.path.exists(SRC):
        print(f'源配置不存在: {SRC}')
        return 1
    with open(SRC, encoding='utf-8') as f:
        txt = f.read().replace('\r\n', '\n')

    policy = build_policy()
    print(f'新策略组行数: {len([l for l in policy if l.strip() and not l.strip().startswith(";")])}')

    # 替换 [policy] 段
    lines = txt.split('\n')
    out, i, done = [], 0, False
    while i < len(lines):
        if lines[i].strip() == '[policy]':
            out.append(lines[i])
            out.extend(policy)
            i += 1
            while i < len(lines) and not lines[i].startswith('['):
                i += 1
            done = True
            continue
        out.append(lines[i])
        i += 1
    if not done:
        print('未找到 [policy] 段')
        return 1

    # 把流媒体的兜底分流改到新组（Spotify/YouTube/Netflix 等走 🎵 流媒体）
    STREAM_HOSTS = ['spotify.com', 'scdn.co', 'spotifycdn.com', 'youtube.com',
                    'googlevideo.com', 'netflix.com', 'nflxvideo.net', 'disneyplus.com',
                    'hbomax.com', 'twitch.tv', 'soundcloud.com', 'kkbox.com']
    res, on = [], False
    for l in out:
        if l.strip() == '[filter_local]':
            on = True
            res.append(l)
            res.append('; ---- 流媒体走专用组（吞吐优先）----')
            for h in STREAM_HOSTS:
                res.append(f'host-suffix, {h}, 🎵 流媒体')
            continue
        if on and l.startswith('['):
            on = False
        # 删掉原有的重复流媒体规则（避免先后覆盖）
        if on and re.match(r'^host-suffix,\s*(spotify|youtube|googlevideo|netflix)', l.strip(), re.I):
            continue
        res.append(l)

    dst = SRC
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(res))
    print(f'已写入 {dst}  {os.path.getsize(dst)} 字节')

    # 自检
    body = '\n'.join(res)
    n_policy = len(re.findall(r'(?m)^(static|url-latency-benchmark|available|round-robin)=', body))
    n_sec = len(re.findall(r'(?m)^\[.+\]$', body))
    print(f'  段头 {n_sec}   策略定义 {n_policy}')
    print(f'  含 CR: {open(dst,"rb").read().count(13)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

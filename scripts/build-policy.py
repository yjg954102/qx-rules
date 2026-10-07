#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略组 + 分流规则生成器（规范版）。

架构：一份配置，一个「总开关」策略组
  🔀 全局-在家直连还是走节点
     在家 → 🎯 全球直连      （流量交给旁路由 sing-box）
     出门 → ♻️ 自动优选 / 某国家组
  12 个用途组都指向总开关，改一处即可全站切换。

输入  scripts/qx-template.conf（含 {AUTO:policy} / {AUTO:filter_local} 占位符）
输出  qx-integrated.conf（完整可用配置）

节点来源优先级：
  1) --nodes-url 指定的 URL（默认聚合器 qx-compatible-all.txt）
  2) 模板 [policy] 段里已有的节点（离线兜底）
  3) 都取不到 → 报错退出（避免生成没有节点的配置）

拨测过滤：能读到聚合器拨测结果时自动剔除失败节点（--no-probe 可关闭）
"""
import argparse
import json
import os
import re
import sys
import urllib.request

UA = {'User-Agent': 'Quantumult X'}
# 节点源按顺序尝试：路由器聚合器 → 仓库内清单（GitHub Actions 用这个）
NODES_SOURCES = [
    'http://192.168.50.2:8109/output/qx-compatible-all.txt',
    'http://127.0.0.1:8109/output/qx-compatible-all.txt',
    'output/nodes-qx-compatible.txt',
]
DEFAULT_NODES_URL = NODES_SOURCES[0]
PROBE_FILE = '/opt/open-box/data/subscription-aggregator/probe-results.json'
PUB_FILE = '/opt/open-box/data/subscription-aggregator/published-nodes.json'

REGIONS = [
    ('美国', r'美国|US|United States|圣何塞|洛杉矶|西雅图|芝加哥'),
    ('香港', r'香港|HK|Hong Kong|hkt|i-Cable|HGC'),
    ('日本', r'日本|JP|Japan|东京|大阪'),
    ('新加坡', r'新加坡|SG|Singapore'),
    ('台湾', r'台湾|TW|Taiwan'),
    ('英国', r'英国|UK|Britain|伦敦'),
    ('加拿大', r'加拿大|CA|Canada'),
    ('越南', r'越南|VN|Vietnam'),
    ('德国', r'德国|DE|Germany'),
    ('其他', r''),
]
SERVICES = [
    ('🤖 AI', '美国', ['openai.com', 'chatgpt.com', 'oaistatic.com', 'oaiusercontent.com',
                       'anthropic.com', 'claude.ai', 'gemini.google.com',
                       'generativelanguage.googleapis.com', 'copilot.microsoft.com',
                       'perplexity.ai', 'poe.com', 'mistral.ai', 'x.ai', 'groq.com',
                       'cursor.com', 'midjourney.com', 'stability.ai', 'huggingface.co',
                       'replicate.com', 'together.ai', 'openrouter.ai']),
    ('📺 油管', '日本', ['youtube.com', 'youtu.be', 'ytimg.com', 'googlevideo.com',
                         'yt3.ggpht.com', 'youtubei.googleapis.com', 'youtube-nocookie.com',
                         'ggpht.com', 'youtube.googleapis.com']),
    ('🎬 流媒体', '香港', ['netflix.com', 'nflxvideo.net', 'nflximg.net', 'nflxso.net',
                          'nflxext.com', 'disneyplus.com', 'dssott.com', 'bamgrid.com',
                          'hbomax.com', 'max.com', 'primevideo.com', 'amazonvideo.com',
                          'aiv-cdn.net', 'hulu.com', 'spotify.com', 'scdn.co',
                          'spotifycdn.com', 'soundcloud.com', 'tidal.com', 'deezer.com',
                          'kkbox.com', 'twitch.tv', 'ttvnw.net', 'crunchyroll.com',
                          'vrv.co', 'abema.tv', 'dazn.com']),
    ('💬 电报', '新加坡', ['telegram.org', 't.me', 'telegram.me', 'tdesktop.com',
                          'telegra.ph', 'telesco.pe', 'cdn-telegram.org', 'contest.com',
                          'graph.org']),
    ('🐦 社交', '美国', ['twitter.com', 'x.com', 'twimg.com', 't.co', 'facebook.com',
                        'fbcdn.net', 'instagram.com', 'cdninstagram.com', 'reddit.com',
                        'redd.it', 'redditmedia.com', 'discord.com', 'discordapp.com',
                        'discord.gg', 'threads.net', 'tiktok.com', 'tiktokcdn.com',
                        'linkedin.com', 'licdn.com']),
    ('🔍 谷歌', '日本', ['google.com', 'googleapis.com', 'gstatic.com',
                        'googleusercontent.com', 'gmail.com', 'googlemail.com',
                        'googletagmanager.com', 'google.co.jp', 'google.com.hk',
                        'google.com.tw', 'withgoogle.com', 'recaptcha.net']),
    ('📦 微软', '美国', ['microsoft.com', 'live.com', 'msn.com', 'office.com',
                        'office365.com', 'azure.com', 'azureedge.net', 'msecnd.net',
                        'windowsupdate.com', 'visualstudio.com', 'onedrive.com',
                        'sharepoint.com', 'outlook.com', 'bing.com', 'microsoftonline.com']),
    ('🍎 苹果', '香港', ['apple.com', 'icloud.com', 'icloud.com.cn', 'mzstatic.com',
                        'cdn-apple.com', 'aaplimg.com', 'apple-cloudkit.com', 'me.com',
                        'itunes.com', 'appstore.com']),
    ('🎮 游戏', '日本', ['steampowered.com', 'steamcommunity.com', 'steamstatic.com',
                        'steamcontent.com', 'epicgames.com', 'unrealengine.com',
                        'playstation.com', 'sony.com', 'xbox.com', 'xboxlive.com',
                        'nintendo.com', 'nintendo.net', 'battle.net', 'blizzard.com',
                        'riotgames.com', 'ea.com', 'ubisoft.com', 'rockstargames.com',
                        'gog.com', 'roblox.com', 'supercell.com']),
    ('📥 下载', '美国', ['github.com', 'githubusercontent.com', 'githubassets.com',
                        'gitlab.com', 'sourceforge.net', 'mega.nz', 'mediafire.com',
                        'dropbox.com', '1drv.ms', 'archive.org']),
    ('📰 资讯', '美国', ['bbc.com', 'bbc.co.uk', 'cnn.com', 'nytimes.com', 'wsj.com',
                        'reuters.com', 'bloomberg.com', 'theguardian.com',
                        'washingtonpost.com', 'economist.com', 'ft.com', 'nikkei.com',
                        'asahi.com', 'medium.com', 'substack.com', 'wikipedia.org',
                        'wikimedia.org']),
    ('🛒 境外购物', '美国', ['amazon.com', 'amazon.co.jp', 'amazonaws.com', 'ebay.com',
                            'aliexpress.com', 'alibaba.com', 'etsy.com', 'walmart.com',
                            'target.com', 'bestbuy.com', 'rakuten.co.jp', 'yahoo.co.jp',
                            'mercari.com', 'shein.com', 'temu.com']),
]
GENERAL = [
    'server_check_url=http://developers.google.cn/generate_204',
    'network_check_url=http://www.google.cn',
    'dns_exclusion_list=*.local, *.lan',
    'icmp_auto_reply=true',
    'server_check_timeout=2000',
    'udp_whitelist=1-65535',
    'fallback_udp_policy=direct',
]
DOMESTIC = ['weixin.qq.com', 'qq.com', 'wechat.com', 'qpic.cn', 'qlogo.cn',
            'gtimg.cn', 'gtimg.com', 'qqmail.com', 'tencent-cloud.net', 'tencent.com',
            'alipay.com', 'alipayobjects.com', 'taobao.com', 'tmall.com', 'alicdn.com',
            'aliyuncs.com', 'amap.com', 'autonavi.com', 'douyin.com', 'bytedance.com',
            'snssdk.com', 'jd.com', 'meituan.com', 'dianping.com', 'baidu.com',
            'bdstatic.com', 'weibo.com', 'sinaimg.cn', 'zhihu.com', 'bilibili.com',
            'hdslb.com']
SWITCH = '🔀 全局-在家直连还是走节点'
RULE_RE = re.compile(r'\surl(-and-header)?\s+\S')


def fetch_tags(url, timeout=30):
    """支持 http(s) URL 与本地文件路径"""
    try:
        if url.startswith(('http://', 'https://')):
            t = urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout).read().decode('utf-8', 'replace')
        else:
            t = open(url, encoding='utf-8').read()
    except Exception as e:
        print(f'  [WARN] 节点源不可达({url[:56]}): {str(e)[:44]}', file=sys.stderr)
        return []
    tags = []
    for line in t.splitlines():
        m = re.search(r'tag=([^,]+)$', line.strip())
        if m:
            tags.append(m.group(1).strip())
    return tags


def tags_from_template(path):
    """离线兜底：从模板 [policy] 段里已有的节点提取"""
    if not os.path.exists(path):
        return []
    t = open(path, encoding='utf-8').read()
    m = re.search(r'(?m)^static=' + re.escape(SWITCH) + r',\s*(.+)$', t)
    if m:
        items = [x.strip() for x in m.group(1).split(',')]
        return [x for x in items if x and not x.startswith('🎯')]
    return []


def dead_tags():
    try:
        res = (json.load(open(PROBE_FILE, encoding='utf-8')) or {}).get('results') or {}
        nd = json.load(open(PUB_FILE, encoding='utf-8'))
        nodes = nd if isinstance(nd, list) else (nd.get('nodes') or [])
        meta = {str(n.get('id')): n.get('tag', '') for n in nodes if isinstance(n, dict)}
        return {meta.get(str(k), '') for k, v in res.items() if not v.get('success')}
    except Exception:
        return set()


def build_policy(tags, buckets):
    ctry = list(buckets)
    svc_names = [n for n, _, _ in SERVICES]
    L = [
        '; ============ 【总开关】改这一行即可全站切换 ============',
        ';   在家 → 选「🎯 全球直连」',
        ';   出门 → 选「♻️ 自动优选」或某个国家组（美国/日本/香港…）',
        ';   下面 12 个 🌐 用途组都跟随它，无需逐个修改',
        f'static={SWITCH}, 🎯 全球直连, ♻️ 自动优选, ' + ', '.join(ctry) + ', 🚀 手动选节点',
        '',
        '; ========== 核心组 ==========',
        'static=🎯 全球直连, direct',
        'static=🛑 广告拦截, reject',
        'static=🚀 手动选节点, ' + ', '.join(tags),
        'static=♻️ 自动优选, ' + ', '.join(tags),
        '',
        '; ========== ★国家/地区（含该国全部可用节点）==========',
    ]
    for name, v in buckets.items():
        L.append(f'static={name}, ' + ', '.join(v))
    L += ['', '; ========== 🌐 用途组（跟随 🔀 总开关）==========']
    for name, default, _ in SERVICES:
        L.append(f'static={name}, {SWITCH}, '
                 f'{default if default in buckets else ctry[0]}, 🎯 全球直连')
    return L


def build_filter_local():
    L = ['; ===== 境外服务：按用途分流 =====']
    for name, _, domains in SERVICES:
        L.append(f'; ---- {name} ----')
        L += [f'host-suffix, {d}, {name}' for d in domains]
    L.append('; ===== 国内 App：直连 =====')
    L += [f'host-suffix, {d}, 🎯 全球直连' for d in DOMESTIC]
    L += ['geoip, cn, 🎯 全球直连',
          '; final 也跟随总开关：在家=直连，出门=走节点',
          f'final, {SWITCH}']
    return L


def apply_template(tpl_path, policy, filt):
    """把生成内容套进模板的占位符；同时用 GENERAL 覆盖 [general]"""
    t = open(tpl_path, encoding='utf-8').read().replace('\r\n', '\n')
    lines = t.split('\n')
    out, i = [], 0
    while i < len(lines):
        s = lines[i].strip()
        if s in ('[general]', '[policy]', '[filter_local]'):
            out.append(lines[i])
            body = (GENERAL if s == '[general]' else
                    policy if s == '[policy]' else filt)
            out.extend(body)
            i += 1
            while i < len(lines) and not lines[i].startswith('['):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def validate(body):
    """引用完整性校验：所有被引用的策略必须已定义"""
    defined, on = set(), False
    for l in body:
        if l.strip() == '[policy]':
            on = True
            continue
        if on and l.startswith('['):
            break
        if on:
            m = re.match(r'^(?:static|url-latency-benchmark|available|round-robin|dest-hash)\s*=\s*([^,]+),', l)
            if m:
                defined.add(m.group(1).strip())
    refs, on = set(), False
    for l in body:
        if l.strip() == '[filter_local]':
            on = True
            continue
        if on and l.startswith('['):
            break
        if on and l.strip() and not l.strip().startswith(';'):
            p = [x.strip() for x in l.split(',')]
            if len(p) >= 3:
                refs.add(p[-1])
    for l in body:
        m = re.match(r'^final,\s*(.+)$', l.strip())
        if m:
            refs.add(m.group(1).strip())
    builtin = {'direct', 'reject', 'proxy'}
    bad = [r for r in refs if r not in defined and r not in builtin]
    return defined, refs, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', default='scripts/qx-template.conf')
    ap.add_argument('--out', default='qx-integrated.conf')
    ap.add_argument('--nodes-url', default=DEFAULT_NODES_URL)
    ap.add_argument('--no-probe', action='store_true')
    a = ap.parse_args()
    # 让 output/... 这类相对路径基于仓库根（脚本的上级目录）
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # 依次尝试：命令行指定 → 路由器聚合器 → 仓库内清单
    sources = []
    if a.nodes_url and a.nodes_url != DEFAULT_NODES_URL:
        sources.append(a.nodes_url)
    sources += [u for u in NODES_SOURCES if u not in sources]
    tags, src = [], ''
    for u in sources:
        tags = fetch_tags(u)
        if tags:
            src = u
            break
    if not tags:
        tags = tags_from_template(a.template)
        src = '模板兜底'
    if not tags:
        print('[ERROR] 取不到节点，拒绝生成无节点配置', file=sys.stderr)
        return 1
    print(f'节点 {len(tags)} 个（来源：{src}）')

    skip = set() if a.no_probe else dead_tags()
    if skip:
        before = len(tags)
        tags = [t for t in tags if t not in skip]
        print(f'拨测剔除 {before - len(tags)} 个坏节点')

    buckets, used = {}, set()
    for name, pat in REGIONS:
        v = ([x for x in tags if x not in used] if not pat
             else [x for x in tags if re.search(pat, x, re.I) and x not in used])
        if v:
            buckets[name] = v
            used.update(v)
    print('国家组: ' + ', '.join(f'{k}({len(v)})' for k, v in buckets.items()))

    policy = build_policy(tags, buckets)
    filt = build_filter_local()
    body = apply_template(a.template, policy, filt)

    defined, refs, bad = validate(body)
    print(f'策略组 {len(defined)} 个  被引用 {len(refs)} 个')
    if bad:
        print(f'[ERROR] 未定义的策略引用: {bad}', file=sys.stderr)
        return 1
    print('引用校验 ✅ 通过')

    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(body))
    txt = '\n'.join(body)
    print(f'已写出 {a.out}  {os.path.getsize(a.out)} 字节')
    print(f'  段头 {len(re.findall(chr(94) + r"\[.+\]$", txt, re.M))}  '
          f'策略 {len(defined)}  本地分流 {len(filt)} 行')
    return 0


if __name__ == '__main__':
    sys.exit(main())

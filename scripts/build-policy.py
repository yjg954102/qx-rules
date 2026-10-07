# -*- coding: utf-8 -*-
"""重新设计：国家组为主路径，用途组为快捷入口。

用户诉求：「按国家选择」—— 选一个国家后，各类服务都用该国的节点。

设计：
  · 🚀 节点选择     含全部节点（兜底，任何节点都能选到）
  · 国家组（10 个） 放在最前，每个含该国【全部】节点 ← 主入口
  · 用途组（12 个） 只引用国家组，不写死节点 ← 快捷入口
  · 核心组（4 个）  直连 / 拦截 / 兜底

组数：4 + 10 + 12 = 26（QX 上限 38，安全）

用途组的默认指向（可按需在界面改）：
  🤖 AI → 美国         📺 油管 → 日本      🎬 流媒体 → 香港
  💬 电报 → 新加坡      🐦 社交 → 美国      🔍 谷歌 → 日本
  📦 微软 → 美国        🍎 苹果 → 香港      🎮 游戏 → 日本
  📥 下载 → 美国        📰 资讯 → 美国      🛒 境外购物 → 美国
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
    ('日本', r'日本|JP|Japan|东京|大阪'),
    ('新加坡', r'新加坡|SG|Singapore'),
    ('台湾', r'台湾|TW|Taiwan'),
    ('英国', r'英国|UK|Britain|伦敦'),
    ('加拿大', r'加拿大|CA|Canada'),
    ('越南', r'越南|VN|Vietnam'),
    ('德国', r'德国|DE|Germany'),
    ('其他', r''),
]

# 用途组：组名 -> (默认指向的国家组, 域名列表)
SERVICES = [
    ('🤖 AI', '美国',
     ['openai.com', 'chatgpt.com', 'oaistatic.com', 'oaiusercontent.com',
      'anthropic.com', 'claude.ai', 'gemini.google.com',
      'generativelanguage.googleapis.com', 'copilot.microsoft.com',
      'perplexity.ai', 'poe.com', 'mistral.ai', 'x.ai', 'groq.com',
      'cursor.com', 'midjourney.com', 'stability.ai', 'huggingface.co',
      'replicate.com', 'together.ai', 'openrouter.ai']),
    ('📺 油管', '日本',
     ['youtube.com', 'youtu.be', 'ytimg.com', 'googlevideo.com', 'yt3.ggpht.com',
      'youtubei.googleapis.com', 'youtube-nocookie.com', 'ggpht.com',
      'youtube.googleapis.com']),
    ('🎬 流媒体', '香港',
     ['netflix.com', 'nflxvideo.net', 'nflximg.net', 'nflxso.net', 'nflxext.com',
      'disneyplus.com', 'dssott.com', 'bamgrid.com', 'hbomax.com', 'max.com',
      'primevideo.com', 'amazonvideo.com', 'aiv-cdn.net', 'hulu.com',
      'spotify.com', 'scdn.co', 'spotifycdn.com', 'soundcloud.com',
      'tidal.com', 'deezer.com', 'kkbox.com', 'twitch.tv', 'ttvnw.net',
      'crunchyroll.com', 'vrv.co', 'abema.tv', 'dazn.com']),
    ('💬 电报', '新加坡',
     ['telegram.org', 't.me', 'telegram.me', 'tdesktop.com', 'telegra.ph',
      'telesco.pe', 'cdn-telegram.org', 'contest.com', 'graph.org']),
    ('🐦 社交', '美国',
     ['twitter.com', 'x.com', 'twimg.com', 't.co', 'facebook.com', 'fbcdn.net',
      'instagram.com', 'cdninstagram.com', 'reddit.com', 'redd.it', 'redditmedia.com',
      'discord.com', 'discordapp.com', 'discord.gg', 'threads.net',
      'tiktok.com', 'tiktokcdn.com', 'linkedin.com', 'licdn.com']),
    ('🔍 谷歌', '日本',
     ['google.com', 'googleapis.com', 'gstatic.com', 'googleusercontent.com',
      'gmail.com', 'googlemail.com', 'googletagmanager.com', 'google.co.jp',
      'google.com.hk', 'google.com.tw', 'withgoogle.com', 'recaptcha.net']),
    ('📦 微软', '美国',
     ['microsoft.com', 'live.com', 'msn.com', 'office.com', 'office365.com',
      'azure.com', 'azureedge.net', 'msecnd.net', 'windowsupdate.com',
      'visualstudio.com', 'onedrive.com', 'sharepoint.com', 'outlook.com',
      'bing.com', 'microsoftonline.com']),
    ('🍎 苹果', '香港',
     ['apple.com', 'icloud.com', 'icloud.com.cn', 'mzstatic.com', 'cdn-apple.com',
      'aaplimg.com', 'apple-cloudkit.com', 'me.com', 'itunes.com', 'appstore.com']),
    ('🎮 游戏', '日本',
     ['steampowered.com', 'steamcommunity.com', 'steamstatic.com', 'steamcontent.com',
      'epicgames.com', 'unrealengine.com', 'playstation.com', 'sony.com',
      'xbox.com', 'xboxlive.com', 'nintendo.com', 'nintendo.net',
      'battle.net', 'blizzard.com', 'riotgames.com', 'ea.com', 'ubisoft.com',
      'rockstargames.com', 'gog.com', 'roblox.com', 'supercell.com']),
    ('📥 下载', '美国',
     ['github.com', 'githubusercontent.com', 'githubassets.com', 'gitlab.com',
      'sourceforge.net', 'mega.nz', 'mediafire.com', 'dropbox.com', '1drv.ms',
      'archive.org']),
    ('📰 资讯', '美国',
     ['bbc.com', 'bbc.co.uk', 'cnn.com', 'nytimes.com', 'wsj.com', 'reuters.com',
      'bloomberg.com', 'theguardian.com', 'washingtonpost.com', 'economist.com',
      'ft.com', 'nikkei.com', 'asahi.com', 'medium.com', 'substack.com',
      'wikipedia.org', 'wikimedia.org']),
    ('🛒 境外购物', '美国',
     ['amazon.com', 'amazon.co.jp', 'amazonaws.com', 'ebay.com', 'aliexpress.com',
      'alibaba.com', 'etsy.com', 'walmart.com', 'target.com', 'bestbuy.com',
      'rakuten.co.jp', 'yahoo.co.jp', 'mercari.com', 'shein.com', 'temu.com']),
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

    buckets, used = {}, set()
    for name, pat in REGIONS:
        if not pat:
            v = [x for x in tags if x not in used]
        else:
            rx = re.compile(pat, re.I)
            v = [x for x in tags if rx.search(x) and x not in used]
        if v:
            buckets[name] = v
            used.update(v)
    print('国家组: ' + ', '.join(f'{k}({len(v)})' for k, v in buckets.items()))

    ctry = list(buckets)
    svc_names = [n for n, _, _ in SERVICES]

    L = []
    L.append('; ========== 核心（4）==========')
    L.append('static=🚀 节点选择, ' + ', '.join(tags))
    L.append('static=🐟 兜底分流, 🚀 节点选择, 🎯 全球直连')
    L.append('static=🎯 全球直连, direct')
    L.append('static=🛑 广告拦截, reject')
    L.append('')
    L.append('; ========== ★国家/地区（主要选择入口，含该国全部节点）==========')
    for name, v in buckets.items():
        L.append(f'static={name}, ' + ', '.join(v))
    L.append('')
    L.append('; ========== 用途快捷入口（选国家组即可，此处默认指向常用国家）==========')
    for name, default, _ in SERVICES:
        if default not in buckets:
            default = ctry[0]
        L.append(f'static={name}, {default}, 🎯 全球直连')

    total = len([x for x in L if x.startswith('static=')])
    print(f'\n策略定义 {total} 组（QX 上限 38）')

    lines = open(SRC, encoding='utf-8').read().replace('\r\n', '\n').split('\n')
    out, i = [], 0
    while i < len(lines):
        s = lines[i].strip()
        if s in ('[general]', '[policy]'):
            out.append(lines[i])
            out.extend(GENERAL if s == '[general]' else L)
            i += 1
            while i < len(lines) and not lines[i].startswith('['):
                i += 1
            continue
        out.append(lines[i])
        i += 1

    # 分流：用途组 -> 各自的组；用途组本身指向默认国家组
    svc_rules = []
    for name, _, domains in SERVICES:
        svc_rules.append(f'; ---- {name} ----')
        for d in domains:
            svc_rules.append(f'host-suffix, {d}, {name}')

    res, on = [], False
    for l in out:
        if l.strip() == '[filter_local]':
            on = True
            res.append(l)
            res.append('; ===== 境外服务：按用途分流 =====')
            res.extend(svc_rules)
            res.append('; ===== 国内 App：直连 =====')
            for d in DOMESTIC:
                res.append(f'host-suffix, {d}, 🎯 全球直连')
            res.append('geoip, cn, 🎯 全球直连')
            res.append('final, 🐟 兜底分流')
            continue
        if on and l.startswith('['):
            on = False
        if on:
            continue
        res.append(l)

    with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(res))
    body = '\n'.join(res)
    print(f'已写入 {SRC}  {os.path.getsize(SRC)} 字节')
    print(f'  段头 {len(re.findall(chr(94) + r"\[.+\]$", body, re.M))}   static {total}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

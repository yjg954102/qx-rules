#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 output/ 已合并的规则重建三类派生订阅，供主配置（qx-integrated.conf）使用。

由 GitHub Actions 每天在 merge.ps1 / annotate.ps1 之后调用。

产出：
  output/rewrite-category/   App 按类别分组（约 13 个文件）
  output/filter-platform/    分流按广告联盟分组（约 12 个文件）
  output/moyu/               墨鱼（ddgksf2013）复写，按 App 独立（约 30 个文件）

要点：
  · 所有输出强制 LF 行尾 —— QX 不接受行尾 \r，否则规则数显示 0
  · 所有输出以 \n 结尾，无 BOM
"""
import collections
import concurrent.futures as cf
import json
import os
import re
import sys
import urllib.parse
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'output')
AXE = '🛑 广告拦截'

# ---------------------------------------------------------------- 类别定义
REWRITE_CATS = collections.OrderedDict([
    ('视频影视', ['视频', '影视', '电视', 'TV', '直播', '动漫', '电影', '影院', '剧场', '短剧',
                  '优酷', '爱奇艺', '腾讯视频', '芒果', 'B站', '哔哩', '抖音', '快手', '西瓜',
                  'netflix', 'youtube', 'disney', 'crunchyroll', '体育', '球']),
    ('音乐音频', ['音乐', 'K歌', '听书', '有声', '电台', '播客', 'FM', 'music',
                  '网易云', '酷狗', '酷我', '唱吧', '蜻蜓', '喜马拉雅', '荔枝']),
    ('购物电商', ['购物', '商城', '超市', '优选', '买菜', '外卖', '团购', '电商', '店铺',
                  '淘宝', '天猫', '京东', '拼多多', '苏宁', '唯品', '闲鱼', '得物', '小红书',
                  '美团', '饿了么', '朴朴', '叮咚', '盒马', '永辉', '便利店', '咖啡', '奶茶',
                  '麦当劳', '肯德基', '星巴克', '瑞幸', '山姆', '沃尔玛']),
    ('出行地图', ['地图', '导航', '出行', '打车', '出租', '租车', '代驾', '单车', '公交', '地铁',
                  '航空', '机票', '火车', '高铁', '酒店', '民宿', '旅行', '旅游',
                  '高德', '滴滴', '携程', '去哪儿', '飞猪', '同程', '途牛', '12306',
                  '顺丰', '快递', '物流']),
    ('金融支付', ['银行', '证券', '基金', '保险', '理财', '支付', '钱包', '信用卡', '投资',
                  '股市', '股票', '行情', '财经', '比特', '币', '交易所', '银联',
                  '支付宝', '工商', '建设', '招商', '平安', '中信', '兴业', '浦发', '民生']),
    ('阅读小说', ['小说', '阅读', '读书', '书城', '文学', '漫画', '杂志', '报纸',
                  '起点', '番茄', '七猫', '掌阅', '晋江', '知网', '豆瓣']),
    ('社交社区', ['社交', '聊天', '社区', '论坛', '微博', '贴吧', '交友', '婚恋', '相册',
                  '微信', 'QQ', '钉钉', '陌陌', '探探', 'Soul', '虎扑', '知乎']),
    ('游戏娱乐', ['游戏', '电竞', '王者', '和平', '原神', '崩坏', '米哈游',
                  'steam', 'epic', 'tap', '棋牌', '彩票', '抽奖', '盲盒', '潮玩']),
    ('教育学习', ['英语', '单词', '学习', '课程', '课堂', '教育', '培训', '考试', '题库', '作业',
                  '词典', '翻译', '论文', '学校', '大学', '考研', '公考', '驾照']),
    ('工具效率', ['浏览器', '输入法', '清理', '管家', '安全', '加速', '助手', '工具箱',
                  '网盘', '云盘', '压缩', '扫描', '打印', '笔记', '日历', '天气', '闹钟',
                  '相机', '拍照', '修图', '剪辑', '录屏', '健康', '运动', '计步', '体重']),
    ('新闻资讯', ['新闻', '资讯', '头条', '快报', '日报', '晚报', '观察', '科技', '汽车', '军事']),
    ('生活服务', ['生活', '家政', '装修', '房产', '租房', '招聘', '求职', '医疗', '医院', '挂号',
                  '药', '宠物', '母婴', '育儿', '政务', '社保', '公积金', '缴费']),
])

PLATFORMS = collections.OrderedDict([
    ('腾讯系', ['qq.com', 'gtimg', 'qpic', 'tencent', 'weixin', 'qlogo', 'gdt.', 'qcloud',
                'myapp.com', 'qqmail']),
    ('字节系', ['bytedance', 'toutiao', 'pstatp', 'snssdk', 'ixigua', 'douyin', 'pangolin',
                'byteimg', 'zjcdn', 'feelgood', 'amemv']),
    ('阿里系', ['alibaba', 'taobao', 'tmall', 'alicdn', 'alimama', 'aliyun', 'alipay',
                'mmstat', 'tanx', 'uc.cn', 'umeng', 'etao', 'fliggy', 'dingtalk']),
    ('百度系', ['baidu', 'bdstatic', 'hao123', '91.com', 'nuomi', 'iqiyi', 'zhidao']),
    ('快手系', ['kuaishou', 'gifshow', 'kwai', 'yximgs']),
    ('京东系', ['jd.com', '360buy', 'jd.hk', 'jingdong']),
    ('美团系', ['meituan', 'dianping', 'mtstat', 'meituan.net']),
    ('网易系', ['163.com', '126.net', 'netease', '127.net', 'lofter', 'youdao']),
    ('新浪微博', ['sina', 'weibo', 'sinaimg', 'wbcdn']),
    ('搜狐系', ['sohu', '56.com', 'chinaren']),
    ('第三方广告联盟', ['umengcloud', 'cnzz', 'talkingdata', 'adjust.com', 'appsflyer',
                        'branch.io', 'kochava', 'tenjin', 'bugly', 'sensorsdata',
                        'growingio', 'mixpanel', 'firebase', 'crashlytics',
                        'adsystem', 'doubleclick', 'googlesyndication', 'adservice',
                        'applovin', 'unityads', 'vungle', 'ironsrc', 'chartboost',
                        'mintegral', 'topon', 'gromore', 'adscope', 'adsmogo', 'mob']),
])

# 墨鱼可用文件（GitHub 源；.top 站点有防盗链，不可用）
MOYU_RAW = 'https://raw.githubusercontent.com/ddgksf2013/Rewrite/master'
MOYU = {
    '解锁-Emby': f'{MOYU_RAW}/Function/EmbyPlugin.conf',
    '增强-B站字幕': f'{MOYU_RAW}/Function/Bilibili_CC.conf',
    '功能-微信解封链接': f'{MOYU_RAW}/Function/UnblockURLinWeChat.conf',
    '功能-优铺重定向': f'{MOYU_RAW}/Function/UposRedirect.conf',
    '净化-高德地图': f'{MOYU_RAW}/AdBlock/AmapAds.conf',
    '净化-微信小程序': f'{MOYU_RAW}/AdBlock/Applet.conf',
    '净化-B站漫画': f'{MOYU_RAW}/AdBlock/BiliBiliComicsAds.conf',
    '净化-Bing': f'{MOYU_RAW}/AdBlock/BingSimplify.conf',
    '净化-菜鸟裹裹': f'{MOYU_RAW}/AdBlock/CainiaoAds.conf',
    '净化-彩云天气': f'{MOYU_RAW}/AdBlock/CaiYunAds.conf',
    '净化-车来了': f'{MOYU_RAW}/AdBlock/CheLaiLeAds.conf',
    '净化-中国联通': f'{MOYU_RAW}/AdBlock/ChinaUnicomAds.conf',
    '净化-假iOS广告': f'{MOYU_RAW}/AdBlock/FakeiOSAds.conf',
    '净化-闲鱼': f'{MOYU_RAW}/AdBlock/GoofishAds.conf',
    '净化-Keep': f'{MOYU_RAW}/AdBlock/KeepAds.conf',
    '净化-墨迹天气': f'{MOYU_RAW}/AdBlock/MoJiWeatherAds.conf',
    '净化-网易云音乐': f'{MOYU_RAW}/AdBlock/NeteaseAds.conf',
    '净化-网易邮箱': f'{MOYU_RAW}/AdBlock/NeteaseMailAds.conf',
    '净化-汽水音乐': f'{MOYU_RAW}/AdBlock/QiShuiMusicAds.conf',
    '净化-Reddit': f'{MOYU_RAW}/AdBlock/RedditAds.conf',
    '净化-什么值得买': f'{MOYU_RAW}/AdBlock/SmzdmAds.conf',
    '净化-淘票票': f'{MOYU_RAW}/AdBlock/TaoPiaoPiaoAds.conf',
    '净化-百度贴吧': f'{MOYU_RAW}/AdBlock/TieBaAds.conf',
    '净化-微信': f'{MOYU_RAW}/AdBlock/WeChat.conf',
    '净化-微博': f'{MOYU_RAW}/AdBlock/WeiboAds.conf',
    '净化-小宇宙': f'{MOYU_RAW}/AdBlock/XiaoYuZhouAds.conf',
    '净化-喜马拉雅': f'{MOYU_RAW}/AdBlock/Ximalaya.conf',
    '净化-YouTube': f'{MOYU_RAW}/AdBlock/YoutubeAds.conf',
    '网页-豆瓣': f'{MOYU_RAW}/Html/Douban.conf',
    '网页-无尽Google': f'{MOYU_RAW}/Html/EndlessGoogle.conf',
}

RULE_RE = re.compile(r'\surl(-and-header)?\s+\S')


def read_text(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read().replace('\r\n', '\n').replace('\r', '\n')


def write_lf(path, lines):
    """写文件：强制 LF、无 BOM、以 \\n 结尾"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = '\n'.join(lines) + '\n'
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(data)
    os.chmod(path, 0o644)
    return len(lines)


def get(url, timeout=60):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read().decode('utf-8', 'replace')


# ================================================================ 1. 重写分类
def build_rewrite_categories():
    print('==== [1/3] 重写规则按 App 类别')
    appdir = os.path.join(OUT, 'per-app')
    if not os.path.isdir(appdir):
        print('  跳过：output/per-app 不存在')
        return 0
    files = [f for f in os.listdir(appdir) if f.endswith('.conf')]
    groups = collections.defaultdict(list)
    for f in files:
        name = f[:-5]
        low = name.lower()
        cat = '通用其他'
        for c, kws in REWRITE_CATS.items():
            if any(k.lower() in low for k in kws):
                cat = c
                break
        groups[cat].append(f)

    outdir = os.path.join(OUT, 'rewrite-category')
    n_files = 0
    for cat, names in groups.items():
        seen, lines = set(), []
        for f in sorted(names):
            rules = [l.strip() for l in read_text(os.path.join(appdir, f)).split('\n')
                     if l.strip() and not l.strip().startswith(('#', ';', '['))
                     and RULE_RE.search(l)]
            fresh = [r for r in rules if r not in seen]
            if not fresh:
                continue
            seen.update(fresh)
            lines.append(f';【{f[:-5]}】{len(fresh)} 条')
            lines.extend(fresh)
        if lines:
            n = write_lf(os.path.join(outdir, cat + '.conf'), lines)
            n_rules = len([l for l in lines if RULE_RE.search(l)])
            print(f'  {cat:<10} {len(names):>4} App  {n_rules:>4} 条')
            n_files += 1
    print(f'  → {n_files} 个文件')
    return n_files


# ================================================================ 2. 分流分类
def build_filter_platforms():
    print('==== [2/3] 分流规则按广告联盟')
    src = os.path.join(OUT, 'QX-AllInOne-Filter.conf')
    if not os.path.exists(src):
        print('  跳过：QX-AllInOne-Filter.conf 不存在')
        return 0
    rules = []
    for l in read_text(src).split('\n'):
        s = l.strip()
        if not s or s.startswith(('#', ';', '[')):
            continue
        p = [x.strip() for x in s.split(',')]
        if len(p) < 3:
            continue
        t, val = p[0].lower(), ','.join(p[1:-1]).strip()
        m = {'domain': 'host', 'host': 'host', 'domain-suffix': 'host-suffix',
             'host-suffix': 'host-suffix', 'domain-keyword': 'host-keyword',
             'host-keyword': 'host-keyword', 'domain-wildcard': 'host-wildcard',
             'host-wildcard': 'host-wildcard'}
        if t in m:
            rules.append((m[t], val))
        elif t in ('ip-cidr', 'ip6-cidr'):
            rules.append((t, val))
    rules = list(dict.fromkeys(rules))

    buckets = collections.OrderedDict((c, []) for c in PLATFORMS)
    buckets['长尾域名'] = []
    for t, val in rules:
        v = val.lower()
        hit = None
        for cat, kws in PLATFORMS.items():
            if any(k in v for k in kws):
                hit = cat
                break
        buckets[hit or '长尾域名'].append((t, val))

    outdir = os.path.join(OUT, 'filter-platform')
    n_files = 0
    for cat, items in buckets.items():
        if not items:
            continue
        items = sorted(set(items), key=lambda x: -len(x[1]))
        lines = [f'{t}, {v}, {AXE}, no-resolve' if t in ('ip-cidr', 'ip6-cidr')
                 else f'{t}, {v}, {AXE}' for t, v in items]
        write_lf(os.path.join(outdir, cat + '.conf'), lines)
        print(f'  {cat:<14} {len(lines):>6} 条')
        n_files += 1
    print(f'  → {n_files} 个文件')
    return n_files


# ================================================================ 3. 墨鱼复写
def build_moyu():
    print('==== [3/3] 墨鱼复写（按 App 独立）')
    outdir = os.path.join(OUT, 'moyu')

    def one(item):
        tag, url = item
        try:
            t = get(url)
        except Exception as e:
            return tag, None, str(e)[:50]
        hosts, rules, meta = [], [], False
        for raw in t.replace('\r\n', '\n').split('\n'):
            s = raw.strip()
            if s.startswith('// ==UserScript=='):
                meta = True
                continue
            if s.startswith('// ==/UserScript=='):
                meta = False
                continue
            if meta or s.startswith('// @') or not s or s.startswith('#'):
                continue
            m = re.match(r'^hostname\s*=\s*(.+)$', s, re.I)
            if m:
                hosts += [h.strip() for h in m.group(1).split(',') if h.strip()]
                continue
            if RULE_RE.search(s):
                rules.append(s)
        return tag, (rules, hosts), None

    ok, mitm = 0, []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for tag, res, err in ex.map(one, MOYU.items()):
            if err or not res:
                print(f'  FAIL {tag}: {err}')
                continue
            rules, hosts = res
            write_lf(os.path.join(outdir, tag + '.conf'), rules)
            mitm += hosts
            ok += 1
            print(f'  {tag:<20} {len(rules):>3} 条')

    mitm = sorted(set(h for h in mitm if h and not h.startswith('<')))
    write_lf(os.path.join(outdir, '_mitm-hostnames.txt'), [', '.join(mitm)])
    print(f'  → {ok} 个文件，MITM 主机名 {len(mitm)} 个')
    return ok


def main():
    print(f'仓库根：{ROOT}')
    a = build_rewrite_categories()
    b = build_filter_platforms()
    c = build_moyu()
    print(f'\n合计：重写分类 {a} + 分流分类 {b} + 墨鱼 {c}')

    # ---- 归一化：把输出目录里所有文件的 CRLF 转成 LF ----
    # 有些文件不是本脚本生成的（历史遗留/手工添加），可能带 CRLF，
    # 会让 QX 显示「0 条规则」。这里统一处理，避免因单个遗留文件让整个 CI 失败。
    fixed = 0
    for d in ('rewrite-category', 'filter-platform', 'moyu', 'per-app', 'per-domain'):
        dp = os.path.join(OUT, d)
        if not os.path.isdir(dp):
            continue
        for f in os.listdir(dp):
            p = os.path.join(dp, f)
            if not os.path.isfile(p):
                continue
            raw = open(p, 'rb').read()
            if b'\r' in raw:
                open(p, 'wb').write(raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n'))
                fixed += 1
                print(f'  归一化 CRLF → LF: {d}/{f}')
    if fixed:
        print(f'  共归一化 {fixed} 个文件')

    # ---- 自检：确保无 CR ----
    bad = []
    for d in ('rewrite-category', 'filter-platform', 'moyu'):
        dp = os.path.join(OUT, d)
        if not os.path.isdir(dp):
            continue
        for f in os.listdir(dp):
            p = os.path.join(dp, f)
            if os.path.isfile(p) and b'\r' in open(p, 'rb').read():
                bad.append(f'{d}/{f}')
    if bad:
        print(f'!! 仍有 CRLF 文件 {len(bad)} 个（QX 会显示 0 条规则）')
        for x in bad[:10]:
            print('   ' + x)
        return 1
    print('自检通过：所有输出均为 LF 行尾')
    return 0


if __name__ == '__main__':
    sys.exit(main())

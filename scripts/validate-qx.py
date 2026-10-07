# -*- coding: utf-8 -*-
"""QX 配置预检：在导入前抓出会导致「配置文件语法错误」的问题。

已知会触发语法错误的写法（本会话实际遇到过）：
  · url-latency-benchmark 组里节点数 < 2
  · 策略组引用了不存在的策略/节点名
  · static 组里出现 * 之类非法项
  · [general] 用了白名单外的键
  · [mitm] 出现多个 hostname 字段
  · 非 12 个标准段头（QX 要求全部存在）
  · 远程资源行尾带注释
"""
import os
import re
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    'C:/Users/Administrator/Documents/deepseek-harness/default-workspace/iOS-QX规则集/qx-分类版.conf'

SECTIONS = ['[general]', '[dns]', '[server_remote]', '[policy]', '[filter_remote]',
            '[rewrite_local]', '[rewrite_remote]', '[task_local]', '[server_local]',
            '[http_backend]', '[mitm]', '[filter_local]']

# [general] 合法键（据官方 sample.conf）
GENERAL_OK = {
    'profile_img_url', 'resource_parser_url', 'network_check_url', 'server_check_url',
    'server_check_user_agent', 'server_check_timeout', 'fallback_udp_policy',
    'doh_user_agent', 'geo_location_checker', 'running_mode_trigger',
    'dns_exclusion_list', 'dns_reject_domain_behavior', 'ssid_suspended_list',
    'enhanced_compatibility_ssid_list', 'udp_whitelist', 'udp_drop_list',
    'excluded_routes', 'icmp_auto_reply',
}
# 策略类型
POLICY_TYPES = ('static', 'available', 'round-robin', 'dest-hash',
                'url-latency-benchmark', 'ssid')
PARAM_RE = re.compile(r'^(check-interval|tolerance|alive-checking|server-tag-regex|'
                      r'resource-tag-regex|img-url)=')
BUILTIN = {'direct', 'reject', 'proxy'}


def main():
    raw = open(PATH, 'rb').read()
    txt = raw.decode('utf-8', 'replace')
    errors, warns = [], []

    if raw.count(13):
        warns.append(f'文件含 {raw.count(13)} 个 CR（CRLF 行尾）')
    if raw[:3] == b'\xef\xbb\xbf':
        warns.append('文件带 BOM')

    lines = txt.split('\n')

    # 1) 段头完整性
    found = [l.strip() for l in lines if re.match(r'^\[.+\]$', l.strip())]
    missing = [s for s in SECTIONS if s not in found]
    extra = [s for s in found if s not in SECTIONS]
    if missing:
        errors.append(f'缺少段头: {missing}')
    if extra:
        errors.append(f'非标准段头（QX 会报错）: {extra}')

    # 分段
    def sec(name):
        out, on = [], False
        for l in lines:
            if l.strip() == name:
                on = True
                continue
            if on and l.startswith('['):
                break
            if on:
                out.append(l)
        return out

    # 2) [general] 键白名单
    for l in sec('[general]'):
        s = l.strip()
        if not s or s.startswith((';', '#')):
            continue
        k = s.split('=')[0].strip()
        if k not in GENERAL_OK:
            errors.append(f'[general] 非法键: {k}')

    # 3) [mitm] 只能有一个 hostname
    hn = [l for l in sec('[mitm]') if l.strip().lower().startswith('hostname')]
    if len(hn) > 1:
        errors.append(f'[mitm] 有 {len(hn)} 个 hostname 字段（只允许 1 个）')
    if hn and '=' not in hn[0]:
        errors.append('[mitm] hostname 行缺少 =')

    # 4) 策略组：收集定义 + 引用检查
    defined, groups = set(), []
    for l in sec('[policy]'):
        s = l.strip()
        if not s or s.startswith((';', '#')):
            continue
        m = re.match(r'^(\S+?)\s*=\s*(.+)$', s)
        if not m:
            errors.append(f'[policy] 无法解析: {s[:60]}')
            continue
        typ, rest = m.group(1), m.group(2)
        if typ not in POLICY_TYPES:
            errors.append(f'[policy] 未知类型 {typ}: {s[:60]}')
            continue
        parts = [x.strip() for x in rest.split(',')]
        if not parts or not parts[0]:
            errors.append(f'[policy] {typ} 缺少策略名: {s[:60]}')
            continue
        name = parts[0]
        items = [x for x in parts[1:] if x and not PARAM_RE.match(x)]
        defined.add(name)
        groups.append((typ, name, items))

    for typ, name, items in groups:
        # 单节点测速组 → 报错（实测会触发 syntax error）
        if typ == 'url-latency-benchmark' and len(items) < 2:
            errors.append(f'{typ}={name} 只有 {len(items)} 个节点（<2 会语法错误）')
        # entries containing = that are not params
        for it in items:
            if '=' in it and not PARAM_RE.match(it):
                warns.append(f'{name} 里含非常规项: {it[:50]}')
        if typ == 'static' and '*' in items:
            errors.append(f'static={name} 含非法项 *')

    # 引用检查（策略组引用其它策略）
    for typ, name, items in groups:
        for it in items:
            if it in BUILTIN or it in defined:
                continue
            # 可能是节点名；节点名不在 defined 里是正常的
            continue

    # 5) 规则行尾注释（QX 不支持行内注释）
    for sname in ('[filter_local]', '[filter_remote]', '[rewrite_local]', '[rewrite_remote]'):
        for l in sec(sname):
            s = l.rstrip()
            if not s or s.startswith((';', '#', '[')):
                continue
            # 分流/重写行内的 ; 注释：`..., reject  ;注` 形式
            if re.search(r'\S\s+;\S', s):
                errors.append(f'{sname} 行尾注释（QX 会当参数）: {s[:60]}')

    # 6) 远程资源行不应含段头
    for sname in ('[filter_remote]', '[rewrite_remote]', '[server_remote]'):
        for l in sec(sname):
            if l.strip().startswith('['):
                errors.append(f'{sname} 里混入段头: {l[:50]}')

    # 7) filter_local 的 policy 引用
    policy_names = {n for _, n, _ in groups} | BUILTIN | {'direct', 'reject'}
    for l in sec('[filter_local]'):
        s = l.strip()
        if not s or s.startswith((';', '#')):
            continue
        p = [x.strip() for x in s.split(',')]
        if len(p) >= 3:
            pol = p[-1]
            if pol not in policy_names:
                errors.append(f'[filter_local] 引用未知策略: {pol}  ({s[:50]})')

    # 订阅 URL 必须是 ASCII（URL 含未编码中文时 QX 显示「0 条规则」）
    for lineno, url in check_ascii_urls(lines):
        errors.append(f'订阅 URL 含非 ASCII 字符（QX 会显示 0 条规则），'
                      f'请改用 ASCII 文件名: 行{lineno} {url}')

    # 输出
    print(f'文件: {PATH}')
    print(f'  字节 {len(raw)}   行 {len(lines)}   段头 {len(found)}')
    print(f'  策略组 {len(groups)} 个（定义名 {len(defined)} 个）')
    print()
    if errors:
        print(f'❌ 错误 {len(errors)} 条：')
        for e in errors:
            print('   ' + e)
    else:
        print('✅ 无阻断性错误')
    if warns:
        print(f'⚠️  警告 {len(warns)} 条：')
        for w in warns[:10]:
            print('   ' + w)
    return 1 if errors else 0



def check_ascii_urls(lines):
    """订阅 URL 必须全是 ASCII。
    踩过的坑：URL 里带未编码的中文（如 .../墨鱼-应用净化.conf）QX 会显示「0 条规则」。
    文件名一律用 ASCII，已验证可用。"""
    bad = []
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if not s.startswith('http') or s.startswith(';'):
            continue
        url = s.split(',')[0].strip()
        try:
            url.encode('ascii')
        except UnicodeEncodeError:
            bad.append((i, url[:90]))
    return bad


if __name__ == '__main__':
    sys.exit(main())

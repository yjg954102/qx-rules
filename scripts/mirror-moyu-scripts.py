#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""镜像墨鱼脚本到本仓库，并把规则里的引用改写为本仓库地址。

为什么需要：
  ddgksf2013.top 曾长期 403/不可访问；实测该站点的 *.js 直接猜路径会拿到 SPA 首页。
  如果规则继续引用它，站点一变我们的规则就失效。
  镜像后规则只依赖本仓库（用户已依赖的 GitHub），可靠性大幅提升。

产出：
  output/moyu-full/scripts/<name>.js     镜像的脚本
  output/moyu-full/★VIP解锁-全部.conf     引用改写后的规则
  output/moyu-full/广告净化-全部.conf
"""
import concurrent.futures as cf
import os
import re
import sys
import urllib.request

UA = {'User-Agent': 'Quantumult X/1.5.0', 'Accept': '*/*'}
SITE = 'https://ddgksf2013.top/scripts/'
MIRROR = 'https://raw.githubusercontent.com/yjg954102/qx-rules/main/output/moyu-full/scripts/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'output', 'moyu-full')
SCRIPTS_DIR = os.path.join(OUT, 'scripts')


def main():
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    # 收集所有引用的墨鱼脚本
    refs = set()
    for f in ('★VIP解锁-全部.conf', '广告净化-全部.conf'):
        p = os.path.join(OUT, f)
        if not os.path.exists(p):
            print(f'[ERROR] 缺少 {f}，请先运行 fetch-moyu-full.py', file=sys.stderr)
            return 1
        t = open(p, encoding='utf-8').read()
        refs.update(re.findall(re.escape(SITE) + r'([A-Za-z0-9._\-]+\.js)', t))
    refs = sorted(refs)
    print(f'引用的墨鱼脚本 {len(refs)} 个')

    def download(name):
        try:
            b = urllib.request.urlopen(
                urllib.request.Request(SITE + name, headers=UA), timeout=40).read()
            t = b.decode('utf-8', 'replace')
            if '<!DOCTYPE' in t[:200] or '<html' in t[:200]:
                return name, None, 'HTML 假页面'
            return name, b, None
        except Exception as e:
            return name, None, str(e)[:50]

    ok, bad = 0, []
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for name, data, err in ex.map(download, refs):
            if data is None:
                bad.append((name, err))
                continue
            p = os.path.join(SCRIPTS_DIR, name)
            with open(p, 'wb') as f:
                f.write(data)
            os.chmod(p, 0o644)
            ok += 1
    print(f'  镜像成功 {ok}/{len(refs)}')
    for n, e in bad[:8]:
        print(f'    FAIL {n}: {e}')

    # 改写规则里的引用
    total = 0
    for f in ('★VIP解锁-全部.conf', '广告净化-全部.conf'):
        p = os.path.join(OUT, f)
        t = open(p, encoding='utf-8').read()
        n = t.count(SITE)
        t2 = t.replace(SITE, MIRROR)
        with open(p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(t2)
        print(f'  {f}: 改写 {n} 处引用 → 本仓库')
        total += n
    print(f'  合计改写 {total} 处')
    return 0 if not bad else 0


if __name__ == '__main__':
    sys.exit(main())

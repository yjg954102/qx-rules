#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并墨鱼两个来源的应用净化规则，减少 QX 订阅数量。

背景：
  两批墨鱼内容互补而非重复（实测交集仅 4 条）：
    output/moyu/        来自墨鱼 GitHub 仓库（30 个 App：微博/网易云/喜马拉雅…）
    output/moyu-full/   来自墨鱼站点（38 个：StartUpAds 507 条/知乎/小红书…）
  保留全部规则，但把「应用净化」合并成一个文件，订阅数从 30+ 降到 1，
  避免 QX 因订阅过多而加载缓慢。

产出：
  output/moyu-merged/墨鱼-应用净化.conf   两批净化合并（去重 + 分节注释）
  output/moyu-merged/_index.json          明细
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'output')
DST = os.path.join(OUT, 'moyu-merged')
RULE_RE = re.compile(r'\surl(-and-header)?\s+\S')


def rules_of(path):
    out = []
    for l in open(path, encoding='utf-8'):
        s = l.strip()
        if s and not s.startswith((';', '#')) and RULE_RE.search(s):
            out.append(s)
    return out


def main():
    os.makedirs(DST, exist_ok=True)
    groups = []   # (标签, [规则])

    # 1) 旧墨鱼：按 App 一个文件
    for p in sorted(glob.glob(os.path.join(OUT, 'moyu', '*.conf'))):
        tag = os.path.basename(p)[:-5]
        if tag.startswith(('解锁', '★')):     # 解锁类单独保留，不并入净化
            continue
        r = rules_of(p)
        if r:
            groups.append((tag, r))

    # 2) 新完整版：广告净化合集（内部已按 App 分节）
    p = os.path.join(OUT, 'moyu-full', '广告净化-全部.conf')
    if os.path.exists(p):
        cur, buf = None, []
        for l in open(p, encoding='utf-8'):
            s = l.rstrip()
            m = re.match(r'^;【(.+?)】', s.strip())
            if m:
                if cur and buf:
                    groups.append((cur, buf))
                cur, buf = m.group(1), []
                continue
            if s.strip() and not s.strip().startswith((';', '#')) and RULE_RE.search(s):
                buf.append(s.strip())
        if cur and buf:
            groups.append((cur, buf))

    # 合并去重
    seen, lines = set(), []
    lines.append('; ============================================================')
    lines.append('; 墨鱼应用净化 · 合并版')
    lines.append(';   来源1：墨鱼 GitHub 仓库（微博/网易云/喜马拉雅/高德/Keep…）')
    lines.append(';   来源2：墨鱼站点（去开屏/知乎/小红书/快看漫画…）')
    lines.append(';   已跨源去重；每个 App 一段，可整段注释掉关闭')
    lines.append('; ============================================================')
    stat = []
    for tag, rs in sorted(groups, key=lambda x: -len(x[1])):
        fresh = [r for r in rs if r not in seen]
        if not fresh:
            continue
        seen.update(fresh)
        lines.append('')
        lines.append(f';【{tag}】{len(fresh)} 条')
        lines.extend(fresh)
        stat.append({'tag': tag, 'rules': len(fresh)})

    dst = os.path.join(DST, 'moyu-app-clean.conf')  # ASCII 名：URL 含中文会让 QX 显示 0 条规则
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    os.chmod(dst, 0o644)

    with open(os.path.join(DST, '_index.json'), 'w', encoding='utf-8') as f:
        json.dump({'total': len(seen), 'groups': stat}, f, ensure_ascii=False, indent=1)

    orig = sum(len(r) for _, r in groups)
    print(f'  合并 {len(groups)} 个来源，原始 {orig} 条 → 去重后 {len(seen)} 条')
    print(f'  已写出 {dst}  ({os.path.getsize(dst)} 字节)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

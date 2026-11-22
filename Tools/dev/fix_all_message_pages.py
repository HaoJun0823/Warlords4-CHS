#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复所有事件消息：把 <Message> 里 | 分隔的每一页都拆到 <=24 字。

之前只拆了首段是错的 —— 实测每一页都有 24 字上限。
保持 <Message> 标签数不变，只用 | 增加分页（不触发节点数崩溃）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path("i:/LocalGames/Warlords IV Heroes of Etheria/English")
LIMIT = 24
STRONG = "。！？!?…"
WEAK = "；;：:，,、"


def clauses(t):
    out, buf = [], ""
    for ch in t:
        buf += ch
        if ch in STRONG or ch in WEAK:
            out.append(buf); buf = ""
    if buf: out.append(buf)
    return out


def split_page(t, lim=LIMIT):
    t = t.strip()
    if len(t) <= lim: return [t]
    parts, cur = [], ""
    for cl in clauses(t):
        if len(cl) > lim:
            if cur: parts.append(cur); cur = ""
            for i in range(0, len(cl), lim): parts.append(cl[i:i+lim])
        elif len(cur) + len(cl) <= lim:
            cur += cl
        else:
            if cur: parts.append(cur)
            cur = cl
    if cur: parts.append(cur)
    # 合并过短尾段（不超限）
    while len(parts) >= 2 and len(parts[-1]) < lim // 3:
        if len(parts[-2]) + len(parts[-1]) <= lim:
            parts[-2] += parts[-1]; parts.pop()
        else:
            break
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = files = 0
    for p in sorted(list(BASE.rglob("*.evt")) + list(BASE.rglob("*.qst"))):
        s = p.read_bytes().decode("gbk")
        msgs = list(re.finditer(r'(<Message\b[^>]*>)(.*?)(</Message>)', s, re.S))
        changes = []
        for m in msgs:
            pages = m.group(2).split("|")
            new_pages = []
            changed = False
            for pg in pages:
                parts = split_page(pg)
                new_pages.extend(parts)
                if len(parts) != 1:
                    changed = True
            if not changed:
                continue
            changes.append((m, "|".join(new_pages)))
        if not changes:
            continue
        files += 1
        total += len(changes)
        if args.apply:
            for m, new_body in reversed(changes):
                s = s[:m.start()] + m.group(1) + new_body + m.group(3) + s[m.end():]
            p.write_bytes(s.encode("gbk"))
    print(f"{'已应用' if args.apply else '预览'}: {total}处消息 / {files}文件")


if __name__ == "__main__":
    main()

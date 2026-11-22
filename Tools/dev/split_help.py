#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Help.xml：把超长 <Text> 段落按标点拆成多个 <Text>，保留原属性。

教程1的52字段刷屏，拆成2段(26字)后正常 -> 阈值约50，取45保守。
Help 每个 Entry 只有4-6段，拆后不触发"节点数上限"。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path("G:/Projects/Warlords_IV_HOE_106_CH/chinese/Help.xml")
LIMIT = 45
STRONG = "。！？!?…"
WEAK = "；;：:，,、"


def split_clauses(text):
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in STRONG or ch in WEAK:
            out.append(buf); buf = ""
    if buf: out.append(buf)
    return out


def split_by_limit(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for cl in split_clauses(text):
        if len(cl) > limit:
            if cur: parts.append(cur); cur = ""
            for i in range(0, len(cl), limit):
                parts.append(cl[i:i + limit])
        elif len(cur) + len(cl) <= limit:
            cur += cl
        else:
            if cur: parts.append(cur)
            cur = cl
    if cur: parts.append(cur)
    while len(parts) >= 2 and len(parts[-1]) < limit // 3:
        if len(parts[-2]) + len(parts[-1]) <= limit:
            parts[-2] += parts[-1]; parts.pop()
        else:
            break
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    s = P.read_bytes().decode("gbk")
    # 匹配 <Text ...>content</Text>，捕获完整开标签
    pat = re.compile(r'(<Text\b[^>]*>)(.*?)(</Text>)', re.S)
    changes = []
    for m in pat.finditer(s):
        content = m.group(2)
        if len(content.strip()) <= LIMIT:
            continue
        parts = split_by_limit(content, LIMIT)
        if len(parts) <= 1:
            continue
        indent = re.search(r'\n(\s*)', s[max(0, m.start()-30):m.start()])
        ind = indent.group(1) if indent else "      "
        open_tag = m.group(1)
        rep = ("\r\n" + ind).join(f"{open_tag}{p}{m.group(3)}" for p in parts)
        changes.append((m, rep, len(content), [len(p) for p in parts]))

    for _, _, n, sizes in changes:
        print(f"  {n}字 -> {sizes}")
    print(f"共 {len(changes)} 段")

    if args.apply:
        for m, rep, _, _ in reversed(changes):
            s = s[:m.start()] + rep + s[m.end():]
        P.write_bytes(s.encode("gbk"))
        print("已写入 Help.xml")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只对事件消息 <Message> 首段用 | 分页拆短（不动字幕、不增节点）。"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
CHS = Path("G:/Projects/Warlords_IV_HOE_106_CH/chinese")
MSG_LIMIT = 24
STRONG = "。！？!?…"
WEAK = "；;：:，,、"


def split_clauses(text):
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in STRONG or ch in WEAK:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def split_by_limit(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for cl in split_clauses(text):
        if len(cl) > limit:
            if cur:
                parts.append(cur); cur = ""
            for i in range(0, len(cl), limit):
                parts.append(cl[i:i + limit])
        elif len(cur) + len(cl) <= limit:
            cur += cl
        else:
            if cur: parts.append(cur)
            cur = cl
    if cur: parts.append(cur)
    while len(parts) >= 2 and len(parts[-1]) < limit // 2:
        if len(parts[-2]) + len(parts[-1]) <= limit:
            parts[-2] += parts[-1]; parts.pop()
        else:
            break
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = files = 0
    for p in sorted(list(CHS.rglob("*.evt")) + list(CHS.rglob("*.qst"))):
        s = p.read_bytes().decode("gbk")
        msgs = list(re.finditer(r'(<Message\b[^>]*>)(.*?)(</Message>)', s, re.S))
        changes = []
        for m in msgs:
            pages = m.group(2).split("|")
            first = pages[0].strip()
            if len(first) <= MSG_LIMIT:
                continue
            parts = split_by_limit(first, MSG_LIMIT)
            if len(parts) <= 1:
                continue
            changes.append((m, "|".join(parts + pages[1:]), len(first), len(parts)))
        if not changes:
            continue
        files += 1
        total += len(changes)
        for _, _, n, k in changes:
            print(f"  {p.relative_to(CHS)}: {n}字 -> {k}页")
        if args.apply:
            for m, new_body, _, _ in reversed(changes):
                s = s[:m.start()] + m.group(1) + new_body + m.group(3) + s[m.end():]
            p.write_bytes(s.encode("gbk"))
    print(f"{'已应用' if args.apply else '预览'}: {total}处 / {files}文件")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Help.xml 全面修复：每段<=24字防刷屏，每Entry段数受控防溢出。

分层策略：
  - Entry 原段数<=5：超长段按标点拆成多段（有 UI 空间），每段<=24字
  - Entry 原段数>=6：超长段就地精简到<=24字（不再加段，避免溢出）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P = Path("i:/LocalGames/Warlords IV Heroes of Etheria/English/Help.xml")
LIMIT = 24
CROWD = 6  # 原段数>=6 视为拥挤，不再加段
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


def split_parts(t, lim=LIMIT):
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
    return parts


def compact(t, lim=LIMIT):
    """就地精简：在<=lim的语义边界截断。"""
    t = t.strip()
    if len(t) <= lim: return t
    for puncts in (STRONG, WEAK):
        for i in range(lim, max(lim // 2, 1), -1):
            if t[i-1] in puncts: return t[:i].strip()
    return t[:lim].strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    s = P.read_bytes().decode("gbk")
    n_split = n_compact = 0

    def fix_entry(em):
        nonlocal n_split, n_compact
        body = em.group(2)
        texts = list(re.finditer(r'(<Text\b[^>]*>)(.*?)(</Text>)', body, re.S))
        if not texts: return em.group(0)

        # 统一策略：所有超长段就地精简到<=24字，绝不加段。
        # 理由：教程实测显示 4 段不溢出、8 段溢出，UI 段数容量有限；
        # 精简保段数是唯一同时满足「不刷屏」+「不溢出」的方案。
        changes = []
        for m in texts:
            t = m.group(2).strip()
            if len(t) <= LIMIT: continue
            new_part = compact(t)
            changes.append((m, new_part))
            n_compact += 1

        if not changes: return em.group(0)
        for m, new_part in reversed(changes):
            body = body[:m.start()] + m.group(1) + new_part + m.group(3) + body[m.end():]
        return em.group(1) + body + em.group(3)

    new_s = re.sub(r'(<Entry\b[^>]*>)(.*?)(</Entry>)', fix_entry, s, flags=re.S)

    print(f"拆分 {n_split} 段 / 精简 {n_compact} 段")
    # 验证
    over = [len(m.group(1).strip()) for m in re.finditer(r'<Text\b[^>]*>(.*?)</Text>', new_s, re.S)
            if len(m.group(1).strip()) > LIMIT]
    print(f"处理后超{LIMIT}字段: {len(over)}")
    entries = re.findall(r'<Entry\b[^>]*>(.*?)</Entry>', new_s, re.S)
    mx = max(len(re.findall(r'<Text\b', e)) for e in entries)
    print(f"处理后单Entry最大段数: {mx}")

    if args.apply:
        P.write_bytes(new_s.encode("gbk"))
        print("已写入 Help.xml")


if __name__ == "__main__":
    main()

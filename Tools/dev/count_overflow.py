#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精确统计 chinese/ 中复读风险文本数量（基于实测阈值）。

  过场字幕 <Text>      : >=38 字
  事件消息 <Message>首段: >24 字（| 之后分页安全，不计）
"""
from pathlib import Path
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
CHS = ROOT / "chinese"

CUTSCENE_TH = 38
MESSAGE_TH = 24


def scan():
    cut = []   # (rel, text, n)
    msg = []   # (rel, text, n, npages)
    for p in sorted(CHS.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".xml", ".evt", ".qst"):
            continue
        try:
            s = p.read_bytes().decode("gbk")
        except Exception:
            continue
        rel = p.relative_to(CHS).as_posix()

        if s.lstrip().startswith("<CutScene"):
            for m in re.finditer(r"<Text\b[^>]*>([^<]*)</Text>", s):
                t = m.group(1).strip()
                if len(t) >= CUTSCENE_TH:
                    cut.append((rel, t, len(t)))

        if p.suffix.lower() in (".evt", ".qst"):
            for m in re.finditer(r"<Message\b[^>]*>(.*?)</Message>", s, re.S):
                t = m.group(1)
                first = t.split("|")[0].strip()
                if len(first) > MESSAGE_TH:
                    msg.append((rel, first, len(first), len(t.split("|"))))

    return cut, msg


def report():
    cut, msg = scan()

    print("=" * 72)
    print("【1】过场字幕 <Text>  >= %d 字" % CUTSCENE_TH)
    print("=" * 72)
    byfile = defaultdict(list)
    for rel, t, n in cut:
        byfile[rel].append((n, t))
    for rel in sorted(byfile):
        items = byfile[rel]
        print("  %-26s %2d 处  字数: %s" % (
            rel, len(items), ", ".join(str(n) for n, _ in items)))
    print("  ---- 合计 %d 处 / %d 个文件" % (len(cut), len(byfile)))

    # 字数分布
    bins = defaultdict(int)
    for _, _, n in cut:
        if n < 45: bins["38-44"] += 1
        elif n < 55: bins["45-54"] += 1
        elif n < 65: bins["55-64"] += 1
        else: bins["65+"] += 1
    print("  字数分布:", dict(bins))
    print()

    print("=" * 72)
    print("【2】事件消息 <Message> 首段 > %d 字" % MESSAGE_TH)
    print("=" * 72)
    byfile2 = defaultdict(list)
    for rel, t, n, np in msg:
        byfile2[rel].append((n, np, t))
    for rel in sorted(byfile2):
        items = byfile2[rel]
        print("  %-26s %2d 处  字数: %s" % (
            rel, len(items), ", ".join(str(n) for n, _, _ in items)))
    print("  ---- 合计 %d 处 / %d 个文件" % (len(msg), len(byfile2)))

    bins2 = defaultdict(int)
    for _, _, n, _ in msg:
        if n <= 30: bins2["25-30"] += 1
        elif n <= 45: bins2["31-45"] += 1
        elif n <= 65: bins2["46-65"] += 1
        else: bins2["65+"] += 1
    print("  字数分布:", dict(bins2))
    print()

    print("=" * 72)
    print("总计: 过场 %d + 消息 %d = %d 处风险文本" % (len(cut), len(msg), len(cut) + len(msg)))
    print("=" * 72)


if __name__ == "__main__":
    report()

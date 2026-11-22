#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：定位汉化后文本重复渲染的根因。"""
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path("i:/LocalGames/Warlords IV Heroes of Etheria/English")


def show_special_chars(rel):
    s = (BASE / rel).read_bytes().decode("gbk")
    print("=" * 60)
    print(rel)
    for ch in ["<", ">", "&", '"', "|", "\\"]:
        print("  %-6s count=%d" % (repr(ch), s.count(ch)))
    bad = list(re.finditer(r"&(?!amp;|lt;|gt;|quot;|apos;)[^;]{0,12}", s))
    for m in bad[:20]:
        print("  BAD & at", m.start(), repr(m.group()))


def main():
    for rel in ["Campaign/Campaign_0.xml", "The Storm Hills.evt"]:
        show_special_chars(rel)

    # 精确看问题文本2 中每个字符的字节，找 0x7C / 0x0A / 0x0D / 0x00
    s = (BASE / "The Storm Hills.evt").read_bytes().decode("gbk")
    m = re.search(r"<Message>(.*?)</Message>", s, re.S)
    while m and "利瓦里亚" not in m.group(1):
        m = re.search(r"<Message>(.*?)</Message>", s[m.end():], re.S)
    if m:
        t = m.group(1)
        b = t.encode("gbk")
        print("\n问题文本2 长度", len(b), "字节")
        for i, x in enumerate(b):
            if x in (0x7C, 0x00, 0x0A, 0x0D, 0x1A):
                print("  特殊字节 0x%02X at %d" % (x, i))


if __name__ == "__main__":
    main()

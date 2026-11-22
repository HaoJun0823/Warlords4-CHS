#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描汉化文本中可能触发引擎渲染溢出的超长段落。

实测阈值（GOG 1.06 + GBK）：
  - CutScene <Text>       : <=37 汉字(74字节) 安全；>=38 汉字(76字节) 复读
  - <Message> 单个 | 分页 : <=32 汉字(64字节) 安全；>=34 汉字(68字节) 复读
    （| 之后的分页走独立缓冲，实测 37字/74字节 安全）
"""
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path("i:/LocalGames/Warlords IV Heroes of Etheria/English")

CUTSCENE_LIMIT = 37   # 汉字
MESSAGE_LIMIT = 32    # 汉字（第一段）


def cjk_len(s: str) -> int:
    return len(s)


def scan_cutscenes():
    print("=" * 78)
    print("【过场字幕 <Text>】超过 %d 字的段落（实测 >=38 字复读）" % CUTSCENE_LIMIT)
    print("=" * 78)
    hits = []
    for p in sorted(BASE.rglob("*.xml")):
        try:
            s = p.read_bytes().decode("gbk")
        except Exception:
            continue
        for m in re.finditer(r"<Text\b[^>]*>(.*?)</Text>", s, re.S):
            t = m.group(1)
            n = cjk_len(t)
            if n > CUTSCENE_LIMIT:
                hits.append((p.relative_to(BASE), n, t))
    for rel, n, t in hits:
        print("  %-24s %2d字 | %s" % (str(rel), n, t[:34]))
    print("  合计 %d 处\n" % len(hits))
    return hits


def scan_messages():
    print("=" * 78)
    print("【事件消息 <Message>】第一段超过 %d 字的段落" % MESSAGE_LIMIT)
    print("=" * 78)
    hits = []
    for p in sorted(list(BASE.rglob("*.evt")) + list(BASE.rglob("*.qst"))):
        try:
            s = p.read_bytes().decode("gbk")
        except Exception:
            continue
        for m in re.finditer(r"<Message\b[^>]*>(.*?)</Message>", s, re.S):
            t = m.group(1)
            pages = t.split("|")
            first = pages[0]
            n = cjk_len(first)
            if n > MESSAGE_LIMIT:
                hits.append((p.relative_to(BASE), n, len(pages), first))
    for rel, n, np, t in hits:
        print("  %-24s 首段%2d字/%d页 | %s" % (str(rel), n, np, t[:34]))
    print("  合计 %d 处\n" % len(hits))
    return hits


def main():
    scan_cutscenes()
    scan_messages()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不拆节点、保持 time 不变，把超长字幕/消息就地压缩到阈值内。

用于规避「拆节点过多导致引擎数组越界崩溃」。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
CHS = ROOT / "chinese"
BACKUP = Path("i:/LocalGames/Warlords IV Heroes of Etheria/English.before_split")

CUT_LIMIT = 37
MSG_LIMIT = 24
STRONG = "。！？!?…"
WEAK = "；;：:，,、"


def compact(text: str, limit: int) -> str:
    """在接近 limit 的语义边界截断，尽量多保留内容。"""
    text = text.strip()
    if len(text) <= limit:
        return text
    # 从 limit 往回找最近的标点（先强后弱），尽量贴近上限
    for puncts in (STRONG, WEAK):
        for i in range(limit, max(limit // 2, 1), -1):
            if text[i - 1] in puncts:
                return text[:i].strip()
    # 没合适标点，硬截
    return text[:limit].strip()


def compact_cutscene(path: Path, apply: bool, report: list[str]) -> bool:
    s = path.read_bytes().decode("gbk")
    if not s.lstrip().startswith("<CutScene"):
        return False
    changed = False
    out = []
    pos = 0
    for m in re.finditer(r'(<Text time="(\d+)">)([^<]*)(</Text>)', s):
        content = m.group(3)
        if len(content) <= CUT_LIMIT:
            continue
        new = compact(content, CUT_LIMIT)
        if new == content:
            continue
        report.append(f"  time={m.group(2)} {len(content)}字 -> {len(new)}字: {content[:20]}...")
        out.append((m.start(), m.end(), m.group(1) + new + m.group(4)))
        changed = True
    if apply and changed:
        for a, b, rep in reversed(out):
            s = s[:a] + rep + s[b:]
        path.write_bytes(s.encode("gbk"))
    return changed


def compact_messages(path: Path, apply: bool, report: list[str]) -> bool:
    if path.suffix.lower() not in (".evt", ".qst"):
        return False
    s = path.read_bytes().decode("gbk")
    out = []
    for m in re.finditer(r'(<Message\b[^>]*>)(.*?)(</Message>)', s, re.S):
        body = m.group(2)
        pages = body.split("|")
        first = pages[0].strip()
        if len(first) <= MSG_LIMIT:
            continue
        new_first = compact(first, MSG_LIMIT)
        if new_first == first:
            continue
        new_body = "|".join([new_first] + pages[1:])
        report.append(f"  消息首段 {len(first)}字 -> {len(new_first)}字")
        out.append((m.start(), m.end(), m.group(1) + new_body + m.group(3)))
    if apply and out:
        for a, b, rep in reversed(out):
            s = s[:a] + rep + s[b:]
        path.write_bytes(s.encode("gbk"))
    return bool(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--from-backup", action="store_true", help="从未切分的RC2备份读取字幕")
    args = ap.parse_args()

    # 实验模式：只处理 Campaign_0.xml（游戏目录）
    if args.from_backup:
        src = BACKUP / "Campaign" / "Campaign_0.xml"
        dst = Path("i:/LocalGames/Warlords IV Heroes of Etheria/English/Campaign/Campaign_0.xml")
        report: list[str] = []
        compact_cutscene(src, False, report)
        print(f"模式: 从RC2备份生成 Campaign_0 精简预览（{len(report)}处）")
        for r in report:
            print(r)
        if args.apply:
            # 复制备份到目标再精简
            import shutil
            shutil.copy2(src, dst)
            compact_cutscene(dst, True, [])
            print(f"\n已写入 {dst}")
        return

    # 全量模式
    report = []
    nf = nc = 0
    for p in sorted(CHS.rglob("*")):
        if not p.is_file():
            continue
        local: list[str] = []
        rel = p.relative_to(CHS)
        if p.suffix == ".xml" and "Campaign" in rel.parts:
            if compact_cutscene(p, args.apply, local):
                nf += 1
        if compact_messages(p, args.apply, local):
            nc += 1
        if local:
            report.append(f"=== {rel}")
            report.extend(local)
    print(f"模式: {'写入' if args.apply else '预览'}  字幕文件{nf} 消息文件{nc}")
    for r in report:
        print(r)


if __name__ == "__main__":
    main()

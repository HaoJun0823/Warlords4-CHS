#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复复读机 BUG：把超长文本按标点断句切分。

  过场字幕 <Text>       : 拆成多个 <Text time=...>，每个 <= CUT_LIMIT 字
                           时间点在原 time 到下一 time 的区间内均分
  事件消息 <Message>首段: 用 '|' 分页拆短，每页 <= MSG_LIMIT 字

用法：
  python Tools/dev/split_overflow.py            # dry-run，只预览不写入
  python Tools/dev/split_overflow.py --apply    # 实际应用改动
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
CHS = ROOT / "chinese"

CUT_LIMIT = 37   # 过场字幕单节点字数上限（实测 >=38 复读）
MSG_LIMIT = 24   # 事件消息首段每页字数上限（实测 >24 复读）

# 断句标点：强(句末) -> 弱(句中)
STRONG = "。！？!?…"
WEAK = "；;：:，,、"


def split_clauses(text: str) -> list[str]:
    """把文本按标点切成语义块，标点保留在块尾。"""
    clauses: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in STRONG or ch in WEAK:
            clauses.append(buf)
            buf = ""
    if buf:
        clauses.append(buf)
    return clauses


def split_by_limit(text: str, limit: int) -> list[str]:
    """在语义完整处断句，每段 <= limit 字。优先强标点，必要时弱标点，最后硬切。"""
    text = text.strip()
    if len(text) <= limit:
        return [text]

    clauses = split_clauses(text)
    parts: list[str] = []
    cur = ""

    for cl in clauses:
        # 单个语义块就超长 → 硬切
        if len(cl) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            for i in range(0, len(cl), limit):
                chunk = cl[i:i + limit]
                if chunk:
                    parts.append(chunk)
            continue
        if len(cur) + len(cl) <= limit:
            cur += cl
        else:
            if cur:
                parts.append(cur)
            cur = cl
    if cur:
        parts.append(cur)

    # 合并过短的尾段（< limit 的一半）到前一段，避免零碎；但绝不能超限
    while len(parts) >= 2 and len(parts[-1]) < limit // 2:
        if len(parts[-2]) + len(parts[-1]) <= limit:
            parts[-2] += parts[-1]
            parts.pop()
        else:
            break
    return parts


def split_cutscene(path: Path, apply: bool, report: list[str]) -> bool:
    s = path.read_bytes().decode("gbk")
    if not s.lstrip().startswith("<CutScene"):
        return False

    # 解析所有 <Text time="X">...</Text>
    text_re = re.compile(r'<Text time="(\d+)">([^<]*)</Text>')
    nodes = list(text_re.finditer(s))
    dur_m = re.search(r'duration="(\d+)"', s)
    duration = int(dur_m.group(1)) if dur_m else None

    # 原始时间点序列（用于计算每段的显示区间）
    times = [int(m.group(1)) for m in nodes]

    changes = []
    for i, m in enumerate(nodes):
        t = int(m.group(1))
        content = m.group(2)
        if len(content) < CUT_LIMIT:
            continue
        parts = split_by_limit(content, CUT_LIMIT)
        if len(parts) <= 1:
            continue

        # 显示区间：[t, next_t)，最后一段到 duration
        if i + 1 < len(times):
            end = times[i + 1]
        else:
            end = duration if duration and duration > t else t + 6000
        span = end - t
        step = max(1000, span // len(parts))
        new_times = [t + step * k for k in range(len(parts))]
        changes.append((m, content, parts, new_times))

    if not changes:
        return False

    for m, content, parts, new_times in changes:
        report.append(f"  [{path.name}] time={m.group(1)} {len(content)}字 -> {len(parts)}段 {[len(p) for p in parts]}")
        for p, nt in zip(parts, new_times):
            report.append(f"      time={nt}: {p}")

    if apply:
        # 从后往前替换，避免前面的替换改变后面 match 的偏移
        for m, content, parts, new_times in reversed(changes):
            replacement = "".join(f'<Text time="{nt}">{p}</Text>' for p, nt in zip(parts, new_times))
            s = s[:m.start()] + replacement + s[m.end():]
        path.write_bytes(s.encode("gbk"))
    return True


def split_messages(path: Path, apply: bool, report: list[str]) -> bool:
    if path.suffix.lower() not in (".evt", ".qst"):
        return False
    s = path.read_bytes().decode("gbk")
    msg_re = re.compile(r'(<Message\b[^>]*>)(.*?)(</Message>)', re.S)
    msgs = list(msg_re.finditer(s))

    changes = []
    for m in msgs:
        body = m.group(2)
        pages = body.split("|")
        first = pages[0].strip()
        if len(first) <= MSG_LIMIT:
            continue
        parts = split_by_limit(first, MSG_LIMIT)
        if len(parts) <= 1:
            continue
        new_body = "|".join(parts + pages[1:])
        changes.append((m, first, parts, new_body))

    if not changes:
        return False

    for m, first, parts, new_body in changes:
        report.append(f"  [{path.name}] 首段 {len(first)}字 -> {len(parts)}页 {[len(p) for p in parts]}")

    if apply:
        # 从后往前替换，避免前面的替换改变后面 match 的偏移
        for m, first, parts, new_body in reversed(changes):
            s = s[:m.start()] + m.group(1) + new_body + m.group(3) + s[m.end():]
        path.write_bytes(s.encode("gbk"))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="实际应用改动（默认仅预览）")
    ap.add_argument("--detail", action="store_true", help="输出切分后的详细文本")
    args = ap.parse_args()

    report: list[str] = []
    file_count = 0
    cut_count = 0
    msg_count = 0

    for p in sorted(CHS.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(CHS)
        local: list[str] = []
        if p.suffix.lower() == ".xml" and "Campaign" in rel.parts:
            if split_cutscene(p, args.apply, local):
                cut_count += sum(1 for l in local if "字 ->" in l)
                file_count += 1
        if split_messages(p, args.apply, local):
            msg_count += sum(1 for l in local if "首段" in l)
            file_count += 1
        if local:
            report.append("=" * 72)
            report.append(str(rel))
            report.extend(local if args.detail else [l for l in local if "字 ->" in l])

    mode = "实际写入" if args.apply else "DRY-RUN 预览"
    print(f"模式: {mode}")
    print(f"字幕改动 {cut_count} 处 / 消息改动 {msg_count} 处 / 涉及 {file_count} 文件\n")
    for line in report:
        print(line)
    if not args.apply:
        print("\n（加 --apply 实际应用）")


if __name__ == "__main__":
    main()

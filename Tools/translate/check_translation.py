#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_translation.py — 校验 chinese/ 下的汉化文本

违反任意一条铁律都会让游戏卡死或显示异常，故全部作为硬错误：

  1. 文本文件必须是合法 GBK 编码，且无 BOM
  2. 禁止数值实体 &#...; —— 引擎解析器遇到会死循环卡死（2026-11-22 实测）
     命名实体（&apos; &quot; &amp; &lt; &gt;）安全，原文本身就在用
  3. XML 标签结构必须与 english/ 原文一致（标签名序列，不得增删标签）
  4. 格式化占位符（%s %d 等）数量必须与原文一致
  5. .nam 文件行数必须与原文一致（按行索引）

用法：
  python Tools/translate/check_translation.py
  python Tools/ci/build_release.py          # 构建时自动调用本校验
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
ENG = ROOT / "english"
CHS = ROOT / "chinese"

TEXT_EXTS = {".xml", ".nam", ".evt", ".qst", ".txt", ".ini"}
XML_EXTS = {".xml", ".evt", ".qst"}

RE_BOM = re.compile(rb"^\xef\xbb\xbf|^\xff\xfe|^\xfe\xff")
RE_NUMERIC_ENTITY = re.compile(rb"&#")
RE_PLACEHOLDER = re.compile(rb"%[a-zA-Z]")
RE_COMMENT = re.compile(rb"<!--.*?-->", re.S)
RE_TAG = re.compile(rb"<(/?)([A-Za-z_][\w:.-]*)")


def text_files(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix.lower() in TEXT_EXTS
    }


def tag_sequence(data: bytes) -> list[bytes]:
    """标签名序列（忽略注释、文本、属性）。"""
    return [m.group(2) for m in RE_TAG.finditer(RE_COMMENT.sub(b"", data))]


def check_one(rel: str, chs_path: Path, eng_path: Path,
              errors: list[str], warns: list[str]) -> dict:
    raw = chs_path.read_bytes()
    eng_raw = eng_path.read_bytes() if eng_path.is_file() else None
    st = {
        "file": rel,
        "bytes": len(raw),
        "unchanged": bool(eng_raw is not None and raw == eng_raw),
    }

    # 未翻译的文件直接沿用原文字节，放行。
    # 注意：部分原文含 cp1252 标点（… “ ” –），既非 GBK 也非 UTF-8，
    # 但原版游戏本就能处理；强制 GBK 会让初始仓库无法过校验。
    # 一旦翻译（字节改变），下面的铁律就会生效。
    if st["unchanged"]:
        return st

    if eng_raw is None:
        warns.append(f"{rel}: english/ 中无对应原文文件")

    if RE_BOM.match(raw):
        errors.append(f"{rel}: 含 BOM 头，引擎可能无法解析")

    try:
        raw.decode("gbk", errors="strict")
    except UnicodeDecodeError as e:
        errors.append(
            f"{rel}: 非合法 GBK（偏移 {e.start}）。原文可能含 cp1252 标点"
            "（… “ ” –），翻译时请一并换成中文标点或 GBK 可表示的字符"
        )
        return st

    n_entity = len(RE_NUMERIC_ENTITY.findall(raw))
    if n_entity:
        errors.append(
            f"{rel}: 含 {n_entity} 处数值实体 '&#...;' —— 会导致游戏死循环卡死；"
            "请直接写中文，或改用命名实体（&apos; &quot; &amp; &lt; &gt;）"
        )

    if eng_raw is None:
        return st

    n_ph = len(RE_PLACEHOLDER.findall(raw))
    n_ph_eng = len(RE_PLACEHOLDER.findall(eng_raw))
    if n_ph != n_ph_eng:
        errors.append(
            f"{rel}: 格式化占位符数量 {n_ph} != 原文 {n_ph_eng}（%s/%d 等必须原样保留）"
        )

    if chs_path.suffix.lower() in XML_EXTS:
        tags = tag_sequence(raw)
        tags_eng = tag_sequence(eng_raw)
        # CutScene 的 <Text> 允许拆分（修复长文本复读的既定手段）：
        # 对比时把连续的 <Text> 折叠归一化，只要求总体标签集合一致。
        is_cutscene = raw.lstrip().startswith(b"<CutScene")
        is_help = rel.endswith("Help.xml")
        # 过场字幕与帮助文档都允许 <Text> 节点增加（拆段修复复读的既定手段）：
        # 其它标签须完全一致，Text 数不得少于原文。
        if is_cutscene or is_help:
            others = lambda seq: [t for t in seq if t != b"Text"]
            if others(tags) != others(tags_eng) or tags.count(b"Text") < tags_eng.count(b"Text"):
                errors.append(
                    f"{rel}: 结构异常——除 <Text> 外的标签须与原文一致，"
                    "且 <Text> 节点数不得少于原文（拆段用于修复复读）"
                )
        elif tags != tags_eng:
            errors.append(
                f"{rel}: XML 标签结构不一致（译文 {len(tags)} 个 / 原文 {len(tags_eng)} 个），"
                "不得增删或重排标签"
            )

        # 长文本复读风险（实测阈值，仅警告不阻断）：
        #   - 过场字幕 <Text>  >=38 汉字会复读
        #   - 事件消息 <Message> 首段 >=26 汉字会复读（| 之后的分页用独立缓冲，安全）
        text = raw.decode("gbk", errors="ignore")
        if is_cutscene:
            for m in re.finditer(r"<Text\b[^>]*>([^<]*)</Text>", text):
                n = len(m.group(1))
                if n >= 38:
                    warns.append(
                        f"{rel}: 过场字幕 {n} 字（>=38），可能复读；"
                        "请拆成多个 <Text time=...> 节点（每节点<=37字）"
                    )
        if rel.endswith(".evt") or rel.endswith(".qst"):
            for m in re.finditer(r"<Message\b[^>]*>(.*?)</Message>", text, re.S):
                first = m.group(1).split("|")[0]
                n = len(first)
                if n > 24:
                    warns.append(
                        f"{rel}: 事件消息首段 {n} 字（>24），可能复读；"
                        "请用 '|' 把首段拆短（每页<=24字）"
                    )

    if chs_path.suffix.lower() == ".nam":
        n = len(raw.splitlines())
        n_eng = len(eng_raw.splitlines())
        if n != n_eng:
            errors.append(f"{rel}: 行数 {n} != 原文 {n_eng}（.nam 按行索引，不得增删行）")

    return st


def run_check(strict: bool = False):
    errors: list[str] = []
    warns: list[str] = []
    stats: list[dict] = []

    if not ENG.is_dir() or not CHS.is_dir():
        errors.append(f"缺少目录：{ENG} 或 {CHS}")
        return errors, warns, stats

    eng_files = text_files(ENG)
    chs_files = text_files(CHS)

    for rel, p in sorted(chs_files.items()):
        stats.append(check_one(rel, p, ENG / rel, errors, warns))

    missing = sorted(set(eng_files) - set(chs_files))
    if missing:
        msg = (f"chinese/ 缺少 {len(missing)} 个原文文本文件：" + ", ".join(missing[:8]))
        (errors if strict else warns).append(msg + (" ..." if len(missing) > 8 else ""))

    for rel in sorted(set(chs_files) - set(eng_files)):
        errors.append(f"{rel}: english/ 中不存在此文件，疑似误建")

    return errors, warns, stats


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 chinese/ 汉化文本（GBK / 数值实体 / XML 结构 / 占位符 / 行数）")
    ap.add_argument("--strict", action="store_true", help="chinese/ 缺少原文文件时也报错")
    args = ap.parse_args()

    errors, warns, stats = run_check(args.strict)
    translated = sum(1 for s in stats if not s["unchanged"])
    total = sum(s["bytes"] for s in stats)
    print(f"校验 {len(stats)} 个文件（已改 {translated} / 未改 {len(stats) - translated}），共 {total} 字节")
    for w in warns:
        print(f"[WARN]  {w}")
    for e in errors:
        print(f"[ERROR] {e}")
    if errors:
        print(f"\n失败：{len(errors)} 错误，{len(warns)} 警告")
        return 1
    print(f"\n通过：0 错误，{len(warns)} 警告")
    return 0


if __name__ == "__main__":
    sys.exit(main())

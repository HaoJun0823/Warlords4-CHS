#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_release.py — 校验汉化发布包 zip 的结构与编码门禁

检查：
  - zip 内含 English/ 文本文件与 必读说明.txt
  - 所有 English/ 下文本文件为合法 GBK 且不含数值实体 '&#'
  - XML 标签结构与仓库 english/ 原文一致

用法：
  python Tools/ci/verify_release.py build_out/Warlords4-CHS-v*.zip
  python Tools/ci/verify_release.py build_out       # 校验目录内全部 zip
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
ENG = ROOT / "english"
sys.path.insert(0, str(ROOT / "Tools" / "translate"))
from check_translation import tag_sequence  # noqa: E402


def verify_one(zip_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            entries = [n for n in names if n.startswith("English/") and not n.endswith("/")]
            if not entries:
                errors.append("zip 内无 English/ 文本文件")
            if "必读说明.txt" not in names:
                errors.append("缺少 必读说明.txt")
            if "文件清单.txt" not in names:
                errors.append("缺少 文件清单.txt")
            if not any(n.startswith("附赠文档/") for n in names):
                errors.append("缺少 附赠文档/（完整教程 PDF/Markdown）")
            if "许可/LICENSE" not in names:
                errors.append("缺少 许可/LICENSE")
            if "许可/Apache-2.0.txt" not in names:
                errors.append("缺少 许可/Apache-2.0.txt")

            for n in entries:
                data = z.read(n)
                rel = n[len("English/"):]
                orig = ENG / rel
                orig_raw = orig.read_bytes() if orig.is_file() else None
                # 未翻译文件沿用原文字节（部分原文含 cp1252 标点，原版本身可运行），放行
                if orig_raw is not None and data == orig_raw:
                    continue
                try:
                    data.decode("gbk", errors="strict")
                except UnicodeDecodeError as e:
                    errors.append(f"{n}: 非合法 GBK（偏移 {e.start}）")
                if b"&#" in data:
                    errors.append(f"{n}: 含数值实体 '&#...;'，会导致游戏卡死")
                if orig_raw is not None and Path(rel).suffix.lower() in {".xml", ".evt", ".qst"}:
                    tags = tag_sequence(data)
                    tags_eng = tag_sequence(orig_raw)
                    if data.lstrip().startswith(b"<CutScene") or rel.endswith("Help.xml"):
                        # 过场字幕/帮助文档允许 <Text> 节点增加（拆段修复复读的既定手段）
                        others = lambda seq: [t for t in seq if t != b"Text"]
                        if others(tags) != others(tags_eng) or tags.count(b"Text") < tags_eng.count(b"Text"):
                            errors.append(f"{n}: 结构异常（除 Text 外标签须一致，Text 不得少于原文）")
                    elif tags != tags_eng:
                        errors.append(f"{n}: XML 标签结构与 english/ 原文不一致")
    except zipfile.BadZipFile:
        errors.append("不是合法 zip 文件")
    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    target = Path(sys.argv[1])
    if target.is_dir():
        zips = sorted(target.glob("*.zip"))
        if not zips:
            print(f"{target} 内没有 zip")
            return 2
    else:
        zips = [target]

    failed = 0
    for z in zips:
        errs = verify_one(z)
        if errs:
            failed += 1
            print(f"[FAIL] {z.name}")
            for e in errs:
                print(f"   - {e}")
        else:
            print(f"[OK]   {z.name}（{z.stat().st_size} 字节）")
    if failed:
        print(f"\n{failed} 个包未通过校验")
        return 1
    print(f"\n全部 {len(zips)} 个包通过校验")
    return 0


if __name__ == "__main__":
    sys.exit(main())

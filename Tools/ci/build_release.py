#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_release.py — 装配《战神IV：艾瑟里亚英雄》(Warlords IV: Heroes of Etheria)
简体中文汉化发布包

把 chinese/ 下的 GBK 文本文件按游戏 English/ 目录布局打进 zip。
玩家把压缩包内的 English 文件夹解压到游戏根目录覆盖即可，
Language.ini 保持 Name = english（已实测：GBK 中文在 English 槽位正常显示）。

构建前自动运行 check_translation 全部铁律校验，有硬错误则拒绝出包。

用法：
  python Tools/ci/build_release.py
  python Tools/ci/build_release.py --out-root D:/rel
  python Tools/ci/build_release.py --date 20261122 --time 0815   # 固定时间戳，便于复现
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
CHS = ROOT / "chinese"
BUILD_OUT = ROOT / "build_out"
CST = timezone(timedelta(hours=8))

sys.path.insert(0, str(ROOT / "Tools" / "translate"))
from check_translation import run_check, text_files  # noqa: E402


README_TEXT = """《战神IV：艾瑟里亚英雄》(Warlords IV: Heroes of Etheria)
简体中文汉化补丁
============================================================

适用版本：GOG 1.06（Warlords IV: Heroes of Etheria）

【安装】
  1. 解压本压缩包到游戏根目录（Warlords4.exe 所在目录）。
  2. 包内 English 文件夹会覆盖游戏原有的 English 文件夹。
  3. 不要修改 Language.ini（保持 Name = english）。
  4. 直接启动游戏即可看到中文。

【卸载 / 还原】
  用 GOG 安装器修复游戏，或把你事先备份的原始 English 文件夹还原。

【重要提示】
  - 本补丁为非官方个人作品，未获游戏官方授权。安装前请备份存档与原始文件。
  - 禁止商业使用；二次分发请保留来源与改动记录。
  - 文本为 GBK 编码。请勿用记事本另存为 UTF-8，否则游戏内会乱码或卡死。
  - 请勿在文本中写数值实体（形如 &#x4E2D;），引擎不支持，会导致游戏死循环卡死。
    需要引号时请用命名实体 &quot; 和 &apos;（原文本身就在用）。

【工程与源码】
  本补丁由 Git 管理、CI 自动构建。汉化工程见：
  G:\\Projects\\Warlords_IV_HOE_106_CH
"""


def build(out_root: Path, date: str | None, tm: str | None) -> Path:
    errors, warns, stats = run_check(strict=False)
    if errors:
        print("校验未通过，拒绝出包：")
        for e in errors:
            print(f"  [ERROR] {e}")
        sys.exit(1)

    chs_files = text_files(CHS)
    changed = sum(1 for s in stats if not s["unchanged"])
    print(f"校验通过：{len(stats)} 个文件，其中已汉化 {changed} 个")

    stamp = (date or datetime.now(CST).strftime("%Y%m%d")) + "-" + \
            (tm or datetime.now(CST).strftime("%H%M"))
    out_root.mkdir(parents=True, exist_ok=True)
    zip_path = out_root / f"Warlords4-CHS-v{stamp}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, p in sorted(chs_files.items()):
            z.write(p, f"English/{rel}")
        z.writestr("必读说明.txt", README_TEXT.encode("utf-8-sig"))
        z.writestr(
            "文件清单.txt",
            ("汉化文本文件清单（GBK 编码）\n" + "=" * 60 + "\n"
             + "\n".join(f"  English/{r}" for r in sorted(chs_files))
             + f"\n\n共 {len(chs_files)} 个文件\n").encode("utf-8-sig"),
        )

    print(f"已生成：{zip_path}（{zip_path.stat().st_size} 字节）")
    print(f"警告 {len(warns)} 条（不影响出包）")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-root", default=str(BUILD_OUT), help="输出目录（默认 build_out/）")
    ap.add_argument("--date", default=None, help="固定日期 YYYYMMDD")
    ap.add_argument("--time", dest="tm", default=None, help="固定时间 HHMM")
    args = ap.parse_args()
    build(Path(args.out_root), args.date, args.tm)
    return 0


if __name__ == "__main__":
    sys.exit(main())

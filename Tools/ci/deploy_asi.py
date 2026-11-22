#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把编译好的 W4CHS_DLL.dll 部署为游戏根目录的 W4CHS_DLL.asi + winmm.dll。

用法：
  python Tools/ci/deploy_asi.py                    # 部署到默认游戏目录
  python Tools/ci/deploy_asi.py --game D:/path     # 指定游戏目录
  python Tools/ci/deploy_asi.py --uninstall        # 卸载（删除 asi 和 winmm.dll）
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
DLL = ROOT / "W4CHS_DLL" / "build" / "W4CHS_DLL.dll"
ASI_LOADER = ROOT / "dist" / "common" / "winmm.dll"
DEFAULT_GAME = Path("i:/LocalGames/Warlords IV Heroes of Etheria")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", default=str(DEFAULT_GAME))
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()
    game = Path(args.game)

    if args.uninstall:
        for name in ["W4CHS_DLL.asi", "winmm.dll", "W4CHS.log", "W4CHS.ini"]:
            p = game / name
            if p.exists():
                p.unlink()
                print(f"已删除 {p}")
        return

    if not DLL.is_file():
        print(f"!! 找不到 {DLL}，先运行 build_dll_local.py")
        sys.exit(1)
    shutil.copy2(DLL, game / "W4CHS_DLL.asi")
    print(f"已部署 {game / 'W4CHS_DLL.asi'}")
    if ASI_LOADER.is_file() and not (game / "winmm.dll").exists():
        shutil.copy2(ASI_LOADER, game / "winmm.dll")
        print(f"已部署 ASI Loader {game / 'winmm.dll'}")
    elif (game / "winmm.dll").exists():
        print("winmm.dll 已存在，跳过")
    # 默认配置：开日志
    ini = game / "W4CHS.ini"
    if not ini.exists():
        ini.write_text("[W4CHS]\nDebug=1\nFullWidth=0\n", encoding="ascii")
        print(f"已生成 {ini}")


if __name__ == "__main__":
    main()

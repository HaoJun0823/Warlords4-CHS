#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dll_local.py — 本地编译 W4CHS_DLL（MSVC 2017 v141, Win32/x86）

目标：产出 W4CHS_DLL.dll（后由 build_release.py 改名 W4CHS_DLL.asi 收进发布包）。
配方与参考项目（MajestyIIExtend/build_deploy.sh、ArmyMenCHS）一致：
  v141 (MSVC 14.16) + Windows SDK 10.0.26100.0 + cl /LD /Y- /utf-8。

环境适配：
  - CI（ubuntu-latest + msvc-wine）：`cl` 已在 PATH（bin/x86 包装脚本），
    INCLUDE/LIB 由包装脚本设置，本脚本不覆盖。传给 cl 的路径一律「相对仓库根 +
    POSIX 分隔符」，由包装脚本负责转换成 wine 内路径。
  - 本地 Windows（VS2017 Professional）：自动定位 cl.exe，并补上 INCLUDE/LIB。

用法：
  python Tools/ci/build_dll_local.py                 # 编译 -> W4CHS_DLL/build/W4CHS_DLL.dll
  python Tools/ci/build_dll_local.py --clean        # 先清再编
  python Tools/ci/build_dll_local.py --out X:/o.dll # 自定义输出路径
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
PROJ = ROOT / "W4CHS_DLL"
SRC = PROJ  # dllmain.cpp / pch.cpp / pch.h / framework.h 都在 W4CHS_DLL/


def find_cl():
    """返回 cl 可执行路径；CI 上优先用 PATH 中的 msvc-wine 包装。"""
    on_path = shutil.which("cl") or shutil.which("cl.exe")
    if on_path:
        return Path(on_path), None   # 无需补 INCLUDE/LIB（CI 已设）
    # 本地：扫描 VS2017 Professional 的 v141 cl.exe
    base = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2017\Professional"
                r"\VC\Tools\MSVC")
    if base.is_dir():
        # 取最新的 14.x 版本目录
        vers = sorted([d for d in base.iterdir() if d.name.startswith("14.")],
                     reverse=True)
        for v in vers:
            cand = v / "bin" / "Hostx86" / "x86" / "cl.exe"
            if cand.is_file():
                return cand, v
    # 兜底：VS2022 也可能装了 v141 工具集
    base22 = Path(r"C:\Program Files\Microsoft Visual Studio\2022")
    if base22.is_dir():
        for ed in sorted(base22.iterdir(), reverse=True):
            cand = ed / "VC" / "Tools" / "MSVC"
            if cand.is_dir():
                vers = sorted([d for d in cand.iterdir() if d.name.startswith("14.")],
                             reverse=True)
                for v in vers:
                    c = v / "bin" / "Hostx86" / "x86" / "cl.exe"
                    if c.is_file():
                        return c, v
    return None, None


def msvc_include_lib(v: Path):
    """根据 v141 目录推导出 INCLUDE/LIB（本地 Windows 用）。"""
    sdk = Path(r"C:\Program Files (x86)\Windows Kits\10")
    sdk_ver = "10.0.26100.0"
    inc = ";".join([
        str(v / "include"),
        str(sdk / "Include" / sdk_ver / "ucrt"),
        str(sdk / "Include" / sdk_ver / "um"),
        str(sdk / "Include" / sdk_ver / "shared"),
    ])
    lib = ";".join([
        str(v / "lib" / "x86"),
        str(sdk / "Lib" / sdk_ver / "ucrt" / "x86"),
        str(sdk / "Lib" / sdk_ver / "um" / "x86"),
    ])
    return inc, lib


def build(clean: bool, out: Path | None):
    cl, v = find_cl()
    if cl is None:
        print("!! 未找到 cl.exe（CI 上需 msvc-wine 的 PATH；本地需安装 VS2017 v141）")
        sys.exit(1)
    print(f"[cl] 使用：{cl}")

    out_dll = out or (PROJ / "build" / "W4CHS_DLL.dll")
    out_dll.parent.mkdir(parents=True, exist_ok=True)
    if clean and out_dll.exists():
        out_dll.unlink()

    # 把 .obj 也重定向到 build/，避免污染仓库根目录（cl 默认把 obj 写到 cwd）。
    # ★ 传给 cl 的路径一律「相对仓库根 + POSIX 分隔符 '/'」，并固定 cwd=ROOT：
    #   · 本地 Windows：cl.exe 接受正斜杠路径；
    #   · Linux CI（msvc-wine）：bin/x86/cl 包装脚本把 POSIX 相对路径转成 wine
    #     内路径（与 TAK_41BB_CHS 的 /Fobuild_dll/obj/ 同款），比绝对路径少一层
    #     转换风险。刻意不用 os.sep：两个平台走**同一套命令行**，可直接比对。
    #   旧版这里硬编码 f"/Fo{obj_dir}\\"，是改用 windows runner 时留下的坑：
    #   Linux 下会变成 /Fo/home/runner/.../build\ ，cl 找不到输出目录。
    def cl_rel(p: Path) -> str:
        try:
            return p.relative_to(ROOT).as_posix()
        except ValueError:          # --out 指向仓库外时保留绝对路径
            return p.as_posix()

    fo_dir = cl_rel(out_dll.parent) + "/"      # /Fo 传目录，必须以 '/' 结尾
    src = cl_rel(SRC)
    cmd = [
        str(cl), "/nologo", "/LD", "/EHsc", "/Y-", "/utf-8", "/O2",
        "/D", "WIN32", "/D", "NDEBUG", "/D", "W4CHSDLL_EXPORTS",
        "/D", "_WINDOWS", "/D", "_USRDLL",
        f"/Fo{fo_dir}",
        "/I", src,
        f"{src}/dllmain.cpp", f"{src}/pch.cpp",
        "/link", f"/OUT:{cl_rel(out_dll)}",
        "/SUBSYSTEM:WINDOWS",
        "kernel32.lib", "user32.lib", "gdi32.lib", "advapi32.lib",
        "shell32.lib", "ole32.lib",
    ]
    # 本地 Windows：补 INCLUDE/LIB；CI 上 v 为 None，沿用 msvcenv.sh 的设定
    env = dict(os.environ)
    if v is not None:
        inc, lib = msvc_include_lib(v)
        env["INCLUDE"] = inc
        env["LIB"] = lib

    print("[build] 编译 W4CHS_DLL ...")
    rc = subprocess.run(cmd, env=env, cwd=str(ROOT))
    if rc.returncode != 0:
        print(f"!! 编译失败 rc={rc.returncode}")
        sys.exit(1)
    if not out_dll.is_file():
        print(f"!! 编译声称成功但产物缺失：{out_dll}")
        sys.exit(1)
    print(f"✓ 产物：{out_dll}  ({out_dll.stat().st_size} B)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    build(args.clean, Path(args.out) if args.out else None)


if __name__ == "__main__":
    main()

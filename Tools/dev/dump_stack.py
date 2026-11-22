#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 minidump 提取崩溃线程的寄存器与栈回溯（x86）。"""
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
data = Path("i:/LocalGames/Warlords IV Heroes of Etheria/crash_20261122_100843.dmp").read_bytes()

sig, ver, nstreams, dir_rva = struct.unpack_from("<IIII", data, 0)
streams = {}
off = dir_rva
for _ in range(nstreams):
    st, sz, rva = struct.unpack_from("<III", data, off)
    streams[st] = (rva, sz)
    off += 12

ThreadList, MemoryList = 3, 5
EXC_TID = 0x9f40

# 模块列表用于地址->函数
mods = []
if ModuleList := 4:
    rva, sz = streams[4]
    n, = struct.unpack_from("<I", data, rva)
    for i in range(n):
        m = rva + 4 + i * 108
        base, = struct.unpack_from("<Q", data, m)
        size, = struct.unpack_from("<I", data, m + 8)
        nr, = struct.unpack_from("<I", data, m + 20)
        ln, = struct.unpack_from("<I", data, nr)
        name = data[nr + 4:nr + 4 + ln].decode("utf-16le", errors="replace")
        mods.append((base, size, name))


def addr_module(a):
    for base, size, name in mods:
        if base <= a < base + size:
            return name.split("\\")[-1], a - base
    return "?", 0


# 找崩溃线程
rva, sz = streams[ThreadList]
n, = struct.unpack_from("<I", data, rva)
ctx_rva = ctx_size = stack_start = stack_size = stack_rva = 0
for i in range(n):
    t = rva + 4 + i * 48
    tid, = struct.unpack_from("<I", data, t)
    if tid == EXC_TID:
        stack_start, = struct.unpack_from("<Q", data, t + 24)
        stack_size, = struct.unpack_from("<I", data, t + 32)
        stack_rva, = struct.unpack_from("<I", data, t + 36)
        ctx_size, = struct.unpack_from("<I", data, t + 40)
        ctx_rva, = struct.unpack_from("<I", data, t + 44)
        break

ctx = data[ctx_rva:ctx_rva + ctx_size]
eip, = struct.unpack_from("<I", ctx, 0xB8)
ebp, = struct.unpack_from("<I", ctx, 0xB4)
esp, = struct.unpack_from("<I", ctx, 0xC4)
edx, = struct.unpack_from("<I", ctx, 0xA8)
eax, = struct.unpack_from("<I", ctx, 0xB0)
ecx, = struct.unpack_from("<I", ctx, 0xAC)
print(f"崩溃线程 tid={EXC_TID:#x}")
print(f"  EIP={eip:#x} ({addr_module(eip)})")
print(f"  EBP={ebp:#x} ESP={esp:#x} EDX={edx:#x} EAX={eax:#x} ECX={ecx:#x}")

# 栈回溯（ebp 链）
print("\n=== 栈回溯 (EBP chain) ===")
stack = data[stack_rva:stack_rva + stack_size]
def read32(addr):
    o = addr - stack_start
    if 0 <= o + 4 <= len(stack):
        return struct.unpack_from("<I", stack, o)[0]
    return None

cur = ebp
for depth in range(25):
    if cur is None or cur < stack_start or cur > stack_start + stack_size - 8:
        break
    ret = read32(cur + 4)
    nxt = read32(cur)
    if ret is None:
        break
    mod, rva_off = addr_module(ret)
    print(f"  #{depth}: EBP={cur:#x} ret={ret:#x} {mod}+0x{rva_off:x}")
    if nxt is None or nxt <= cur:
        break
    cur = nxt

# 扫描栈上所有看起来像代码地址的值
print("\n=== 栈上代码地址（Warlords4.exe 范围）===")
seen = set()
for i in range(0, len(stack) - 3, 4):
    v = struct.unpack_from("<I", stack, i)[0]
    if 0x400000 <= v < 0x400000 + 0x493000:
        if v not in seen:
            seen.add(v)
            mod, rva_off = addr_module(v)
            if depth < 30 and len(seen) <= 40:
                print(f"  {v:#x} {mod}+0x{rva_off:x}")

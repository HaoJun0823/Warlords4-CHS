#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小化解析 minidump：提取异常类型、崩溃地址、崩溃线程、模块列表。"""
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DUMP = Path("i:/LocalGames/Warlords IV Heroes of Etheria/crash_20261122_100843.dmp")
data = DUMP.read_bytes()

# MINIDUMP_HEADER: Signature(4) Version(4) NumberOfStreams(4) StreamDirectoryRva(4)
sig, ver, nstreams, dir_rva = struct.unpack_from("<IIII", data, 0)
print(f"sig={sig:#x} ver={ver:#x} streams={nstreams} dir_rva={dir_rva:#x}")
assert sig == 0x504d444d, "not a minidump"

streams = {}
off = dir_rva
for i in range(nstreams):
    stype, data_size, rva = struct.unpack_from("<III", data, off)
    streams[stype] = (rva, data_size)
    off += 12

# stream types
ExceptionStream = 6
ThreadListStream = 3
ModuleListStream = 4
SystemInfoStream = 7

print("\n=== Exception (type 6) ===")
if ExceptionStream in streams:
    rva, sz = streams[ExceptionStream]
    # MINIDUMP_EXCEPTION_STREAM: ThreadId(4) alignment(4) MINIDUMP_EXCEPTION(...) + ThreadContext
    tid, = struct.unpack_from("<I", data, rva)
    # MINIDUMP_EXCEPTION: ExceptionCode(4) Flags(4) Record(8) Address(8) NumberParameters(4) alignment(4) Info[15](4*15)
    exc_off = rva + 8
    code, flags = struct.unpack_from("<II", data, exc_off)
    record = struct.unpack_from("<Q", data, exc_off + 8)[0]
    addr = struct.unpack_from("<Q", data, exc_off + 16)[0]
    nparams, = struct.unpack_from("<I", data, exc_off + 24)
    print(f"  ThreadId={tid:#x} ExceptionCode={code:#x} ExceptionAddress={addr:#x} flags={flags} nparams={nparams}")
    code_names = {0xC0000005: "ACCESS_VIOLATION", 0xC0000006: "IN_PAGE_ERROR", 0xC0000094: "INT_DIVIDE_BY_ZERO",
                  0xC0000095: "INT_OVERFLOW", 0xC00000FD: "STACK_OVERFLOW", 0xC0000409: "STACK_BUFFER_OVERRUN",
                  0x80000003: "BREAKPOINT", 0xC0000374: "HEAP_CORRUPTION"}
    print(f"  异常类型: {code_names.get(code, 'UNKNOWN')}")
    # ExceptionInformation
    if nparams >= 2:
        info_off = exc_off + 32
        vals = struct.unpack_from(f"<{nparams}Q", data, info_off)
        print(f"  参数: {[hex(v) for v in vals]} (0=读/写, 1=访问地址)")
else:
    print("  无异常流")

print("\n=== Threads (type 3) ===")
if ThreadListStream in streams:
    rva, sz = streams[ThreadListStream]
    n, = struct.unpack_from("<I", data, rva)
    print(f"  线程数={n}")
    for i in range(min(n, 40)):
        t = rva + 4 + i * 48
        tid, suspend, pri, base = struct.unpack_from("<IIII", data, t)
        print(f"    tid={tid:#x} suspend={suspend} pri={pri}")

print("\n=== Modules (type 4) ===")
if ModuleListStream in streams:
    rva, sz = streams[ModuleListStream]
    n, = struct.unpack_from("<I", data, rva)
    print(f"  模块数={n}")
    # MINIDUMP_MODULE: BaseOfImage(8) SizeOfImage(4) CheckSum(4) TimeDateStamp(4) ModuleNameRva(4) ...
    for i in range(min(n, 60)):
        m = rva + 4 + i * 108
        base, = struct.unpack_from("<Q", data, m)
        size, = struct.unpack_from("<I", data, m + 8)
        name_rva, = struct.unpack_from("<I", data, m + 20)
        # MINIDUMP_STRING: Length(4) then UTF-16
        ln, = struct.unpack_from("<I", data, name_rva)
        name = data[name_rva + 4:name_rva + 4 + ln].decode("utf-16le", errors="replace")
        print(f"    {base:#x} {size:#8x} {name}")

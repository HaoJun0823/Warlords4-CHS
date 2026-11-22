// dllmain.cpp — 战神IV（Warlords4.exe）中文换行修复 ASI
// ============================================================================
// 根因（IDA 静态分析 + 对标 PanzerGeneral2CHS）：
//   引擎排版中文时，字符宽度函数把 GBK 字符码(word, 最高位=1)判为非法，
//   返回宽度 0；导致行宽计算错误、过量塞字，随后逐字节截字把汉字劈开 →
//   中文换行错乱/乱码。
//
// 本 DLL 用「纯 Win32 手动 detour」（复制 PG2CHS 框架，无 MinHook），挂 2 点：
//   · 0x5B2660  宽度函数A：GBK 字符返回全角宽度，ASCII 走原函数
//   · 0x5B2700  宽度函数B：同上
//
// 验证流程：W4CHS.ini 设 Debug=1，启动游戏看 W4CHS.log：
//   - 若日志显示传入字符码是 GBK 码（>=0x8100）→ 方案A生效
//   - 若是小索引（<0x100）→ 符号判断不成立，需改用截字对齐方案（见文档）
// ============================================================================

#include "pch.h"
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>

// ===================== 配置 =====================
static struct Cfg {
    bool  debug      = true;   // 写详细日志（默认开，便于验证）
    int   fullWidth  = 0;      // GBK 全角宽度(px)；0=自动取 halfWidth*2
} g_cfg;

static void LoadCfg() {
    char path[MAX_PATH];
    GetModuleFileNameA(nullptr, path, MAX_PATH);
    char* slash = strrchr(path, '\\');
    if (slash) *(slash + 1) = 0;
    strcat_s(path, "W4CHS.ini");
    FILE* f = fopen(path, "r");
    if (!f) return;
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "Debug", 5) == 0) {
            const char* p = strchr(line, '=');
            if (p) g_cfg.debug = (atoi(p + 1) != 0);
        } else if (strncmp(line, "FullWidth", 9) == 0) {
            const char* p = strchr(line, '=');
            if (p) g_cfg.fullWidth = atoi(p + 1);
        }
    }
    fclose(f);
}

// ===================== 日志 =====================
static FILE* g_log = nullptr;
static void Log(const char* fmt, ...) {
    if (!g_cfg.debug) return;
    if (!g_log) {
        char path[MAX_PATH];
        GetModuleFileNameA(nullptr, path, MAX_PATH);
        char* slash = strrchr(path, '\\');
        if (slash) *(slash + 1) = 0;
        strcat_s(path, "W4CHS.log");
        g_log = fopen(path, "w");
    }
    if (!g_log) return;
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fflush(g_log);
}

// ===================== 关键地址（VA, imagebase 0x400000）=====================
static const char* TARGET_EXE   = "Warlords4.exe";
static const DWORD IMAGE_BASE   = 0x400000;
static const DWORD ADDR_WIDTH_A = 0x5B2660;  // sub_5B2660 宽度函数A
static const DWORD ADDR_WIDTH_B = 0x5B2700;  // sub_5B2700 宽度函数B

// 原函数指针类型：
//   short __cdecl WidthFn(void* fontMgr, int ch, const char* s)
//   实际 prologue: push ebp; mov ebp,esp; sub esp,14h
//   参数: [ebp+8]=字符码, [ebp+0Ch]=字符串指针, ecx=字体管理器(全局 0x876100 由函数内 mov ecx,offset 设置)
typedef short (__cdecl *WidthFn)(int ch, const char* s);

static WidthFn g_origWidthA = nullptr;
static WidthFn g_origWidthB = nullptr;
static int g_dbgA = 0, g_dbgB = 0, g_dbgGBK = 0;

// ===================== 手动 Detour（复制 PG2CHS）============================
#define MAX_DETOURS 4
struct Detour { BYTE* target; int len; BYTE orig[16]; BYTE* tramp; bool installed; };
static Detour g_detours[MAX_DETOURS];
static int    g_detourCount = 0;

static bool WriteJmpChecked(BYTE* at, const void* dest) {
    LONGLONG rel = (LONGLONG)((const BYTE*)dest) - (LONGLONG)(at + 5);
    if (rel < -0x80000000LL || rel > 0x7FFFFFFFLL) return false;
    at[0] = 0xE9;
    int32_t r32 = (int32_t)rel;
    memcpy(at + 1, &r32, 4);
    return true;
}

static void* InstallDetour(DWORD va, int len, const BYTE* expect, void* hookFn) {
    HMODULE hGame = GetModuleHandleA(TARGET_EXE);
    if (!hGame) { Log("detour %08X: 找不到 %s\n", va, TARGET_EXE); return nullptr; }
    BYTE* target = (BYTE*)hGame + (va - IMAGE_BASE);
    if (g_detourCount >= MAX_DETOURS || len < 5 || len > 15) return nullptr;
    if (memcmp(target, expect, len) != 0) {
        Log("detour %08X: prologue 不符\n  实际 ", va);
        for (int i = 0; i < len; ++i) Log("%02X ", target[i]);
        Log("\n  预期 ");
        for (int i = 0; i < len; ++i) Log("%02X ", expect[i]);
        Log("\n  → 跳过（EXE 版本不符）\n");
        return nullptr;
    }
    Detour& d = g_detours[g_detourCount];
    d.target = target; d.len = len; d.installed = false;
    d.tramp = (BYTE*)VirtualAlloc(nullptr, len + 5, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!d.tramp) { Log("detour %08X: VirtualAlloc 失败\n", va); return nullptr; }
    memcpy(d.tramp, target, len);
    if (!WriteJmpChecked(d.tramp + len, target + len)) {
        Log("detour %08X: 跳板回跳超 2GB\n", va);
        VirtualFree(d.tramp, 0, MEM_RELEASE); d.tramp = nullptr; return nullptr;
    }
    memcpy(d.orig, target, len);
    DWORD op;
    if (!VirtualProtect(target, len, PAGE_EXECUTE_READWRITE, &op)) {
        Log("detour %08X: VirtualProtect 失败\n", va);
        VirtualFree(d.tramp, 0, MEM_RELEASE); d.tramp = nullptr; return nullptr;
    }
    if (!WriteJmpChecked(target, hookFn)) {
        VirtualProtect(target, len, op, &op);
        VirtualFree(d.tramp, 0, MEM_RELEASE); d.tramp = nullptr; return nullptr;
    }
    for (int i = 5; i < len; ++i) target[i] = 0x90;
    VirtualProtect(target, len, op, &op);
    FlushInstructionCache(GetCurrentProcess(), target, len);
    FlushInstructionCache(GetCurrentProcess(), d.tramp, len + 5);
    d.installed = true;
    g_detourCount++;
    Log("detour %08X: OK  hook=%p tramp=%p\n", va, hookFn, d.tramp);
    return d.tramp;
}

static void UninstallAll() {
    for (int i = 0; i < g_detourCount; ++i) {
        Detour& d = g_detours[i];
        if (!d.installed) continue;
        DWORD op;
        if (VirtualProtect(d.target, d.len, PAGE_EXECUTE_READWRITE, &op)) {
            memcpy(d.target, d.orig, d.len);
            VirtualProtect(d.target, d.len, op, &op);
            FlushInstructionCache(GetCurrentProcess(), d.target, d.len);
        }
        if (d.tramp) { VirtualFree(d.tramp, 0, MEM_RELEASE); d.tramp = nullptr; }
        d.installed = false;
    }
    g_detourCount = 0;
}

// ===================== Hook 函数 =====================
// 决策：GBK 字符（word >= 0x8100）返回全角宽度；其余走原函数。
// 用哪个原函数：A 用 g_origWidthA，B 用 g_origWidthB（保持各自行为）。
static short HookWidthCommon(int ch, const char* s, WidthFn orig, int* dbg, const char* tag) {
    WORD c = (WORD)ch;
    if (c >= 0x8100) {
        // GBK 字符码：原函数因符号判断返回 0，这里返回全角宽度
        if (g_cfg.debug && g_dbgGBK < 30) {
            Log("%s GBK ch=%04X s=%p\n", tag, c, s);
            ++g_dbgGBK;
        }
        int w = g_cfg.fullWidth > 0 ? g_cfg.fullWidth : 12; // 默认全角12px，可配置
        return (short)w;
    }
    // ASCII / 小索引：走原函数（零回归）
    if (g_cfg.debug && *dbg < 20) {
        Log("%s pass ch=%d(%04X) s=%p\n", tag, ch, c, s);
        ++(*dbg);
    }
    if (!orig) return 0;
    return orig(ch, s);
}

static short __cdecl HookWidthA(int ch, const char* s) {
    return HookWidthCommon(ch, s, g_origWidthA, &g_dbgA, "A");
}
static short __cdecl HookWidthB(int ch, const char* s) {
    return HookWidthCommon(ch, s, g_origWidthB, &g_dbgB, "B");
}

// ===================== DLL 入口 =====================
BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
    if (reason != DLL_PROCESS_ATTACH) {
        if (reason == DLL_PROCESS_DETACH) {
            UninstallAll();
            if (g_log) { fclose(g_log); g_log = nullptr; }
        }
        return TRUE;
    }
    DisableThreadLibraryCalls(hModule);
    LoadCfg();
    Log("W4CHS init debug=%d fullWidth=%d\n", g_cfg.debug, g_cfg.fullWidth);

    // prologue 期望值（实测 Warlords4.exe GOG 1.06）
    // 0x5B2660 / 0x5B2700: push ebp; mov ebp,esp; sub esp,14h
    static const BYTE kWidthPro[6] = { 0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x14 };

    g_origWidthA = (WidthFn)InstallDetour(ADDR_WIDTH_A, 6, kWidthPro, (void*)&HookWidthA);
    g_origWidthB = (WidthFn)InstallDetour(ADDR_WIDTH_B, 6, kWidthPro, (void*)&HookWidthB);

    Log("W4CHS hooks: A=%p B=%p\n", g_origWidthA, g_origWidthB);
    if (!g_origWidthA || !g_origWidthB)
        Log("W4CHS !! 有 hook 未装上（检查 EXE 版本 / prologue）\n");
    return TRUE;
}

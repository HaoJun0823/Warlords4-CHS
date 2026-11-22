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
    bool  debug       = true;  // 写详细日志
    int   fullWidth   = 0;     // GBK 全角宽度(px)（已证实引擎宽度正确，未使用）
    bool  insertSpace = true;  // 对长中文串按字符边界插入空格，帮助引擎正确分词换行
    int   wordsPerLine= 15;    // 每多少个中文字插入一个空格
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
        } else if (strncmp(line, "InsertSpace", 11) == 0) {
            const char* p = strchr(line, '=');
            if (p) g_cfg.insertSpace = (atoi(p + 1) != 0);
        } else if (strncmp(line, "WordsPerLine", 12) == 0) {
            const char* p = strchr(line, '=');
            if (p) g_cfg.wordsPerLine = atoi(p + 1);
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
static const DWORD ADDR_WRAP    = 0x5B1CA0;  // sub_5B1CA0 排版入口（观测）

// 原函数指针类型（关键：这是 __thiscall，ecx=字体管理器，栈上传 ch 和 s）：
//   5B2670  mov eax,[ebp+8]    ; ch
//   5B2673  mov edx,ecx        ; ecx = 字体管理器
//   5B2676  mov esi,[ebp+0Ch]  ; s
//   调用 trampoline 时必须把字体管理器放回 ecx，否则 0x5B26AB 处野指针崩溃。
typedef short (__cdecl *WidthFn)(int ch, const char* s);

// 排版函数: short __stdcall(void* this, char* src, short maxW, short maxL, char flag, void* out)
// prologue: push ebp; mov ebp,esp; sub esp,39Ch ; 结尾 retn 14h (5 栈参数)
typedef short (__stdcall *WrapFn)(char* src, short maxW, short maxL, char flag, void* out);
static WidthFn g_origWidthA = nullptr;
static WidthFn g_origWidthB = nullptr;
static WrapFn  g_origWrap   = nullptr;
static int g_dbgA = 0, g_dbgB = 0, g_dbgGBK = 0, g_dbgWrap = 0;

// ===================== 手动 Detour（复制 PG2CHS）============================
#define MAX_DETOURS 8
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
// 原函数 __thiscall：ecx=字体管理器，栈=[ch][s]。
// detour 用 jmp 落到 hook，进入瞬间 ecx 仍是字体管理器；compiler prologue
// 不碰 ecx，但调用 trampoline 时必须显式把 ecx 设回去，否则野指针崩溃。
//
// 用 naked-ish 技巧：hook 函数用 __fastcall，第一个参数捕获 ecx。
// __fastcall: 参数1->ecx, 参数2->edx, 其余从栈右->左。
// 但这里我们要的是「原函数的栈布局」[ebp+8]=ch [ebp+C]=s，
// 因此 hook 仍声明为 __cdecl(ch, s)，仅用内联汇编在进入时读 ecx 保存。

static short CallOrigWithThis(WidthFn origFn, void* fontMgr, int ch, const char* s) {
    short result = 0;
    WidthFn fp = origFn;      // 局部指针，内联汇编用 [fp] 间接调用
    void* fm = fontMgr;
    int   c  = ch;
    const char* ps = s;
    __asm {
        mov ecx, fm           ; 恢复 thiscall 的 ecx（字体管理器）
        push ps               ; 栈参数2（原函数 [ebp+0Ch]）
        push c                ; 栈参数1（原函数 [ebp+8]）
        call dword ptr [fp]   ; 间接调 trampoline（原函数 retn 8 自己清栈，勿 add esp）
        mov result, ax
    }
    return result;
}

// 实测（日志确认）：这两个函数是 __thiscall(void* fontMgr, int fontIndex, const char* s)，
// 测「整段字符串 s 在字体 fontIndex 下的像素宽度」。GBK 字符处理在函数内部逐字节进行。
//
// 策略：含 GBK 的字符串，引擎内部把高字节当负索引 → 宽度偏低。
// 我们先取原函数基准宽度，再按中文字符数补偿一个全角宽度。
static int CountGBK(const char* s, int* bytes) {
    int n = 0, b = 0;
    if (!s) return 0;
    for (const unsigned char* p = (const unsigned char*)s; *p; ) {
        if (*p >= 0x81 && p[1] >= 0x40) { n++; b += 2; p += 2; }
        else { b += 1; p += 1; }
    }
    if (bytes) *bytes = b;
    return n;
}

static short HookWidthCommon(int fontIndex, const char* s, WidthFn orig, int* dbg, const char* tag) {
    void* fontMgr = nullptr;
    __asm { mov fontMgr, ecx }   // 进入 hook 时 ecx = 字体管理器

    short r = orig ? CallOrigWithThis(orig, fontMgr, fontIndex, s) : 0;

    int bytes = 0;
    int gbk = CountGBK(s, &bytes);
    if (gbk > 0) {
        // 实测结论：引擎对中文算 19px/字，宽度本来正确！不要补偿。
        // 仅记录一次数据用于确认，然后原样返回。
        if (g_cfg.debug && g_dbgGBK < 6) {
            Log("%s CJK fi=%d gbk=%d bytes=%d baseW=%d (=%.1f/字) s=",
                tag, fontIndex, gbk, bytes, r, (float)r / gbk);
            for (int i = 0; i < 16 && s[i]; ++i) Log("%02X ", (BYTE)s[i]);
            Log("\n");
            ++g_dbgGBK;
        }
        return r;   // 宽度正确，原样返回
    }

    if (g_cfg.debug && *dbg < 10) {
        Log("%s ascii fi=%d baseW=%d\n", tag, fontIndex, r);
        ++(*dbg);
    }
    return r;
}

// 关键：原函数是 __thiscall retn 8（callee 清 8 字节栈参数）。
// 若 hook 用 __cdecl（caller 清栈），调用方游戏代码会栈失衡崩溃。
// 故 hook 必须 __stdcall（同样 retn 8），保持栈平衡。
static short __stdcall HookWidthA(int ch, const char* s) {
    return HookWidthCommon(ch, s, g_origWidthA, &g_dbgA, "A");
}
static short __stdcall HookWidthB(int ch, const char* s) {
    return HookWidthCommon(ch, s, g_origWidthB, &g_dbgB, "B");
}

// 排版入口观测：打印每次调用的源字符串，确定长文本是被调用多次还是画多遍。
static short __stdcall HookWrap(char* src, short maxW, short maxL, char flag, void* out) {
    void* self = nullptr;
    __asm { mov self, ecx }   // 进入时 ecx = this

    // 统计中文字符数
    int gbk = 0;
    if (src) {
        for (const unsigned char* p = (const unsigned char*)src; *p; ) {
            if (*p >= 0x81 && p[1] >= 0x40) { gbk++; p += 2; }
            else p++;
        }
    }

    char* passSrc = src;
    static char s_buf[1024];

    // 核心修复：长中文串按字符边界插入空格，帮助引擎按空格分词→正确换行，
    // 否则整句是一个"词"，排版循环无法推进指针，反复从头画整句 → 复读机。
    if (g_cfg.insertSpace && gbk >= (g_cfg.wordsPerLine + 4)) {
        int wpl = g_cfg.wordsPerLine > 0 ? g_cfg.wordsPerLine : 15;
        int si = 0, cnt = 0;
        const unsigned char* p = (const unsigned char*)src;
        while (*p && si < (int)sizeof(s_buf) - 4) {
            if (*p >= 0x81 && p[1] >= 0x40) {
                s_buf[si++] = (char)p[0];
                s_buf[si++] = (char)p[1];
                p += 2;
                // 遇到中文标点则强制断词；否则每 wpl 个字插入空格
                if (cnt && (cnt % wpl == 0)) s_buf[si++] = ' ';
                cnt++;
            } else {
                s_buf[si++] = (char)*p++;
            }
        }
        s_buf[si] = 0;
        passSrc = s_buf;
        if (g_cfg.debug && g_dbgWrap < 30) {
            Log("WRAP-INSERT gbk=%d wpl=%d -> %d bytes s=%s\n", gbk, wpl, si, s_buf);
            ++g_dbgWrap;
        }
    }

    // 手动调用原函数：ecx=this，5个栈参数，原函数 retn 14h 自清栈
    short result = 0;
    WrapFn fp = g_origWrap;
    DWORD slf = (DWORD)self;
    DWORD psrc = (DWORD)passSrc, mw = (DWORD)(short)maxW, ml = (DWORD)(short)maxL,
          fl = (DWORD)(int)flag, po = (DWORD)out;
    if (!fp) return 0;
    __asm {
        mov ecx, slf
        push po
        push fl
        push ml
        push mw
        push psrc
        call dword ptr [fp]    ; retn 14h 自清 20 字节
        mov result, ax
    }
    return result;
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
    static const BYTE kWidthPro[6] = { 0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x14 }; // 0x5B2660/0x5B2700
    // 0x5B1CA0 prologue: 55 8B EC (push ebp;mov ebp,esp) + 81 EC 9C 03 00 00 (sub esp,39Ch)
    // 必须 9 字节完整覆盖 sub esp，len=6 会截断在 imm32 中间导致跳回崩溃。
    static const BYTE kWrapPro[9]  = { 0x55, 0x8B, 0xEC, 0x81, 0xEC, 0x9C, 0x03, 0x00, 0x00 };

    g_origWidthA = (WidthFn)InstallDetour(ADDR_WIDTH_A, 6, kWidthPro, (void*)&HookWidthA);
    g_origWidthB = (WidthFn)InstallDetour(ADDR_WIDTH_B, 6, kWidthPro, (void*)&HookWidthB);
    g_origWrap   = (WrapFn) InstallDetour(ADDR_WRAP,    9, kWrapPro,  (void*)&HookWrap);

    Log("W4CHS hooks: A=%p B=%p Wrap=%p\n", g_origWidthA, g_origWidthB, g_origWrap);
    if (!g_origWidthA || !g_origWidthB || !g_origWrap)
        Log("W4CHS !! 有 hook 未装上（检查 EXE 版本 / prologue）\n");
    return TRUE;
}

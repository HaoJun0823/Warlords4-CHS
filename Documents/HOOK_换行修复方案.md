# 中文换行根治方案：ASI Loader + DLL Hook（参考 PanzerGeneral2CHS）

> 目标：根治引擎排版中文时**复读机 / 刷屏**问题。
> 分析基于 `Warlords4.exe`（GOG 1.06, PE32, imagebase 0x400000），2026-11-22~23。
> 工程范式完全对标 `G:\Projects\PanzerGeneral2CHS`（纯 Win32 手动 detour，无 MinHook）。

---

## 0. 最终有效方案（2026-11-23 验证通过）

**根因**：引擎的排版函数 `sub_5B1CA0` 依赖**按空格分词**（`sub_5B1770`）。中文整句没有空格，
被引擎当成一个超长的"词"，排版循环无法在词内换行 → 反复从头绘制整句 → **复读机/刷屏**。

**最终解法：完全接管排版（UseOwnWrap=1）**
- Hook `sub_5B1CA0 @ 0x5B1CA0`，对含中文的字符串**不再调用原函数**，
  而是自己按 GBK 字符边界分行，直接写入引擎的输出缓冲
  （out = 32 行 × 128 字节，每行一个 NUL 结尾字符串，已由 `sub_5B17F0` 反汇编确认）。
- 中文字宽 19px（实测）、ASCII 8px；累加宽度超过 `maxW` 就换行；
  超过 `maxL` 行丢弃剩余 → 不刷屏。
- **不修改字符串内容**（不插空格）→ 不拆词（"提议"/"召唤"完整）、不漏字、不截断。
- 纯 ASCII 文本仍走原函数（零回归）。

**走过的弯路（均已废弃，记录在下方仅供回溯）**：
1. ❌ 以为宽度函数参数是 GBK 字符码 → 实际是字体索引(0-15)，误判。
2. ❌ 以为中文宽度算成 0 → 实测 19px/字正确，补宽度反而错乱。
3. ❌ 插空格分词 → 拆词（"提 议"）、漏字截断（空格增加字节数超 127）、短文本刷屏更严重。
   `W4CHS.ini` 的 `insertSpace` 开关保留但默认关闭，仅为兼容旧配置。

以下第 1~3 节是当时的分析推断（部分已被上面结论推翻），保留作逆向记录。

---

## 1. 根因（与 PanzerGeneral2CHS 同类 BUG）

PanzerGeneral2CHS 的已验证结论（`dllmain.cpp` 头部）：
> `CharWidth` 逐字节 `movsx` → GBK 高位字节变负 → 负索引越界 → 崩溃/乱码。修法：hook 字符宽度，高位字节返回半宽。

Warlords 的对应点（IDA 确认）：

### 1.1 字符宽度函数（符号判断把 GBK 判为非法）

两个同构函数：
- `sub_5B2660` @ `0x5B2660`
- `sub_5B2700` @ `0x5B2700`

```asm
5B2710  mov  eax, [ebp+8]       ; 字符码(word)
5B2719  movzx eax, ax           ; 零扩展到32位
5B271C  test esi, esi           ; esi = 字符串指针
5B271E  jnz  loc_5B2733
...
5B2733  test ax, ax             ; 测 AX 符号位
5B2736  js   return_0           ; ← 字符码>=0x8000 → 宽度=0
5B2738  cmp  ax, [edx]          ; 字符码 vs 表条目数
5B273B  jge  return_0           ; ← 超出表 → 宽度=0
5B273D  cwde
5B273E  imul ecx, eax, 2Ch      ; 表项 44 字节
...
```

GBK 字符 word（如"中"=0xD6D8）最高位=1 → `js` 命中 → 返回宽度 0。

### 1.2 逐字节截字（把汉字劈成两半）

`sub_5B1CA0` @ `0x5B1CA0`（主排版，32行×128字节槽），当行超宽时：

```asm
5B2050  mov  ecx, ebx
5B2052  lea  edx, [ecx+1]
5B2055  mov  al, [ecx]           ; 逐字节扫描到末尾
5B2057  inc  ecx
5B205A  test al, al
5B205A  jnz  5B2055
5B205C  sub  ecx, edx            ; 行长度(字节)
5B205F  mov  [ebx+ecx-1], al      ; ← al=0，删最后 1 字节！
5B2063  mov  ecx, edi
5B2065  call sub_5B1C40          ; 重算宽度
5B206A  cmp  ax, si
5B206D  jg   5B2050              ; 仍超宽 → 再删 1 字节
```

每次删 1 字节，若删的是汉字一半 → 汉字劈开 → 后续字节流错位 → 乱码 + 换行乱。
分词函数 `sub_5B1770` @ `0x5B1770` 也按字节找 `0x20` 空格，整句中文被当一个超长词，必然触发截字。

---

## 2. 字符码语义链（已厘清）

```
XML字符 word → [esi+1Ch] (0x5B9994)
  → sub_5B1730(字符word) @0x5B1730
  → sub_5B1C60 把 word 存入字符对象[0] (0x5B1C70: mov [edi], ax)
  → sub_5B1C40/sub_5B1C20 读 word[字符对象] (movzx eax, word[ecx])
  → sub_5B2700/sub_5B2660 查宽度表
```

字符对象 offset 0 = 当前字符码 word。若为中文，是 GBK 码（高位置位）。

> ⚠️ 运行时验证仍建议做：hook 宽度函数后打日志，确认传入的字符码是 GBK 码还是小索引。
> 若是小索引，则 1.1 的符号判断不成立，只需处理 1.2 的截字。

---

## 3. Hook 方案（对标 PG2CHS 的 4 点 detour）

### 方案 A（推荐，先做）：Hook 两个宽度函数，修符号判断

**注入点**：`0x5B2660`（prologue `55 8B EC 83 EC 14`）和 `0x5B2700`（同 prologue）

**逻辑**：
```cpp
// 字符码来自 [ebp+8]（栈传参），esi=[ebp+0Ch] 字符串
// 原逻辑: if (ch & 0x8000 || ch >= tableSize) return 0;
// 改为:   对 GBK 字符返回合理全角宽度，其它仍走原函数
short HookWidth(void* fontMgr, int ch, const char* s) {
    WORD c = (WORD)ch;
    if (c >= 0x8100) {           // GBK 字符码区
        return FULL_WIDTH;        // 全角宽度（运行时调，先试 fontObj 的半角×2）
    }
    return origWidth(fontMgr, ch, s);  // ASCII 走原函数，零回归
}
```
**收益**：中文占正确宽度 → 行宽计算准确 → 不会过量塞字 → 大幅减少触发截字。

### 方案 B（配套）：Hook 截字循环，改为按 GBK 字符对齐删除

**注入点**：`0x5B2050`（循环入口，函数 `sub_5B1CA0` 内部）

这是 inline hook（非函数级），用 trampoline：
- 在 `0x5B2050` 放 `jmp` 到自己分配的 cave
- cave 里重新实现"扫描行尾 → 判断末尾是否 GBK 双字节 → 删 1 个完整字符（1 或 2 字节）→ 重算宽度"
- 重算宽度需回调 `sub_5B1C40` 原函数（用 detour trampoline）

### 方案 C（兜底）：Hook 绘制/排版上层，整体接管

若 A+B 仍不理想，参考 PG2CHS `WrapDrawCJK`，完整接管 `sub_5B1CA0`：
- 自己解析 UTF-8/GBK，按字符计宽，按像素宽度换行
- 工作量大，但最彻底

---

## 4. 工程结构（复制 PG2CHS 范式）

```
W4CHS_DLL/
  dllmain.cpp          # 主逻辑 + 手动 detour（复制 PG2CHS 的 Detour 结构）
  pch.h / pch.cpp
  W4CHS_DLL.vcxproj    # VS2017 v141 Win32 /LD
Tools/ci/
  build_dll_local.py   # 复制 PG2CHS，改路径/目标名
dist/common/winmm.dll  # Ultimate ASI Loader（从 PG2CHS 复制）
```

部署：`W4CHS_DLL.dll` → 改名 `W4CHS_DLL.asi`，放游戏根目录，由 `winmm.dll` 加载。

---

## 5. 关键地址速查（VA, imagebase 0x400000）

```
0x5B2660  sub_5B2660   宽度函数A（prologue 55 8B EC 83 EC 14）
0x5B2700  sub_5B2700   宽度函数B（prologue 55 8B EC 83 EC 14）
0x5B1C40  sub_5B1C40   取字符宽度包装（prologue 55 8B EC FF 75 08）
0x5B1C20  sub_5B1C20   取字符宽度包装A（同构）
0x5B1CA0  sub_5B1CA0   主排版（prologue 55 8B EC 81 EC 9C 03）
0x5B205F   逐字节删除指令（mov [ebx+ecx-1], al）
0x5B1770  sub_5B1770   分词（按 0x20）
0x5B1730  sub_5B1730   字符对象创建（参数=字符word）
0x876100  全局字体管理器
```

---

## 6. 实施顺序

1. 复制 PG2CHS 的 DLL 工程骨架到 `W4CHS_DLL/`，改 TARGET_EXE=`Warlords4.exe`、IMAGE_BASE/地址。
2. 先只装**方案 A**的两个宽度 hook + debug 日志（`W4CHS.ini` Debug=1）。
3. 启动游戏，看日志里传入的字符码：
   - 若是 GBK 码 → 方案 A 成立，调 `FULL_WIDTH` 让中文正常排版
   - 若是小索引 → 转方案 B（截字对齐）
4. 验证换行正常后，把 DLL 纳入 `build_release.py` 打包（改名 .asi + winmm.dll）。
5. CI 用 msvc-wine v141 编译（复用 PG2CHS 的 `build_dll_local.py`）。

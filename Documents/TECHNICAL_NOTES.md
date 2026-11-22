# 技术交接：Warlords IV: Heroes of Etheria (GOG 1.06) 简体中文汉化

> 本文件记录汉化可行性的**实证结论**与**踩坑过程**，供翻译 AI 与后续会话参考。
> 结论先行：**纯文本替换即可，不需要逆向、不需要改字体、不需要改配置。**

---

## 1. 结论先行

| 事项 | 结论 | 证据 |
|---|---|---|
| 文本载体 | 外部明文 XML / 行式文本，按语言目录存放 | `English/`、`Russian/` 等 6 个目录 |
| 汉化方式 | 直接把译文写进 `English/` 目录覆盖 | 实测见 §2 |
| 文本编码 | **GBK**（简体中文系统 ACP = 936） | 实测「单人游戏」正常显示 |
| 字体 | **无需修改**，原版 `Arial` 自动回退中文字形 | 实测未改 Font.ini 仍正常 |
| 语言配置 | **无需修改**，`Language.ini` 保持 `Name = english` | 实测在 English 槽位下工作 |
| 致命陷阱 | **数值实体 `&#...;` 会让引擎死循环卡死** | 两次复现，见 §2.4 |
| 命名实体 | `&apos;` / `&quot;` 安全，原文本身在使用 | `Credits.xml`、`Help.xml` |
| 复读机 BUG | 过场字幕/事件消息**单行过长会复读+内存碎片** | 见新增 §2.5 |

---

## 2.5 长文本复读机 BUG（2026-11-22 追加，重要）

### 现象
- 汉化后部分文本"复读机"式重复几十次，并夹杂其它消息的单字碎片（如"护""接""排"）。
- 这些碎片字在文本文件中**根本不存在**，是**缓冲区越界读取相邻内存**的特征。

### 根因定位（对照实验）
1. 文件内文本只出现 1 次 → 排除文件重复。
2. XML 标签配对、无非法 `&`、无 GBK 控制字符冲突 → 排除格式破坏。
3. **内容互换实验**：把 38 字的「世人常说…」与 37 字的「故事始于…」互换时间点。
   - 结果：38 字句在任何位置都复读，37 字句在任何位置都正常 → **取决于文本本身，与位置/时间轴无关**。
4. **拆句实验**：把 38 字句拆成两个 `<Text>`（25字+13字，用不同 time）→ **完全正常**。

### 结论与阈值（实测）
| 文本类型 | 安全阈值 | 超限症状 | 修复方式 |
|---|---|---|---|
| 过场字幕 `<Text>`（Campaign_*.xml） | **≤37 汉字** | >=38 字复读 | 拆成多个 `<Text time=...>` 节点，每个 ≤37 字 |
| 事件消息 `<Message>` 首段（evt/qst） | **≤24 汉字** | >24 字复读 | 用 `\|` 分页拆短，每页 ≤24 字 |
| `\|` 之后的分页 | 实测 37 字安全 | — | 独立缓冲，不需拆 |
| Help.xml / UI 文本 / 技能 | 英文原文本就 100-332 字符且正常 | 无此问题 | **不要拆**，渲染器不同 |

> 注意：CutScene 拆句会**增加 `<Text>` 节点数**，校验脚本已相应放宽（允许 Text 增加，其它标签仍须一致）。

### 状态
RC2 补丁仍含此 BUG（未拆句）。`Tools/translate/check_translation.py` 已加入长度警告（warning 级，不阻断翻译），
后续由翻译 AI 按上述阈值修复。

---

## 2. 实验记录（2026-11-22）

### 2.1 目录勘察
游戏根目录含 `English/ French/ German/ Polish/ Russian/ Spanish/` 六个语言目录，
`Language.ini` 内容为 `[Language] Name = english`。每个语言目录含同名文本文件集：
51 XML、26 nam、21 evt、20 qst、1 txt、1 ini，另有 wav/tga 非文本资产。

核心文本文件：
- `Warlords4Text.xml`（850 行，46KB）—— 主菜单/UI 文本，格式 `<Text tag="[TAG]">文本</Text>`
- `Warlords4Text1.xml`、`Warlords4Abilities.xml`、`Warlords4Help.xml`
- `Help.xml`（84KB）、`W4CampaignText.xml`、`Credits.xml`、`HotKeys.xml`
- `Warlords4Names.xml`、`Warlords4Names1.xml`、`Names/*.nam`
- `*.evt`（事件脚本）、`*.qst`（任务脚本）

### 2.2 exe 静态分析
`Warlords4.exe`（3,087,360 字节）中定位到硬编码语言列表：
```
english french german spanish italian polish russian japanese korean taiwanese
```
以及 `English\Help.xml` ... `Taiwanese\Help.xml` 等路径，
说明引擎原生支持 10 种语言（含日/韩/繁中），但 GOG 版只附了 6 个目录。
另有参数化路径 `%s\Font.ini`、`%s\HotKeys.xml`，`Language.ini`、`Language` 等字符串。
导入/引用了 `MultiByteToWideChar`、`GetACP`、`GetLocaleInfo`、`CodePage`。

字体配置 `Font.ini`：`File=Arial`（系统字体）与 `File=Eterna`（自带字体）；
`Fonts/` 目录有英文/波兰/俄文 TTF，俄文版把 `Eterna` 换成 `EternaWarlods4`。

### 2.3 编码实验
初始假设：借用 `Russian` 槽位，在 XML 中混合写入多种编码的测试文本，一次启动判断哪种有效。
测试项：`[SINGLEPLAYER]`=GBK、`[MULTIPLAYER]`=UTF-8、`[VIEWWARLORDS]`=Big5、
`[OPTIONS]`=数值实体 `&#x9009;&#x9879;`、`[CAMPAIGN]`=GBK。

现象：游戏进程卡死，CPU 累计约 29 秒后无响应，内存约 22MB（用户初报 3.5MB，
为刚启动时读数），主线程处于 Ready —— 典型的死循环烧 CPU。进程退出后无崩溃日志。

### 2.4 隔离过程与根因
| 步骤 | 变量 | 结果 |
|---|---|---|
| 恢复原版 | 无改动 | 游戏正常启动 → 确认是改动引起 |
| Russian 槽位 + 字体改 `Microsoft YaHei` | 字体名带空格 | 卡死 |
| Russian 槽位 + 原字体 + 混合文本 | 含数值实体 | 卡死 |
| English 槽位 + 原字体 + 混合文本 | 含数值实体 | 卡死 |
| English 槽位 + 原字体 + 纯 GBK/UTF-8/Big5（去掉数值实体） | 仅三种编码 | **启动成功，`[SINGLEPLAYER]` 显示正常中文「单人游戏」** |

**根因：数值实体 `&#...;` 触发引擎解析器死循环。**
字体名 `Microsoft YaHei` 带空格也可能有独立问题（但非必需，原字体已够用）。

**关键结论：**
- 引擎按系统 ACP 解码文本；简中 Windows 下 GBK 中文直接可用。
- 不需要改 `Font.ini`：GDI 的 Arial 在简中系统会回退到中文字体。
- 不需要改 `Language.ini`：English 槽位下 GBK 中文正常显示。
- 命名实体安全（原文大量使用 `&apos;` / `&quot;`），只有数值实体致命。

---

## 3. 工程约定

- `english/` 是原文只读副本，`chinese/` 是译文工作区（仅文本文件）。
- 译文必须是 **GBK 无 BOM**，保持标签结构、占位符、行数与原文一致。
- 部分原文含 **cp1252 标点**（`…` `“` `”` `–`，既非 GBK 也非 UTF-8，如 `Campaign_0.xml`、
  `Amthor05.evt` 等 19 个文件）；未翻译文件原样放行，翻译时必须换成中文标点或 GBK 可表示字符。
- `Tools/translate/check_translation.py` 强制上述铁律；CI 在 push/PR 时自动跑。
- `Tools/ci/build_release.py` 把 `chinese/` 按 `English/` 布局打成 zip，
  玩家覆盖游戏目录即可；`verify_release.py` 做包体门禁。

---

## 4. 风险与待办

- [ ] 全量翻译尚未开始（由外部翻译 AI 完成）。
- [ ] 部分 XML 属性中含人名/路径（如 `*.evt` 的 `name="Haunter"`、`string2="English\\Sounds\\..."`），
      翻译时**不要动属性值**，只翻译元素文本，否则可能破坏脚本引用与语音路径。
- [ ] 若某译文字体显示方框，再考虑自定义字库；目前实测无需。
- [ ] 可在真机逐项验证 Help / 战役 / 任务长文本是否有排版溢出（GBK 中文通常比英文短，风险低）。
- [ ] 数值实体的具体触发条件（仅 `&#x` 还是所有 `&#`）未进一步细分；工程上统一禁用即可。

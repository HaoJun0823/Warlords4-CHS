# 《战神IV：艾瑟里亚英雄》(Warlords IV: Heroes of Etheria) 简体中文汉化工程 · Warlords_IV_HOE_106_CH

> ⚠️ **使用前必读**
>
> 本补丁为个人非官方作品，**未获游戏官方授权**；安装会覆盖游戏文件，
> 可能与用户协议（EULA）冲突。请自行判断，风险自担，**安装前备份存档与原始文件**。
>
> **禁止商业使用**；二次修改后分发须公开改动记录并保留来源。

通过**纯文本替换**为 32 位《战神IV：艾瑟里亚英雄》GOG 1.06 版提供简体中文。

> **署名 / Credit**：HaoJun0823 (Randerion)
> **官方源码仓库 / Canonical source**：https://github.com/HaoJun0823/Warlords4-CHS
> **许可 / License**：[HJNCSA-1.0](LICENSE)（Apache-2.0 加附加条件，非商业用途；基础许可见 [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt)）

> 好消息：**不需要逆向、不需要改字体、不需要改配置**。
> 已实测：在 `English` 槽位下，GBK 编码的中文能被引擎正确解码，且系统字体（Arial）
> 在简体中文 Windows 上自动回退到中文字体，直接显示正常中文。
> 详见 [`Documents/TECHNICAL_NOTES.md`](Documents/TECHNICAL_NOTES.md)。

---

## 目标程序

| 项目 | 说明 |
|---|---|
| 主程序 | `Warlords4.exe`（GOG 1.06，PE32） |
| 文本来源 | `English/` 目录：51 XML + 26 nam + 21 evt + 20 qst + txt/ini |
| 文本编码 | **GBK**（简体中文 Windows 的 ACP = 936） |
| 字体 | 原版不改（`Arial` 自动回退中文字形） |
| 配置 | `Language.ini` 保持 `Name = english` |

---

## 快速开始

### 玩家：安装
到 Releases 下载最新 `Warlords4-CHS-v*.zip`，**解压到游戏根目录**（`Warlords4.exe` 所在处），
覆盖同名 `English` 文件夹即可。不要改 `Language.ini`。安装前请备份原始文件。

### 翻译者：改文本
1. 对照 `english/<同名文件>`，编辑 `chinese/<同名文件>`。
2. **只改文本内容**，保持标签、属性、格式化占位符（`%s` / `%d`）、行数不变。
3. 文件用 **GBK 编码**保存（无 BOM）。
4. 运行校验：
   ```bash
   python Tools/translate/check_translation.py
   ```
5. 提交 PR / push，CI 会自动校验、打包并上传 Artifact。

### 开发者：本机构建
```bash
python Tools/translate/check_translation.py          # 校验
python Tools/ci/build_release.py                     # 打包 -> build_out/
python Tools/ci/verify_release.py build_out          # 包体门禁
```

---

## 两个必须知道的铁律

1. **文本必须是 GBK 编码且无 BOM。** UTF-8 中文会乱码；带 BOM 可能导致解析失败。
   请勿用 Windows 记事本「另存为」默认的 UTF-8。
2. **严禁数值实体 `&#x4E2D;` / `&#20013;`。** 引擎解析器遇到会**死循环卡死**
   （2026-11-22 实测，进程 CPU 跑满、内存停在 20MB 左右）。
   需要引号时请用**命名实体** `&quot;` / `&apos;` —— 原文本身就在用，是安全的。
3. **不要改 `Font.ini` / `HotKeys.xml`。** 原字体已能显示中文（GDI 自动回退），
   改字体名有卡死风险；热键配置与翻译无关。保持原样即可。

补充规则（由校验脚本强制）：
- XML 标签结构必须与原文一致，不得增删/重排标签。
- `%s` / `%d` 等占位符数量必须与原文一致。
- `.nam` 文件行数必须与原文一致（按行索引取名字）。
- 部分原文含 **cp1252 标点**（`…` `“` `”` `–`），未翻译的文件原样放行；
  一旦翻译，必须把这些字符一并换成中文标点或 GBK 可表示字符，否则会报「非合法 GBK」。

---

## 目录导航

| 路径 | 说明 |
|---|---|
| `english/` | **原文**，从 GOG 1.06 游戏目录完整复制（含 wav/tga 等非文本资产），只读参考 |
| `chinese/` | **译文工作区**，仅含需翻译的文本文件（xml/nam/evt/qst/txt/ini），由翻译 AI 编辑 |
| `Tools/translate/check_translation.py` | 译文铁律校验 |
| `Tools/ci/build_release.py` | 装配发布包 zip |
| `Tools/ci/verify_release.py` | 发布包结构与编码门禁 |
| `.github/workflows/build-release.yml` | GitHub Actions：push/PR 自动校验打包；手动可发 Release |
| `Documents/TECHNICAL_NOTES.md` | 技术分析、实验记录、结论与待办 |
| `build_out/` | 构建产物（gitignore，不入库） |

---

## CI（GitHub Actions）

`.github/workflows/build-release.yml` 在 **push 到 `master` / `dev`**、**PR 到 `master`**
时自动运行：校验译文 → 装配 zip → 包体门禁 → 上传 Actions Artifact（保留 30 天）。
纯 Python 步骤，不需要编译工具链。

也可在 Actions 页手动 `workflow_dispatch`：

| 输入 | 作用 |
|---|---|
| `publish` | 勾选后额外创建 GitHub Release；默认**不自动发版** |
| `tag` | 发行标签，留空按 `vYYYYMMDD-HHMM` 生成 |

---

## 附赠文档：完整教程（未精简版）

游戏内教程为防刷屏做了精简（每段≤24字）。完整原文由
`Tools/dev/export_tutorials.py` 从 RC2 原始 `Help.xml` 提取，导出为：

- `docs/完整教程_未精简版.md`
- `docs/完整教程_未精简版.pdf`（微软雅黑字体，reportlab 生成）

两者随每个发布包打进 `附赠文档/` 目录，供玩家对照阅读。重新生成：

```bash
python Tools/dev/export_tutorials.py     # 需要 reportlab（仅生成 PDF 时）
```

> PDF 是预生成并入库的静态文件，CI 打包不依赖 reportlab，在 ubuntu 上也能跑。

---

## 翻译进度

`chinese/` 初值为 `english/` 的文本文件副本（尚未翻译）。翻译进度由
`check_translation.py` 输出「已改 / 未改」统计。

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 RC2 原始 Help.xml 提取未精简的完整教程，导出 Markdown + PDF。

随汉化补丁附赠：游戏内教程为防刷屏做了精简，完整原文放在此文档。
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path("G:/Projects/Warlords_IV_HOE_106_CH")
RC2_ZIP = ROOT / "releases/Warlords4_CHS_RC2_GamePreview.zip"
OUT_DIR = ROOT / "build_out"
FONT = Path("C:/Windows/Fonts/msyh.ttc")  # 微软雅黑

TITLE = "《战神IV：艾瑟里亚英雄》完整教程（未精简版）"
SUBTITLE = "游戏内教程为防止文本复读已精简，本文档保留完整原文。适用于 GOG 1.06 简体中文汉化补丁。"


def extract() -> list[tuple[str, list[str]]]:
    with zipfile.ZipFile(RC2_ZIP) as z:
        s = z.read("English/Help.xml").decode("gbk")
    # 标题映射 id -> 名称
    titles = {m.group(1): m.group(2).strip()
              for m in re.finditer(r'<Item id="(5\d\d)"[^>]*>(.*?)</Item>', s)}
    out = []
    for i in range(500, 520):
        key = str(i)
        m = re.search(r'<Entry item="' + key + r'">(.*?)</Entry>', s, re.S)
        if not m:
            continue
        paras = [t.strip() for t in re.findall(r'<Text\b[^>]*>(.*?)</Text>', m.group(1), re.S) if t.strip()]
        title = titles.get(key, f"教程 {i - 499}")
        out.append((title, paras))
    return out


def to_markdown(tutorials: list[tuple[str, list[str]]]) -> str:
    lines = [f"# {TITLE}", "", f"> {SUBTITLE}", "", "---", ""]
    for idx, (title, paras) in enumerate(tutorials, 1):
        lines.append(f"## {title}")
        lines.append("")
        for p in paras:
            lines.append(p)
            lines.append("")
        if idx != len(tutorials):
            lines.append("---")
            lines.append("")
    return "\n".join(lines)


def to_pdf(tutorials: list[tuple[str, list[str]]], path: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    pdfmetrics.registerFont(TTFont("MSYH", str(FONT), subfontIndex=0))
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm,
                            title=TITLE)

    st_title = ParagraphStyle("t", fontName="MSYH", fontSize=18, leading=26,
                              alignment=TA_CENTER, spaceAfter=8)
    st_sub = ParagraphStyle("s", fontName="MSYH", fontSize=9, leading=14,
                            alignment=TA_CENTER, textColor="#666666", spaceAfter=14)
    st_h2 = ParagraphStyle("h2", fontName="MSYH", fontSize=13, leading=18,
                           spaceBefore=12, spaceAfter=6, textColor="#2b4a7a")
    st_body = ParagraphStyle("b", fontName="MSYH", fontSize=10.5, leading=17,
                             spaceAfter=5)

    story = [Paragraph(TITLE, st_title), Paragraph(SUBTITLE, st_sub),
             HRFlowable(width="100%"), Spacer(1, 6)]
    for idx, (title, paras) in enumerate(tutorials, 1):
        story.append(Paragraph(f"{idx}. {title}", st_h2))
        for p in paras:
            story.append(Paragraph(p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), st_body))
        story.append(Spacer(1, 4))
        if idx != len(tutorials):
            story.append(HRFlowable(width="100%"))
    doc.build(story)


def main():
    tutorials = extract()
    print(f"提取 {len(tutorials)} 个教程")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = OUT_DIR / "完整教程_未精简版.md"
    pdf = OUT_DIR / "完整教程_未精简版.pdf"
    md.write_text(to_markdown(tutorials), encoding="utf-8")
    print(f"已生成 {md} ({md.stat().st_size} 字节)")
    try:
        to_pdf(tutorials, pdf)
        print(f"已生成 {pdf} ({pdf.stat().st_size} 字节)")
    except Exception as e:
        print(f"PDF 生成失败: {e}")


if __name__ == "__main__":
    main()

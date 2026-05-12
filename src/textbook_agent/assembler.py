"""Assemble all section files into a single final Markdown textbook."""

from __future__ import annotations

from pathlib import Path

from .parser import parse_toc
from .storage import ProjectStorage


def assemble(storage: ProjectStorage) -> str:
    """Read all section files in TOC order and produce final/textbook.md."""
    toc_md = storage.read_md("04_toc.md")
    if not toc_md.strip():
        raise FileNotFoundError("04_toc.md not found or empty — run `toc` first")

    toc_entries = parse_toc(toc_md)
    if not toc_entries:
        raise ValueError("Could not parse any chapters from 04_toc.md")

    brief = storage.read_md("02_book_brief.md")
    title_line = _extract_title(brief) or "教材"

    parts: list[str] = [f"# {title_line}\n"]

    for entry in toc_entries:
        ch = entry.chapter_num
        parts.append(f"\n## 第{ch}章 {entry.title}\n")

        ch_dir = storage.root / "sections" / f"ch{ch:02d}"
        if not ch_dir.exists():
            parts.append(f"\n> ⚠️ 第{ch}章正文尚未生成。\n")
            continue

        section_files = sorted(ch_dir.glob("sec*.md"))
        if not section_files:
            parts.append(f"\n> ⚠️ 第{ch}章正文尚未生成。\n")
            continue

        for sec_file in section_files:
            content = sec_file.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"\n{content}\n")

    assembled = "\n".join(parts)
    storage.write_md("final/textbook.md", assembled)
    return assembled


def _extract_title(brief_md: str) -> str:
    """Try to find book title from brief markdown."""
    import re
    m = re.search(r"[-\*]\s*书名[：:]\s*(.+)", brief_md)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+教材规格", brief_md, re.MULTILINE)
    return ""

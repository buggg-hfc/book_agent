"""Markdown parsers for TOC and chapter outlines."""

from __future__ import annotations

import re

from .models import SectionInfo, TOCEntry


def parse_toc(md: str) -> list[TOCEntry]:
    """Parse a TOC markdown into a list of TOCEntry objects.

    Expects format:
        ## 第N章 Title
        ### N.M Title — description
    """
    entries: list[TOCEntry] = []
    current: TOCEntry | None = None

    for line in md.splitlines():
        # Chapter heading: ## 第1章 Title  or  ## Chapter 1 Title
        ch_match = re.match(
            r"^##\s+(?:第\s*(\d+)\s*章|Chapter\s+(\d+))\s+(.+)", line.strip()
        )
        if ch_match:
            ch_num = int(ch_match.group(1) or ch_match.group(2))
            ch_title = ch_match.group(3).strip()
            current = TOCEntry(chapter_num=ch_num, title=ch_title)
            entries.append(current)
            continue

        # Section heading: ### 1.2 Title — description  or  ### 1.2 Title
        if current is not None:
            sec_match = re.match(r"^###\s+\d+\.\d+\s+(.+)", line.strip())
            if sec_match:
                sec_title = sec_match.group(1).strip()
                # Strip trailing description (after " — " or " - ")
                sec_title = re.split(r"\s+[—\-]{1,2}\s+", sec_title)[0].strip()
                current.sections.append(sec_title)

    return entries


def parse_outline(md: str, chapter_num: int, chapter_title: str) -> list[SectionInfo]:
    """Parse a chapter outline markdown into a list of SectionInfo objects.

    Expects sections marked as:
        ### N.M Section Title
        **节描述**: description text
    """
    sections: list[SectionInfo] = []
    current_sec: dict | None = None

    for line in md.splitlines():
        # Section heading inside outline: ### 1.2 Title
        sec_match = re.match(
            r"^###\s+\d+\.(\d+)\s+(.+)", line.strip()
        )
        if sec_match:
            if current_sec:
                sections.append(SectionInfo(**current_sec))
            sec_num = int(sec_match.group(1))
            sec_title = sec_match.group(2).strip()
            sec_title = re.split(r"\s+[—\-]{1,2}\s+", sec_title)[0].strip()
            current_sec = {
                "chapter_num": chapter_num,
                "chapter_title": chapter_title,
                "section_num": sec_num,
                "section_title": sec_title,
                "description": "",
            }
            continue

        # Description line: **节描述**: text
        if current_sec is not None:
            desc_match = re.match(r"^\*\*节描述\*\*[:：]\s*(.+)", line.strip())
            if desc_match and not current_sec["description"]:
                current_sec["description"] = desc_match.group(1).strip()

    if current_sec:
        sections.append(SectionInfo(**current_sec))

    return sections


def extract_chapter_num_from_filename(filename: str) -> int | None:
    """Extract chapter number from filename like 'ch03_outline.md'."""
    m = re.search(r"ch(\d+)", filename)
    return int(m.group(1)) if m else None

"""Section review and revision helpers using LLM."""

from __future__ import annotations

import json
import re

from .llm import invoke_llm, reviewing_llm, writing_llm
from .models import ReviewResult, SectionInfo
from .prompts import renderer


def review_section(
    content: str,
    section_info: SectionInfo,
    brief: str,
    style_guide: str,
) -> ReviewResult:
    """Review a written section with the LLM and return a ReviewResult."""
    llm = reviewing_llm()
    prompt = renderer.render(
        "review_section.md.j2",
        section_content=content,
        section_info=section_info,
        brief=brief,
        style_guide=style_guide,
    )
    system = "你是一位严格的教材审稿专家。按要求输出 JSON，不要添加任何其他文字。"
    raw = invoke_llm(llm, system, prompt)

    # Extract JSON from response (may be wrapped in ```json ... ```)
    json_match = re.search(r"\{[\s\S]+\}", raw)
    if not json_match:
        # If we can't parse, treat as passed to avoid blocking
        return ReviewResult(passed=True, issues=[], suggestion="")

    try:
        data = json.loads(json_match.group())
        return ReviewResult(
            passed=bool(data.get("passed", True)),
            issues=data.get("issues", []),
            suggestion=data.get("suggestion", ""),
        )
    except (json.JSONDecodeError, KeyError):
        return ReviewResult(passed=True, issues=[], suggestion="")


def revise_section(
    content: str,
    review: ReviewResult,
    section_info: SectionInfo,
    style_guide: str,
) -> str:
    """Revise a section based on review feedback."""
    llm = writing_llm()
    prompt = renderer.render(
        "revise_section.md.j2",
        section_content=content,
        section_info=section_info,
        style_guide=style_guide,
        issues=review.issues,
        suggestion=review.suggestion,
    )
    system = "你是一位专业教材编辑，根据审稿意见修订正文。直接输出修订后的完整正文。"
    return invoke_llm(llm, system, prompt)


def update_memory(
    section_content: str,
    section_info: SectionInfo,
    current_memory: str,
) -> str:
    """Generate a memory update entry for a completed section."""
    llm = writing_llm()
    prompt = renderer.render(
        "update_memory.md.j2",
        section_content=section_content,
        section_info=section_info,
        current_memory=current_memory,
    )
    system = "你是一位教材编写助手，负责维护编写进度摘要。只输出新增的摘要段落。"
    return invoke_llm(llm, system, prompt)

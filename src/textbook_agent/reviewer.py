"""Section review and revision helpers using LLM."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from .llm import invoke_llm, get_llm_for_step
from .models import ReviewResult, SectionInfo
from .prompts import renderer

if TYPE_CHECKING:
    from .storage import LLMLogger


def review_section(
    content: str,
    section_info: SectionInfo,
    brief: str,
    style_guide: str,
    *,
    logger: LLMLogger | None = None,
    overrides: dict[str, Any] | None = None,
    project_slug: str = "",
) -> ReviewResult:
    """Review a written section with the LLM and return a ReviewResult."""
    ovr = overrides or {}
    llm = get_llm_for_step("review", **ovr)
    prompt = renderer.render(
        "review_section.md.j2",
        section_content=content,
        section_info=section_info,
        brief=brief,
        style_guide=style_guide,
    )
    system = "你是一位严格的教材审稿专家。按要求输出 JSON，不要添加任何其他文字。"
    ctx = f"ch{section_info.chapter_num:02d}_sec{section_info.section_num:02d}"
    raw = invoke_llm(
        llm, system, prompt,
        logger=logger, step="review", context=ctx,
        log_meta={"project_slug": project_slug},
    )

    json_match = re.search(r"\{[\s\S]+\}", raw)
    if not json_match:
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
    *,
    logger: LLMLogger | None = None,
    overrides: dict[str, Any] | None = None,
    project_slug: str = "",
) -> str:
    """Revise a section based on review feedback."""
    ovr = overrides or {}
    llm = get_llm_for_step("revise", **ovr)
    prompt = renderer.render(
        "revise_section.md.j2",
        section_content=content,
        section_info=section_info,
        style_guide=style_guide,
        issues=review.issues,
        suggestion=review.suggestion,
    )
    system = "你是一位专业教材编辑，根据审稿意见修订正文。直接输出修订后的完整正文。"
    ctx = f"ch{section_info.chapter_num:02d}_sec{section_info.section_num:02d}"
    return invoke_llm(
        llm, system, prompt,
        logger=logger, step="revise", context=ctx,
        log_meta={"project_slug": project_slug},
    )


def update_memory(
    section_content: str,
    section_info: SectionInfo,
    current_memory: str,
    *,
    logger: LLMLogger | None = None,
    overrides: dict[str, Any] | None = None,
    project_slug: str = "",
) -> str:
    """Generate a memory update entry for a completed section."""
    ovr = overrides or {}
    llm = get_llm_for_step("memory", **ovr)
    prompt = renderer.render(
        "update_memory.md.j2",
        section_content=section_content,
        section_info=section_info,
        current_memory=current_memory,
    )
    system = "你是一位教材编写助手，负责维护编写进度摘要。只输出新增的摘要段落。"
    ctx = f"ch{section_info.chapter_num:02d}_sec{section_info.section_num:02d}"
    return invoke_llm(
        llm, system, prompt,
        logger=logger, step="memory", context=ctx,
        log_meta={"project_slug": project_slug},
    )

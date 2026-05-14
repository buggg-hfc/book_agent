"""LangGraph workflow — sequential pipeline for textbook generation.

Each node is idempotent: it checks whether its output file already exists
and skips generation if so (unless force=True).  This gives free resume /
checkpoint behaviour on top of LangGraph's own SqliteSaver checkpointing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .config import settings
from .llm import get_llm_for_step, invoke_llm, planning_llm, writing_llm
from .models import (
    ChapterState,
    ReviewResult,
    SectionState,
    SectionStatus,
    WorkflowStage,
)
from .parser import parse_outline, parse_toc
from .prompts import renderer
from .reviewer import review_section, revise_section, update_memory
from .storage import LLMLogger, ProjectStorage


# ─────────────────────────────────────────────────────────────── state ──────

class BookAgentState(TypedDict):
    project_dir: str
    slug: str
    action: str                       # which CLI command triggered this run
    chapter: Optional[int]            # for outline/write --chapter
    section: Optional[int]            # for write --section
    all_chapters: bool                # for --all flag
    force: bool                       # regenerate even if output exists
    model_override: Optional[str]     # --model CLI flag
    temperature_override: Optional[float]  # --temperature CLI flag
    effort_override: Optional[str]    # --effort CLI flag
    error: Optional[str]              # set on failure


# ────────────────────────────────────────────────────────────── helpers ──────

def _storage(state: BookAgentState) -> ProjectStorage:
    return ProjectStorage(Path(state["project_dir"]))


def _force(state: BookAgentState) -> bool:
    return bool(state.get("force", False))


def _overrides(state: BookAgentState) -> dict:
    """Extract CLI LLM overrides from state."""
    return {
        "model": state.get("model_override"),
        "effort": state.get("effort_override"),
        "temperature": state.get("temperature_override"),
    }


def _system_prompt(storage: ProjectStorage) -> str:
    """Build a minimal system prompt from the book brief."""
    brief = storage.read_md("02_book_brief.md")
    if not brief:
        return "你是一位资深教材编写专家，协助编写高质量教材。"
    import re
    title_m = re.search(r"[-\*]\s*书名[：:]\s*(.+)", brief)
    title = title_m.group(1).strip() if title_m else "教材"
    audience_m = re.search(r"[-\*]\s*目标读者[：:]\s*(.+)", brief)
    audience = audience_m.group(1).strip() if audience_m else "学习者"
    level_m = re.search(r"[-\*]\s*难度[级别]*[：:]\s*(.+)", brief)
    level = level_m.group(1).strip() if level_m else "入门"
    return renderer.render(
        "system.md.j2",
        book_title=title,
        audience=audience,
        level=level,
    )


# ──────────────────────────────────────────────────────────────── nodes ──────

def node_ask(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists("01_questions.md") and not _force(state):
        return state

    user_input = storage.read_md("00_user_input.md")
    if not user_input.strip():
        return {**state, "error": "00_user_input.md is empty — run `init` first"}

    ovr = _overrides(state)
    llm = get_llm_for_step("intake_questions", **ovr)
    prompt = renderer.render("intake_questions.md.j2", user_input=user_input)
    system = "你是一位专业教材策划顾问。根据用户输入生成详细追问问卷。"
    logger = storage.logger()
    result = invoke_llm(
        llm, system, prompt,
        logger=logger, step="intake_questions", context="",
        log_meta={"project_slug": state["slug"]},
    )

    storage.write_md("01_questions.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.ask)
    storage.save_state(proj)

    return state


def node_brief(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists("02_book_brief.md") and not _force(state):
        return state

    import re as _re
    user_input = storage.read_md("00_user_input.md")
    questions = storage.read_md("01_questions.md")
    if not questions.strip():
        return {**state, "error": "01_questions.md not found — run `ask` first"}
    if not _re.search(r'\*\*你的答案：\*\*\s*\S', questions):
        return {**state, "error": "请先在 01_questions.md 中填写答案（在每个「你的答案：」后面填写），然后再运行 brief"}

    ovr = _overrides(state)
    llm = get_llm_for_step("brief", **ovr)
    prompt = renderer.render("make_brief.md.j2", user_input=user_input, questions=questions)
    system = "你是一位专业教材策划顾问。生成结构化教材规格说明书。"
    logger = storage.logger()
    result = invoke_llm(
        llm, system, prompt,
        logger=logger, step="brief", context="",
        log_meta={"project_slug": state["slug"]},
    )

    storage.write_md("02_book_brief.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.brief)
    storage.save_state(proj)

    return state


def node_plan(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists("03_plan.md") and not _force(state):
        return state

    brief = storage.read_md("02_book_brief.md")
    if not brief.strip():
        return {**state, "error": "02_book_brief.md missing — run `brief` first"}

    ovr = _overrides(state)
    llm = get_llm_for_step("plan", **ovr)
    prompt = renderer.render("make_plan.md.j2", brief=brief)
    system = "你是一位资深教材策划专家。生成详细的编写总体计划。"
    logger = storage.logger()
    result = invoke_llm(
        llm, system, prompt,
        logger=logger, step="plan", context="",
        log_meta={"project_slug": state["slug"]},
    )

    storage.write_md("03_plan.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.plan)
    storage.save_state(proj)

    return state


def node_toc(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists("04_toc.md") and not _force(state):
        return state

    brief = storage.read_md("02_book_brief.md")
    plan = storage.read_md("03_plan.md")
    if not brief.strip():
        return {**state, "error": "02_book_brief.md missing — run `brief` first"}

    ovr = _overrides(state)
    llm = get_llm_for_step("toc", **ovr)
    prompt = renderer.render("make_toc.md.j2", brief=brief, plan=plan)
    system = "你是一位资深教材策划专家。生成结构清晰的全书目录。"
    logger = storage.logger()
    result = invoke_llm(
        llm, system, prompt,
        logger=logger, step="toc", context="",
        log_meta={"project_slug": state["slug"]},
    )

    storage.write_md("04_toc.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.toc)
    storage.save_state(proj)

    return state


def node_style(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    force = _force(state)
    style_done = storage.exists("style_guide.md") and not force
    gloss_done = storage.exists("glossary.md") and not force
    if style_done and gloss_done:
        return state

    brief = storage.read_md("02_book_brief.md")
    toc = storage.read_md("04_toc.md")
    if not brief.strip() or not toc.strip():
        return {**state, "error": "brief or toc missing — run those steps first"}

    ovr = _overrides(state)
    llm = get_llm_for_step("style", **ovr)
    system = "你是一位资深教材编辑。生成详细规范文档。"
    logger = storage.logger()

    if not style_done:
        prompt = renderer.render("make_style_guide.md.j2", brief=brief, toc=toc)
        result = invoke_llm(
            llm, system, prompt,
            logger=logger, step="style", context="style_guide",
            log_meta={"project_slug": state["slug"]},
        )
        storage.write_md("style_guide.md", result)

    if not gloss_done:
        prompt = renderer.render("make_glossary.md.j2", brief=brief, toc=toc)
        result = invoke_llm(
            llm, system, prompt,
            logger=logger, step="style", context="glossary",
            log_meta={"project_slug": state["slug"]},
        )
        storage.write_md("glossary.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.style)
    storage.save_state(proj)

    return state


def node_outline(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    force = _force(state)
    brief = storage.read_md("02_book_brief.md")
    toc_md = storage.read_md("04_toc.md")
    if not toc_md.strip():
        return {**state, "error": "04_toc.md missing — run `toc` first"}

    toc_entries = parse_toc(toc_md)
    if not toc_entries:
        return {**state, "error": "Could not parse chapters from 04_toc.md"}

    target_chapters = _target_chapters(state, toc_entries)

    ovr = _overrides(state)
    llm = get_llm_for_step("outline", **ovr)
    system = "你是一位资深教材编写专家。根据用户指定的章号，仅生成该单章的详细大纲，不要扩展到其他章节。"
    logger = storage.logger()
    proj = storage.load_state()

    for entry in toc_entries:
        if entry.chapter_num not in target_chapters:
            continue
        outline_rel = storage.outline_path(entry.chapter_num)
        if storage.exists(outline_rel) and not force:
            continue

        ch_ctx = f"ch{entry.chapter_num:02d}"
        prompt = renderer.render(
            "make_chapter_outline.md.j2",
            brief=brief,
            toc=toc_md,
            chapter_num=entry.chapter_num,
            chapter_title=entry.title,
            sections=entry.sections,
        )
        result = invoke_llm(
            llm, system, prompt,
            logger=logger, step="outline", context=ch_ctx,
            log_meta={"project_slug": state["slug"], "chapter": ch_ctx},
        )
        storage.write_md(outline_rel, result)

        ch_id = f"ch{entry.chapter_num:02d}"
        if ch_id not in proj.chapters:
            sections = {}
            for i, sec_title in enumerate(entry.sections, 1):
                sec_id = f"sec{entry.chapter_num:02d}_{i:02d}"
                sections[sec_id] = SectionState(section_id=sec_id, title=sec_title)
            proj.chapters[ch_id] = ChapterState(
                chapter_id=ch_id, title=entry.title, sections=sections
            )
        proj.chapters[ch_id].outline_done = True
        storage.save_state(proj)

    proj.mark_stage_done(WorkflowStage.outlines)
    storage.save_state(proj)

    return state


def node_write(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    force = _force(state)
    brief = storage.read_md("02_book_brief.md")
    toc_md = storage.read_md("04_toc.md")
    style_guide = storage.read_md("style_guide.md")
    glossary = storage.read_md("glossary.md")

    if not toc_md.strip():
        return {**state, "error": "04_toc.md missing — run `toc` first"}

    toc_entries = parse_toc(toc_md)
    target_chapters = _target_chapters(state, toc_entries)
    target_section = state.get("section")

    ovr = _overrides(state)
    logger = storage.logger()
    proj = storage.load_state()

    for entry in toc_entries:
        if entry.chapter_num not in target_chapters:
            continue

        outline_rel = storage.outline_path(entry.chapter_num)
        if not storage.exists(outline_rel):
            continue

        outline_md = storage.read_md(outline_rel)
        sec_infos = parse_outline(outline_md, entry.chapter_num, entry.title)
        if not sec_infos:
            continue

        ch_id = f"ch{entry.chapter_num:02d}"

        for sec_info in sec_infos:
            if target_section is not None and sec_info.section_num != target_section:
                continue

            sec_rel = storage.section_path(entry.chapter_num, sec_info.section_num)
            draft_rel = storage.draft_path(entry.chapter_num, sec_info.section_num)
            review_rel = storage.review_path(entry.chapter_num, sec_info.section_num)
            sec_ctx = f"ch{entry.chapter_num:02d}_sec{sec_info.section_num:02d}"
            sec_id = f"sec{entry.chapter_num:02d}_{sec_info.section_num:02d}"

            if storage.exists(sec_rel) and not force:
                _ensure_section_state(proj, ch_id, entry.title, sec_id, sec_info.section_title)
                continue

            # ── Step 1: Write (skipped when draft checkpoint exists) ─────────
            if storage.exists(draft_rel) and not force:
                content = storage.read_md(draft_rel)
            else:
                global_memory = storage.read_md(storage.memory_path())
                ch_memory = storage.read_md(storage.memory_path(entry.chapter_num))
                write_llm = get_llm_for_step("write", **ovr)
                prompt = renderer.render(
                    "write_section.md.j2",
                    brief=brief,
                    style_guide=style_guide,
                    glossary=glossary,
                    toc=toc_md,
                    chapter_outline=outline_md,
                    section_info=sec_info,
                    global_memory=global_memory,
                    chapter_memory=ch_memory,
                )
                system = _system_prompt(storage) + "\n\n每次调用只撰写用户指定的单个小节，不要输出其他小节或其他章节的内容。"
                content = invoke_llm(
                    write_llm, system, prompt,
                    logger=logger, step="write", context=sec_ctx,
                    log_meta={"project_slug": state["slug"],
                              "chapter": ch_id,
                              "section": f"sec{sec_info.section_num:02d}"},
                )
                storage.write_md(draft_rel, content)  # checkpoint 1: write done

            # ── Step 2: Review (skipped when review checkpoint exists) ───────
            if settings.section_review:
                if storage.exists(review_rel) and not force:
                    review = ReviewResult.model_validate(
                        json.loads(storage.read_md(review_rel))
                    )
                else:
                    review = review_section(
                        content, sec_info, brief, style_guide,
                        logger=logger, overrides=ovr, project_slug=state["slug"],
                    )
                    storage.write_md(
                        review_rel,
                        json.dumps(review.model_dump(), indent=2, ensure_ascii=False),
                    )  # checkpoint 2: review done

                # ── Step 3: Revise ───────────────────────────────────────────
                if not review.passed and settings.auto_revise:
                    content = revise_section(
                        content, review, sec_info, style_guide,
                        logger=logger, overrides=ovr, project_slug=state["slug"],
                    )

            # ── Finalise: save + clean up checkpoints ────────────────────────
            storage.write_md(sec_rel, content)
            storage.delete(draft_rel)
            storage.delete(review_rel)

            # ── Step 4: Update memories ──────────────────────────────────────
            current_global = storage.read_md(storage.memory_path())
            new_entry = update_memory(
                content, sec_info, current_global,
                logger=logger, overrides=ovr, project_slug=state["slug"],
            )
            storage.append_memory(storage.memory_path(), new_entry)
            storage.append_memory(storage.memory_path(entry.chapter_num), new_entry)

            # ── Update project state ─────────────────────────────────────────
            _ensure_section_state(proj, ch_id, entry.title, sec_id, sec_info.section_title)
            proj.chapters[ch_id].sections[sec_id].status = SectionStatus.done
            storage.save_state(proj)

    proj.mark_stage_done(WorkflowStage.write)
    storage.save_state(proj)

    return state


def node_assemble(state: BookAgentState) -> BookAgentState:
    from .assembler import assemble

    storage = _storage(state)
    assemble(storage)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.assemble)
    storage.save_state(proj)

    return state


# ─────────────────────────────────────────────────────────────── routing ──────

def _route(state: BookAgentState) -> str:
    return state.get("action", END)


# ───────────────────────────────────────────────────────────── graph build ───

def build_graph() -> StateGraph:
    g = StateGraph(BookAgentState)

    g.add_node("ask", node_ask)
    g.add_node("brief", node_brief)
    g.add_node("plan", node_plan)
    g.add_node("toc", node_toc)
    g.add_node("style", node_style)
    g.add_node("outline", node_outline)
    g.add_node("write", node_write)
    g.add_node("assemble", node_assemble)

    g.add_conditional_edges(
        START,
        _route,
        {
            "ask": "ask",
            "brief": "brief",
            "plan": "plan",
            "toc": "toc",
            "style": "style",
            "outline": "outline",
            "write": "write",
            "assemble": "assemble",
        },
    )

    for node in ("ask", "brief", "plan", "toc", "style", "outline", "write", "assemble"):
        g.add_edge(node, END)

    return g


def run_action(
    action: str,
    project_dir: Path,
    slug: str,
    chapter: int | None = None,
    section: int | None = None,
    all_chapters: bool = False,
    force: bool = False,
    model_override: str | None = None,
    temperature_override: float | None = None,
    effort_override: str | None = None,
) -> BookAgentState:
    """Compile the graph with SqliteSaver and invoke a specific action."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = str(project_dir / ".checkpoint.db")
    initial_state: BookAgentState = {
        "project_dir": str(project_dir),
        "slug": slug,
        "action": action,
        "chapter": chapter,
        "section": section,
        "all_chapters": all_chapters,
        "force": force,
        "model_override": model_override,
        "temperature_override": temperature_override,
        "effort_override": effort_override,
        "error": None,
    }

    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        graph = build_graph().compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": f"{slug}:{action}"}}
        result = graph.invoke(initial_state, config=config)

    return result


# ────────────────────────────────────────────────────────── private helpers ──

def _target_chapters(
    state: BookAgentState,
    toc_entries: list,
) -> set[int]:
    if state.get("all_chapters"):
        return {e.chapter_num for e in toc_entries}
    if state.get("chapter") is not None:
        return {state["chapter"]}
    return {e.chapter_num for e in toc_entries}


def _ensure_section_state(
    proj,
    ch_id: str,
    ch_title: str,
    sec_id: str,
    sec_title: str,
) -> None:
    if ch_id not in proj.chapters:
        proj.chapters[ch_id] = ChapterState(chapter_id=ch_id, title=ch_title)
    if sec_id not in proj.chapters[ch_id].sections:
        proj.chapters[ch_id].sections[sec_id] = SectionState(
            section_id=sec_id, title=sec_title
        )

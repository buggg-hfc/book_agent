"""LangGraph workflow — sequential pipeline for textbook generation.

Each node is idempotent: it checks whether its output file already exists
and skips generation if so. This gives free resume/checkpoint behaviour on
top of LangGraph's own SqliteSaver checkpointing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .config import settings
from .llm import invoke_llm, planning_llm, writing_llm
from .models import (
    ChapterState,
    SectionState,
    SectionStatus,
    WorkflowStage,
)
from .parser import parse_outline, parse_toc
from .prompts import renderer
from .reviewer import review_section, revise_section, update_memory
from .storage import ProjectStorage


# ─────────────────────────────────────────────────────────────── state ──────

class BookAgentState(TypedDict):
    project_dir: str
    slug: str
    action: str                    # which CLI command triggered this run
    chapter: Optional[int]         # for outline/write --chapter
    section: Optional[int]         # for write --section
    all_chapters: bool             # for --all flag
    error: Optional[str]           # set on failure


# ────────────────────────────────────────────────────────────── helpers ──────

def _storage(state: BookAgentState) -> ProjectStorage:
    return ProjectStorage(Path(state["project_dir"]))


def _system_prompt(storage: ProjectStorage) -> str:
    """Build a minimal system prompt from the book brief."""
    brief = storage.read_md("02_book_brief.md")
    if not brief:
        return "你是一位资深教材编写专家，协助编写高质量教材。"
    # Extract title from brief (best effort)
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
    if storage.exists("01_questions.md"):
        return state

    user_input = storage.read_md("00_user_input.md")
    if not user_input.strip():
        return {**state, "error": "00_user_input.md is empty — run `init` first"}

    llm = planning_llm()
    prompt = renderer.render("intake_questions.md.j2", user_input=user_input)
    system = "你是一位专业教材策划顾问。根据用户输入生成详细追问问卷。"
    result = invoke_llm(llm, system, prompt)

    storage.write_md("01_questions.md", f"# 追问问卷\n\n{result}\n")

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.ask)
    storage.save_state(proj)

    return state


def node_brief(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists("02_book_brief.md"):
        return state

    user_input = storage.read_md("00_user_input.md")
    answers = storage.read_md("01_answers.md")
    if not answers.strip():
        return {**state, "error": "01_answers.md not found — fill in answers first"}

    llm = planning_llm()
    prompt = renderer.render("make_brief.md.j2", user_input=user_input, answers=answers)
    system = "你是一位专业教材策划顾问。生成结构化教材规格说明书。"
    result = invoke_llm(llm, system, prompt)

    storage.write_md("02_book_brief.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.brief)
    storage.save_state(proj)

    return state


def node_plan(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists("03_plan.md"):
        return state

    brief = storage.read_md("02_book_brief.md")
    if not brief.strip():
        return {**state, "error": "02_book_brief.md missing — run `brief` first"}

    llm = planning_llm()
    prompt = renderer.render("make_plan.md.j2", brief=brief)
    system = "你是一位资深教材策划专家。生成详细的编写总体计划。"
    result = invoke_llm(llm, system, prompt)

    storage.write_md("03_plan.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.plan)
    storage.save_state(proj)

    return state


def node_toc(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists("04_toc.md"):
        return state

    brief = storage.read_md("02_book_brief.md")
    plan = storage.read_md("03_plan.md")
    if not brief.strip():
        return {**state, "error": "02_book_brief.md missing — run `brief` first"}

    llm = planning_llm()
    prompt = renderer.render("make_toc.md.j2", brief=brief, plan=plan)
    system = "你是一位资深教材策划专家。生成结构清晰的全书目录。"
    result = invoke_llm(llm, system, prompt)

    storage.write_md("04_toc.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.toc)
    storage.save_state(proj)

    return state


def node_style(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    style_done = storage.exists("style_guide.md")
    gloss_done = storage.exists("glossary.md")
    if style_done and gloss_done:
        return state

    brief = storage.read_md("02_book_brief.md")
    toc = storage.read_md("04_toc.md")
    if not brief.strip() or not toc.strip():
        return {**state, "error": "brief or toc missing — run those steps first"}

    llm = planning_llm()
    system = "你是一位资深教材编辑。生成详细规范文档。"

    if not style_done:
        prompt = renderer.render("make_style_guide.md.j2", brief=brief, toc=toc)
        result = invoke_llm(llm, system, prompt)
        storage.write_md("style_guide.md", result)

    if not gloss_done:
        prompt = renderer.render("make_glossary.md.j2", brief=brief, toc=toc)
        result = invoke_llm(llm, system, prompt)
        storage.write_md("glossary.md", result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.style)
    storage.save_state(proj)

    return state


def node_outline(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    brief = storage.read_md("02_book_brief.md")
    toc_md = storage.read_md("04_toc.md")
    if not toc_md.strip():
        return {**state, "error": "04_toc.md missing — run `toc` first"}

    toc_entries = parse_toc(toc_md)
    if not toc_entries:
        return {**state, "error": "Could not parse chapters from 04_toc.md"}

    # Determine which chapters to process
    target_chapters = _target_chapters(state, toc_entries)

    llm = planning_llm()
    system = "你是一位资深教材编写专家。生成详细的章节大纲。"

    proj = storage.load_state()

    for entry in toc_entries:
        if entry.chapter_num not in target_chapters:
            continue
        outline_rel = storage.outline_path(entry.chapter_num)
        if storage.exists(outline_rel):
            continue

        prompt = renderer.render(
            "make_chapter_outline.md.j2",
            brief=brief,
            toc=toc_md,
            chapter_num=entry.chapter_num,
            chapter_title=entry.title,
            sections=entry.sections,
        )
        result = invoke_llm(llm, system, prompt)
        storage.write_md(outline_rel, result)

        # Update state with chapter info
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
    brief = storage.read_md("02_book_brief.md")
    toc_md = storage.read_md("04_toc.md")
    style_guide = storage.read_md("style_guide.md")
    glossary = storage.read_md("glossary.md")

    if not toc_md.strip():
        return {**state, "error": "04_toc.md missing — run `toc` first"}

    toc_entries = parse_toc(toc_md)
    target_chapters = _target_chapters(state, toc_entries)
    target_section = state.get("section")

    proj = storage.load_state()

    for entry in toc_entries:
        if entry.chapter_num not in target_chapters:
            continue

        outline_rel = storage.outline_path(entry.chapter_num)
        if not storage.exists(outline_rel):
            continue  # Skip chapters without outlines

        outline_md = storage.read_md(outline_rel)
        sec_infos = parse_outline(outline_md, entry.chapter_num, entry.title)
        if not sec_infos:
            continue

        ch_id = f"ch{entry.chapter_num:02d}"

        for sec_info in sec_infos:
            if target_section is not None and sec_info.section_num != target_section:
                continue

            sec_rel = storage.section_path(entry.chapter_num, sec_info.section_num)
            if storage.exists(sec_rel):
                # Already written — update section state if needed
                sec_id = f"sec{entry.chapter_num:02d}_{sec_info.section_num:02d}"
                _ensure_section_state(proj, ch_id, entry.title, sec_id, sec_info.section_title)
                continue

            # Build context
            global_memory = storage.read_md(storage.memory_path())
            ch_memory = storage.read_md(storage.memory_path(entry.chapter_num))

            # Write section
            llm = writing_llm()
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
            system = _system_prompt(storage)
            content = invoke_llm(llm, system, prompt)

            # Review + optional revise
            if settings.section_review:
                review = review_section(content, sec_info, brief, style_guide)
                if not review.passed and settings.auto_revise:
                    content = revise_section(content, review, sec_info, style_guide)

            storage.write_md(sec_rel, content)

            # Update memories
            current_global = storage.read_md(storage.memory_path())
            new_entry = update_memory(content, sec_info, current_global)
            storage.append_memory(storage.memory_path(), new_entry)
            storage.append_memory(storage.memory_path(entry.chapter_num), new_entry)

            # Update project state
            sec_id = f"sec{entry.chapter_num:02d}_{sec_info.section_num:02d}"
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
    # Default: all chapters
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

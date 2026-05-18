"""LangGraph workflow — sequential pipeline for textbook generation.

Each node is idempotent: it checks whether its output file already exists
and skips generation if so (unless force=True).  This gives free resume /
checkpoint behaviour on top of LangGraph's own SqliteSaver checkpointing.
"""

from __future__ import annotations

import json
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from langgraph.graph import END, START, StateGraph
from rich.console import Console
from rich.progress import SpinnerColumn, TextColumn
from rich.progress import Progress as RichProgress
from typing_extensions import TypedDict

_console = Console()

from .config import settings
from .llm import ElapsedColumn, get_llm_for_step, invoke_llm, planning_llm, writing_llm
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
    log_meta = {"project_slug": state["slug"]}

    # Determine which documents still need generation
    pending: list[tuple[str, str]] = []  # (output_filename, template)
    if not style_done:
        pending.append(("style_guide.md", "make_style_guide.md.j2"))
    if not gloss_done:
        pending.append(("glossary.md", "make_glossary.md.j2"))

    style_last_n: dict[str, int] = {}
    with RichProgress(SpinnerColumn(), TextColumn("{task.description}"), ElapsedColumn(), console=_console) as progress:
        task_map = {
            fn: progress.add_task(f"▶ style  {fn.removesuffix('.md')}", total=None)
            for fn, _ in pending
        }

        def _gen_doc(filename: str, template: str) -> tuple[str, str]:
            ctx = filename.removesuffix(".md")
            tid = task_map[filename]
            prompt = renderer.render(template, brief=brief, toc=toc)
            def _hook(n: int, fn: str = filename, c: str = ctx) -> None:
                style_last_n[fn] = n
                progress.update(tid, description=f"▶ style  {c}  [{n} tokens]")
            result = invoke_llm(
                llm, system, prompt,
                logger=logger, step="style", context=ctx, log_meta=log_meta,
                update_hook=_hook,
            )
            return filename, result

        ex = ThreadPoolExecutor(max_workers=len(pending))
        futs = [ex.submit(_gen_doc, fn, tmpl) for fn, tmpl in pending]
        try:
            for fut in futs:
                filename, result = fut.result()
                storage.write_md(filename, result)
                n = style_last_n.get(filename, 0)
                tid = task_map[filename]
                progress.update(tid, description=f"[green]✓[/green] style  {filename.removesuffix('.md')}  [{n} tokens]")
                progress.stop_task(tid)
        except KeyboardInterrupt:
            for f in futs:
                f.cancel()
            ex.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            ex.shutdown(wait=True)

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

    # Fan-out: generate each chapter outline in parallel (outputs go to separate files)
    pending_entries = [
        entry for entry in toc_entries
        if entry.chapter_num in target_chapters
        and not (storage.exists(storage.outline_path(entry.chapter_num)) and not force)
    ]

    if pending_entries:
        with RichProgress(SpinnerColumn(), TextColumn("{task.description}"), ElapsedColumn(), console=_console) as progress:
            task_map = {
                entry.chapter_num: progress.add_task(
                    f"▶ outline  ch{entry.chapter_num:02d}", total=None
                )
                for entry in pending_entries
            }

            outline_last_n: dict[int, int] = {}

            def _gen_outline(entry) -> object:
                ch_num = entry.chapter_num
                ch_ctx = f"ch{ch_num:02d}"
                tid = task_map[ch_num]
                prompt = renderer.render(
                    "make_chapter_outline.md.j2",
                    brief=brief,
                    toc=toc_md,
                    chapter_num=entry.chapter_num,
                    chapter_title=entry.title,
                    sections=entry.sections,
                )
                def _hook(n: int, num: int = ch_num, ctx: str = ch_ctx) -> None:
                    outline_last_n[num] = n
                    progress.update(tid, description=f"▶ outline  {ctx}  [{n} tokens]")
                result = invoke_llm(
                    llm, system, prompt,
                    logger=logger, step="outline", context=ch_ctx,
                    log_meta={"project_slug": state["slug"], "chapter": ch_ctx},
                    update_hook=_hook,
                )
                storage.write_md(storage.outline_path(entry.chapter_num), result)
                return entry

            ex = ThreadPoolExecutor(max_workers=len(pending_entries))
            futures = [ex.submit(_gen_outline, entry) for entry in pending_entries]
            try:
                # Fan-in: state updates sequential in main thread — no state.json contention
                for fut in as_completed(futures):
                    entry = fut.result()
                    ch_num = entry.chapter_num
                    ch_ctx = f"ch{ch_num:02d}"
                    n = outline_last_n.get(ch_num, 0)
                    tid = task_map[ch_num]
                    progress.update(tid, description=f"[green]✓[/green] outline  {ch_ctx}  [{n} tokens]")
                    progress.stop_task(tid)
                    ch_id = ch_ctx
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
            except KeyboardInterrupt:
                for f in futures:
                    f.cancel()
                ex.shutdown(wait=False, cancel_futures=True)
                raise
            else:
                ex.shutdown(wait=True)

    proj.mark_stage_done(WorkflowStage.outlines)
    storage.save_state(proj)

    return state


def node_concept_map(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    if storage.exists(storage.concept_map_path()) and not _force(state):
        return state

    brief = storage.read_md("02_book_brief.md")
    toc_md = storage.read_md("04_toc.md")
    if not toc_md.strip():
        return {**state, "error": "04_toc.md missing — run `toc` first"}

    toc_entries = parse_toc(toc_md)

    all_outlines_parts = []
    for entry in toc_entries:
        outline_md = storage.read_md(storage.outline_path(entry.chapter_num))
        if outline_md.strip():
            all_outlines_parts.append(
                f"---\n\n## 第{entry.chapter_num}章：{entry.title}\n\n{outline_md}"
            )

    if not all_outlines_parts:
        return {**state, "error": "No chapter outlines found — run `outline` first"}

    all_outlines = "\n\n".join(all_outlines_parts)

    ovr = _overrides(state)
    llm = get_llm_for_step("concept_map", **ovr)
    system = "你是一位资深教材架构师。生成全书概念地图，帮助每一章的作者了解全书的概念分布与依赖关系。"
    logger = storage.logger()
    prompt = renderer.render(
        "make_concept_map.md.j2",
        brief=brief,
        toc=toc_md,
        all_outlines=all_outlines,
    )

    result = invoke_llm(
        llm, system, prompt,
        logger=logger, step="concept_map", context="",
        log_meta={"project_slug": state["slug"]},
    )

    storage.write_md(storage.concept_map_path(), result)

    proj = storage.load_state()
    proj.mark_stage_done(WorkflowStage.concept_map)
    storage.save_state(proj)

    return state


def node_write(state: BookAgentState) -> BookAgentState:
    storage = _storage(state)
    force = _force(state)
    brief = storage.read_md("02_book_brief.md")
    toc_md = storage.read_md("04_toc.md")
    style_guide = storage.read_md("style_guide.md")
    glossary = storage.read_md("glossary.md")
    concept_map_md = storage.read_md(storage.concept_map_path())  # static read-only snapshot

    if not toc_md.strip():
        return {**state, "error": "04_toc.md missing — run `toc` first"}

    toc_entries = parse_toc(toc_md)
    target_chapters = _target_chapters(state, toc_entries)
    target_section = state.get("section")

    ovr = _overrides(state)
    sys_prompt = _system_prompt(storage) + "\n\n每次调用只撰写用户指定的单个小节，不要输出其他小节或其他章节的内容。"
    proj_lock = threading.Lock()
    proj = storage.load_state()

    # Collect chapters that have outlines and belong to the target scope
    chapters_to_write: list[tuple] = []
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
        has_pending = any(
            not storage.exists(storage.section_path(entry.chapter_num, si.section_num))
            for si in sec_infos
            if target_section is None or si.section_num == target_section
        )
        if has_pending or force:
            chapters_to_write.append((entry, outline_md, sec_infos))

    if not chapters_to_write:
        with proj_lock:
            proj.mark_stage_done(WorkflowStage.write)
            storage.save_state(proj)
        return state

    _stop = threading.Event()
    write_last_n: dict[int, int] = {}

    with RichProgress(SpinnerColumn(), TextColumn("{task.description}"), ElapsedColumn(), console=_console) as progress:
        task_map = {
            entry.chapter_num: progress.add_task(
                f"▶ write  ch{entry.chapter_num:02d}", total=None
            )
            for entry, _, _ in chapters_to_write
        }

        def _write_chapter(entry, outline_md: str, sec_infos: list) -> None:
            ch_id = f"ch{entry.chapter_num:02d}"
            ch_num = entry.chapter_num
            tid = task_map[ch_num]
            logger = storage.logger()  # per-thread logger; counter may overlap, filenames stay unique

            def _step(step_name: str, ctx: str):
                """Reset per-task elapsed and announce the new step; return its update_hook."""
                progress._tasks[tid].start_time = _time.monotonic()
                progress.update(tid, description=f"▶ {step_name}  {ctx}")
                def _update(n: int, num: int = ch_num) -> None:
                    write_last_n[num] = n
                    progress.update(tid, description=f"▶ {step_name}  {ctx}  [{n} tokens]")
                return _update

            for sec_info in sec_infos:
                if _stop.is_set():
                    return
                if target_section is not None and sec_info.section_num != target_section:
                    continue

                sec_rel = storage.section_path(entry.chapter_num, sec_info.section_num)
                draft_rel = storage.draft_path(entry.chapter_num, sec_info.section_num)
                review_rel = storage.review_path(entry.chapter_num, sec_info.section_num)
                sec_ctx = f"ch{entry.chapter_num:02d}_sec{sec_info.section_num:02d}"
                sec_id = f"sec{entry.chapter_num:02d}_{sec_info.section_num:02d}"

                if storage.exists(sec_rel) and not force:
                    with proj_lock:
                        _ensure_section_state(proj, ch_id, entry.title, sec_id, sec_info.section_title)
                    continue

                # ── Step 1: Write ────────────────────────────────────────────
                write_hook = _step("write", sec_ctx)

                if storage.exists(draft_rel) and not force:
                    content = storage.read_md(draft_rel)
                    if not content.strip():
                        # Empty draft left by a previous think-loop failure; discard
                        storage.delete(draft_rel)
                        content = None
                else:
                    content = None

                if content is None:
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
                        concept_map=concept_map_md,
                        chapter_memory=ch_memory,
                    )
                    content = invoke_llm(
                        write_llm, sys_prompt, prompt,
                        logger=logger, step="write", context=sec_ctx,
                        log_meta={"project_slug": state["slug"],
                                  "chapter": ch_id,
                                  "section": f"sec{sec_info.section_num:02d}"},
                        update_hook=write_hook,
                    )
                    if not content.strip():
                        # Think-phase loop exhausted retries — skip, resume will retry
                        progress.update(tid, description=f"[yellow]⚠ write  {sec_ctx} 为空，跳过[/yellow]")
                        continue
                    storage.write_md(draft_rel, content)

                # ── Step 2: Review ───────────────────────────────────────────
                if settings.section_review:
                    review_hook = _step("review", sec_ctx)
                    if storage.exists(review_rel) and not force:
                        review = ReviewResult.model_validate(
                            json.loads(storage.read_md(review_rel))
                        )
                    else:
                        review = review_section(
                            content, sec_info, brief, style_guide,
                            logger=logger, overrides=ovr, project_slug=state["slug"],
                            update_hook=review_hook,
                        )
                        storage.write_md(
                            review_rel,
                            json.dumps(review.model_dump(), indent=2, ensure_ascii=False),
                        )

                    # ── Step 3: Revise ───────────────────────────────────────
                    if not review.passed and settings.auto_revise:
                        content = revise_section(
                            content, review, sec_info, style_guide,
                            logger=logger, overrides=ovr, project_slug=state["slug"],
                            update_hook=_step("revise", sec_ctx),
                        )

                # ── Finalise ─────────────────────────────────────────────────
                storage.write_md(sec_rel, content)
                storage.delete(draft_rel)
                storage.delete(review_rel)

                # ── Step 4: Update chapter memory (serial within chapter) ────
                ch_memory = storage.read_md(storage.memory_path(entry.chapter_num))
                new_mem_entry = update_memory(
                    content, sec_info, ch_memory,
                    logger=logger, overrides=ovr, project_slug=state["slug"],
                    update_hook=_step("memory", sec_ctx),
                )
                storage.append_memory(storage.memory_path(entry.chapter_num), new_mem_entry)

                # ── Update project state ─────────────────────────────────────
                with proj_lock:
                    _ensure_section_state(proj, ch_id, entry.title, sec_id, sec_info.section_title)
                    proj.chapters[ch_id].sections[sec_id].status = SectionStatus.done
                    storage.save_state(proj)

            n = write_last_n.get(ch_num, 0)
            progress.update(tid, description=f"[green]✓[/green] write  ch{entry.chapter_num:02d}  [{n} tokens]")
            progress.stop_task(tid)

        max_workers = min(len(chapters_to_write), 8)
        ex = ThreadPoolExecutor(max_workers=max_workers)
        futures = [
            ex.submit(_write_chapter, entry, outline_md, sec_infos)
            for entry, outline_md, sec_infos in chapters_to_write
        ]
        try:
            for fut in as_completed(futures):
                fut.result()  # re-raise any exception from a chapter thread
        except KeyboardInterrupt:
            _stop.set()
            for f in futures:
                f.cancel()
            ex.shutdown(wait=True, cancel_futures=True)
            raise
        except Exception:
            ex.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            ex.shutdown(wait=True)

    with proj_lock:
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
    g.add_node("concept_map", node_concept_map)
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
            "concept_map": "concept_map",
            "write": "write",
            "assemble": "assemble",
        },
    )

    for node in ("ask", "brief", "plan", "toc", "style", "outline", "concept_map", "write", "assemble"):
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

"""Typer CLI — entry point for all textbook-agent commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import settings
from .i18n import t
from .models import WorkflowStage
from .storage import ProjectStorage

app = typer.Typer(
    name="textbook-agent",
    help=t("app_help"),
    add_completion=False,
)
console = Console()

# Ordered pipeline stages (used by resume --until)
PIPELINE_ORDER = ["ask", "brief", "plan", "toc", "style", "outline", "concept_map", "write", "assemble"]


# ─────────────────────────────────────────────────────────────── helpers ──────

def _resolve_project_dir(slug: str) -> Path:
    return Path(settings.output_dir) / slug


def _validate_slug(slug: str) -> None:
    """Exit with a clear message if slug contains characters invalid on any OS."""
    import re
    if not re.match(r'^[A-Za-z0-9_\-]+$', slug):
        console.print(t("invalid_slug", slug=slug))
        raise typer.Exit(1)


def _require_project(slug: str) -> tuple[Path, ProjectStorage]:
    project_dir = _resolve_project_dir(slug)
    if not (project_dir / "state.json").exists():
        console.print(t("project_not_found", slug=slug))
        raise typer.Exit(1)
    return project_dir, ProjectStorage(project_dir)


def _run(
    action: str,
    project_dir: Path,
    slug: str,
    *,
    force: bool = False,
    model: str | None = None,
    effort: str | None = None,
    temperature: float | None = None,
    **kwargs,
) -> None:
    """Run a graph action.

    When settings.streaming is True tokens stream inline via invoke_llm and no
    spinner is shown.  When False the original spinner is used.
    """
    from .graph import run_action

    if settings.streaming:
        result = run_action(
            action, project_dir, slug,
            force=force,
            model_override=model,
            temperature_override=temperature,
            effort_override=effort,
            **kwargs,
        )
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task(description=t("run_spinner", action=action), total=None)
            result = run_action(
                action, project_dir, slug,
                force=force,
                model_override=model,
                temperature_override=temperature,
                effort_override=effort,
                **kwargs,
            )

    if result.get("error"):
        console.print(t("run_error", error=result["error"]))
        raise typer.Exit(1)


def _check_api_key() -> None:
    if not settings.api_key:
        console.print(t("api_key_missing"))
        raise typer.Exit(1)


def _count_pending_sections(
    storage: ProjectStorage,
    chapter: int | None,
    section: int | None,
    force: bool,
) -> tuple[list[str], list[str]]:
    """Return (pending_rels, done_rels) for the given scope."""
    from .parser import parse_outline, parse_toc

    toc_md = storage.read_md("04_toc.md")
    if not toc_md:
        return [], []
    try:
        toc_entries = parse_toc(toc_md)
    except Exception:
        return [], []

    target_chs = {chapter} if chapter is not None else {e.chapter_num for e in toc_entries}
    pending, done = [], []

    for entry in toc_entries:
        if entry.chapter_num not in target_chs:
            continue
        outline_rel = storage.outline_path(entry.chapter_num)
        if not storage.exists(outline_rel):
            continue
        try:
            outline_md = storage.read_md(outline_rel)
            sec_infos = parse_outline(outline_md, entry.chapter_num, entry.title)
        except Exception:
            continue
        for si in sec_infos:
            if section is not None and si.section_num != section:
                continue
            sec_rel = storage.section_path(entry.chapter_num, si.section_num)
            if storage.exists(sec_rel) and not force:
                done.append(sec_rel)
            else:
                pending.append(sec_rel)

    return pending, done


def _all_pending_steps(storage: ProjectStorage) -> list[str]:
    """Return all pipeline steps that still need to run, in order."""
    from .parser import parse_outline, parse_toc

    pending = []

    if not storage.exists("01_questions.md"):
        pending.append("ask")
    if not storage.exists("02_book_brief.md"):
        pending.append("brief")
    if not storage.exists("03_plan.md"):
        pending.append("plan")
    if not storage.exists("04_toc.md"):
        pending.append("toc")
    if not storage.exists("style_guide.md") or not storage.exists("glossary.md"):
        pending.append("style")

    toc_md = storage.read_md("04_toc.md")
    toc_entries = []
    if toc_md:
        try:
            toc_entries = parse_toc(toc_md)
        except Exception:
            pass

    if toc_entries:
        if any(not storage.exists(storage.outline_path(e.chapter_num)) for e in toc_entries):
            pending.append("outline")

        if not storage.exists("concept_map.md"):
            pending.append("concept_map")

        missing_section = False
        for entry in toc_entries:
            if not storage.exists(storage.outline_path(entry.chapter_num)):
                continue
            try:
                outline_md = storage.read_md(storage.outline_path(entry.chapter_num))
                for si in parse_outline(outline_md, entry.chapter_num, entry.title):
                    if not storage.exists(storage.section_path(entry.chapter_num, si.section_num)):
                        missing_section = True
                        break
            except Exception:
                continue
            if missing_section:
                break
        if missing_section:
            pending.append("write")

    if not storage.exists("final/textbook.md"):
        pending.append("assemble")

    return pending


# ──────────────────────────────────────────────────────────── commands ────────

# ── Project Management ────────────────────────────────────────────────────────

@app.command(help=t("cmd_rename"), rich_help_panel=t("panel_project"))
def rename(
    old_slug: str = typer.Argument(..., help=t("rename_opt_old")),
    new_slug: str = typer.Argument(..., help=t("rename_opt_new")),
) -> None:
    import shutil

    _validate_slug(new_slug)
    old_dir = _resolve_project_dir(old_slug)
    new_dir = _resolve_project_dir(new_slug)

    if not (old_dir / "state.json").exists():
        console.print(t("rename_not_found", old_slug=old_slug))
        raise typer.Exit(1)

    if new_dir.exists():
        console.print(t("rename_exists", new_slug=new_slug, new_dir=new_dir))
        raise typer.Exit(1)

    # 1. Move directory
    shutil.move(str(old_dir), str(new_dir))

    # 2. Update state.json
    storage = ProjectStorage(new_dir)
    state = storage.load_state()
    state.slug = new_slug
    storage.save_state(state)

    # 3. Update project.yaml
    import yaml
    yaml_path = new_dir / "project.yaml"
    if yaml_path.exists():
        meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        meta["slug"] = new_slug
        yaml_path.write_text(yaml.dump(meta, allow_unicode=True), encoding="utf-8")

    # 4. Update thread_ids in .checkpoint.db (LangGraph SqliteSaver)
    #    thread_id format: "{slug}:{action}" — update prefix in both tables
    import sqlite3
    db_path = new_dir / ".checkpoint.db"
    checkpoint_rows = 0
    if db_path.exists():
        old_prefix = old_slug + ":"
        new_prefix = new_slug + ":"
        skip_len = len(old_prefix) + 1   # SQLite SUBSTR is 1-indexed; +1 for the colon
        with sqlite3.connect(str(db_path)) as conn:
            for table in ("checkpoints", "writes"):
                cur = conn.execute(
                    f"UPDATE {table} "
                    f"SET thread_id = ? || SUBSTR(thread_id, ?) "
                    f"WHERE thread_id LIKE ?",
                    (new_prefix, skip_len, old_prefix + "%"),
                )
                checkpoint_rows += cur.rowcount

    note = t("rename_checkpoint_note", n=checkpoint_rows) if db_path.exists() else ""
    console.print(t("rename_success", old_slug=old_slug, new_slug=new_slug, new_dir=new_dir, note=note))


@app.command(help=t("cmd_init"), rich_help_panel=t("panel_project"))
def init(
    title: str = typer.Option(..., "--title", "-t", help=t("init_opt_title")),
    slug: str = typer.Option(..., "--slug", "-s", help=t("init_opt_slug")),
    info: str = typer.Option("", "--info", "-i", help=t("init_opt_info")),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help=t("init_opt_output_dir")),
) -> None:
    _validate_slug(slug)
    if output_dir:
        settings.output_dir = output_dir

    project_dir = _resolve_project_dir(slug)

    if (project_dir / "state.json").exists():
        console.print(t("init_exists", slug=slug, project_dir=project_dir))
        raise typer.Exit(0)

    project_dir.mkdir(parents=True, exist_ok=True)
    storage = ProjectStorage(project_dir)
    storage.init_project(slug=slug, title=title, info=info)

    console.print(
        Panel(
            t("init_panel_body", title=title, slug=slug, project_dir=project_dir),
            title="textbook-agent init",
            expand=False,
        )
    )


# ── Pipeline Steps ────────────────────────────────────────────────────────────

@app.command(help=t("cmd_ask"), rich_help_panel=t("panel_pipeline"))
def ask(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("01_questions.md") and not force:
        console.print(t("ask_exists"))
        raise typer.Exit(0)

    _run("ask", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(t("ask_success", project_dir=project_dir, slug=slug))


@app.command(help=t("cmd_brief"), rich_help_panel=t("panel_pipeline"))
def brief(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    _check_api_key()
    project_dir, storage = _require_project(slug)

    import re as _re
    questions = storage.read_md("01_questions.md")
    if not questions.strip():
        console.print(t("brief_no_questions", slug=slug))
        raise typer.Exit(1)
    if not _re.search(r'\*\*你的答案：\*\*\s*\S', questions):
        console.print(t("brief_not_filled", project_dir=project_dir))
        raise typer.Exit(1)

    if storage.exists("02_book_brief.md") and not force:
        console.print(t("brief_exists"))
        raise typer.Exit(0)

    _run("brief", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(t("brief_success", project_dir=project_dir))


@app.command(help=t("cmd_plan"), rich_help_panel=t("panel_pipeline"))
def plan(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("03_plan.md") and not force:
        console.print(t("plan_exists"))
        raise typer.Exit(0)

    _run("plan", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(t("plan_success", project_dir=project_dir))


@app.command(help=t("cmd_toc"), rich_help_panel=t("panel_pipeline"))
def toc(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("04_toc.md") and not force:
        console.print(t("toc_exists"))
        raise typer.Exit(0)

    _run("toc", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(t("toc_success", project_dir=project_dir))


@app.command(help=t("cmd_style"), rich_help_panel=t("panel_pipeline"))
def style(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("style_guide.md") and storage.exists("glossary.md") and not force:
        console.print(t("style_exists"))
        raise typer.Exit(0)

    _run("style", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(t("style_success", project_dir=project_dir))


@app.command(help=t("cmd_outline"), rich_help_panel=t("panel_pipeline"))
def outline(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    chapter: Optional[int] = typer.Option(None, "--chapter", "-c", help=t("outline_opt_chapter"), rich_help_panel=t("panel_scope")),
    all_chapters: bool = typer.Option(False, "--all", "-a", help=t("outline_opt_all"), rich_help_panel=t("panel_scope")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if not storage.exists("04_toc.md"):
        console.print(t("no_toc"))
        raise typer.Exit(1)

    _run(
        "outline", project_dir, slug,
        chapter=chapter,
        all_chapters=all_chapters or chapter is None,
        force=force, model=model, effort=effort, temperature=temperature,
    )
    console.print(t("outline_success", project_dir=project_dir))


@app.command(help=t("cmd_concept_map"), rich_help_panel=t("panel_pipeline"))
def concept_map(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if not storage.exists("04_toc.md"):
        console.print(t("no_toc"))
        raise typer.Exit(1)

    if storage.exists("concept_map.md") and not force:
        console.print(t("concept_map_exists"))
        raise typer.Exit(0)

    _run("concept_map", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(t("concept_map_success", project_dir=project_dir))


@app.command(help=t("cmd_write"), rich_help_panel=t("panel_pipeline"))
def write(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    chapter: Optional[int] = typer.Option(None, "--chapter", "-c", help=t("outline_opt_chapter"), rich_help_panel=t("panel_scope")),
    section: Optional[int] = typer.Option(None, "--section", "-s", help=t("write_opt_section"), rich_help_panel=t("panel_scope")),
    all_chapters: bool = typer.Option(False, "--all", "-a", help=t("write_opt_all"), rich_help_panel=t("panel_scope")),
    yes: bool = typer.Option(False, "--yes", "-y", help=t("opt_yes")),
    dry_run: bool = typer.Option(False, "--dry-run", help=t("opt_dry_run")),
    force: bool = typer.Option(False, "--force", help=t("opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    if section is not None and chapter is None:
        console.print(t("write_section_needs_chapter"))
        raise typer.Exit(1)

    project_dir, storage = _require_project(slug)

    if not storage.exists("style_guide.md"):
        console.print(t("write_no_style"))
        raise typer.Exit(1)

    # Determine scope
    is_all = all_chapters or (chapter is None and section is None)
    pending, done = _count_pending_sections(storage, chapter, section, force)

    if dry_run:
        console.print(t("write_dryrun_header"))
        if pending:
            for p in pending:
                console.print(f"  [yellow]→[/yellow] {p}")
        else:
            console.print(t("write_dryrun_empty"))
        console.print(t("write_dryrun_summary", pending=len(pending), done=len(done), total=len(pending) + len(done)))
        return

    if not pending:
        console.print(t("write_all_exist"))
        raise typer.Exit(0)

    # Safety confirmation for bulk operations
    if is_all and not yes:
        console.print(t("write_confirm_header", pending=len(pending), done=len(done), total=len(pending) + len(done)))
        for p in pending[:10]:
            console.print(f"  [yellow]→[/yellow] {p}")
        if len(pending) > 10:
            console.print(t("write_confirm_more", n=len(pending) - 10))

        confirmed = typer.confirm(t("write_confirm_prompt"), default=False)
        if not confirmed:
            console.print(t("write_aborted"))
            raise typer.Exit(0)

    _check_api_key()

    _run(
        "write", project_dir, slug,
        chapter=chapter,
        section=section,
        all_chapters=is_all,
        force=force, model=model, effort=effort, temperature=temperature,
    )
    console.print(t("write_success", project_dir=project_dir))


@app.command(help=t("cmd_assemble"), rich_help_panel=t("panel_pipeline"))
def assemble(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    force: bool = typer.Option(False, "--force", help=t("assemble_opt_force")),
) -> None:
    project_dir, storage = _require_project(slug)

    if storage.exists("final/textbook.md") and not force:
        console.print(t("assemble_exists"))
        raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(description=t("assemble_spinner"), total=None)
        from .assembler import assemble as do_assemble
        do_assemble(storage)

    output_path = project_dir / "final" / "textbook.md"
    size_kb = output_path.stat().st_size // 1024 if output_path.exists() else 0
    console.print(t("assemble_success", output_path=output_path, size_kb=size_kb))


# ── Export ────────────────────────────────────────────────────────────────────

@app.command(help=t("cmd_export"), rich_help_panel=t("panel_export"))
def export(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    format: str = typer.Option("pdf", "--format", "-f", help=t("export_opt_format")),
    output: Optional[str] = typer.Option(None, "--output", "-o", help=t("export_opt_output")),
) -> None:
    valid = ("pdf", "html", "all")
    if format not in valid:
        console.print(t("export_bad_format", choices=" | ".join(valid)))
        raise typer.Exit(1)

    project_dir, storage = _require_project(slug)

    md_path = project_dir / "final" / "textbook.md"
    if not md_path.exists():
        console.print(t("export_no_md", md_path=md_path, slug=slug))
        raise typer.Exit(1)

    out_dir = Path(output) if output else (project_dir / "final")
    from .exporter import export_html, export_pdf  # deferred import

    do_pdf  = format in ("pdf",  "all")
    do_html = format in ("html", "all")

    if do_html:
        html_path = out_dir / "textbook.html"
        export_html(md_path, html_path)
        size_kb = html_path.stat().st_size // 1024
        console.print(t("export_html_success", html_path=html_path, size_kb=size_kb))

    if do_pdf:
        pdf_path = out_dir / "textbook.pdf"
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task(description=t("export_pdf_spinner"), total=None)
            try:
                export_pdf(md_path, pdf_path)
            except (ImportError, RuntimeError) as e:
                console.print(t("export_pdf_error", error=e))
                raise typer.Exit(1)
        size_kb = pdf_path.stat().st_size // 1024
        console.print(t("export_pdf_success", pdf_path=pdf_path, size_kb=size_kb))


# ── Tools ─────────────────────────────────────────────────────────────────────

@app.command(help=t("cmd_lang"), rich_help_panel=t("panel_tools"))
def lang(
    language: str = typer.Argument(..., help=t("lang_opt")),
) -> None:
    valid = ("zh", "en")
    if language.lower() not in valid:
        console.print(t("lang_invalid", choices=" | ".join(valid)))
        raise typer.Exit(1)
    language = language.lower()

    import re as _re

    # Prefer the project-root .env (same search order as Settings.env_file).
    # Fall back to cwd .env; create at project root if neither exists.
    _project_root_env = Path(__file__).parent.parent.parent / ".env"
    _cwd_env = Path(".env")
    if _project_root_env.exists():
        env_path = _project_root_env
    elif _cwd_env.exists():
        env_path = _cwd_env
    else:
        env_path = _project_root_env

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if _re.search(r"^TEXTBOOK_LANG=", content, flags=_re.MULTILINE):
            content = _re.sub(
                r"^TEXTBOOK_LANG=.*$", f"TEXTBOOK_LANG={language}",
                content, flags=_re.MULTILINE,
            )
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += f"TEXTBOOK_LANG={language}\n"
        env_path.write_text(content, encoding="utf-8")
    else:
        env_path.write_text(f"TEXTBOOK_LANG={language}\n", encoding="utf-8")

    console.print(t("lang_set", language=language, env_path=env_path))


@app.command(help=t("cmd_status"), rich_help_panel=t("panel_tools"))
def status(
    slug: str = typer.Argument(..., help=t("opt_slug")),
) -> None:
    project_dir, storage = _require_project(slug)

    # Load state safely
    try:
        proj_state = storage.load_state()
        title = proj_state.title
        stage = proj_state.stage.value
    except Exception:
        title = slug
        stage = t("status_stage_unknown")

    # ── Count outlines and sections (fault-tolerant) ──────────────────────
    toc_ch_count = 0
    outline_done_count = 0
    total_sections = 0
    written_sections = 0

    try:
        from .parser import parse_outline, parse_toc

        toc_md = storage.read_md("04_toc.md")
        if toc_md:
            toc_entries = parse_toc(toc_md)
            toc_ch_count = len(toc_entries)
            for entry in toc_entries:
                outline_rel = storage.outline_path(entry.chapter_num)
                if storage.exists(outline_rel):
                    outline_done_count += 1
                    try:
                        outline_md = storage.read_md(outline_rel)
                        sec_infos = parse_outline(outline_md, entry.chapter_num, entry.title)
                        total_sections += len(sec_infos)
                        for si in sec_infos:
                            if storage.exists(storage.section_path(entry.chapter_num, si.section_num)):
                                written_sections += 1
                    except Exception:
                        pass
    except Exception:
        pass

    pending_sections = total_sections - written_sections

    # ── Last log file ─────────────────────────────────────────────────────
    last_log = storage.last_log_file()
    last_log_str = last_log.name if last_log else t("status_last_log_none")

    # ── Final book ────────────────────────────────────────────────────────
    final_path = project_dir / "final" / "textbook.md"
    if final_path.exists():
        size_kb = final_path.stat().st_size // 1024
        final_str = t("status_final_exists", size_kb=size_kb)
    else:
        final_str = t("status_final_missing")

    # ── Header panel ─────────────────────────────────────────────────────
    outline_info = (
        t("status_ch_count", done=outline_done_count, total=toc_ch_count)
        if toc_ch_count else t("status_unknown_toc")
    )
    section_info = (
        t("status_sec_count", written=written_sections, total=total_sections, pending=pending_sections)
        if total_sections else t("status_unknown_outline")
    )

    console.print(
        Panel(
            t("status_panel_body",
              title=title, slug=slug, stage=stage,
              outline_info=outline_info, section_info=section_info,
              final_str=final_str, last_log_str=last_log_str),
            title=t("status_panel_title"),
            expand=False,
        )
    )

    # ── Artifact checklist ────────────────────────────────────────────────
    checklist = Table(title=t("status_checklist_title"), show_header=True, header_style="bold")
    checklist.add_column(t("status_col_file"))
    checklist.add_column(t("status_col_status"))

    artifact_files = [
        ("02_book_brief.md", t("status_artifact_brief")),
        ("03_plan.md",       t("status_artifact_plan")),
        ("04_toc.md",        t("status_artifact_toc")),
        ("style_guide.md",   t("status_artifact_style")),
        ("glossary.md",      t("status_artifact_glossary")),
    ]
    for rel, label in artifact_files:
        if storage.exists(rel):
            checklist.add_row(label, t("status_file_exists"))
        else:
            checklist.add_row(label, t("status_file_pending"))

    console.print(checklist)

    # ── Chapter details (if any) ──────────────────────────────────────────
    try:
        if proj_state.chapters:
            ch_table = Table(title=t("status_ch_table_title"), show_header=True)
            ch_table.add_column(t("status_col_chapter"), style="bold")
            ch_table.add_column(t("status_col_outline"))
            ch_table.add_column(t("status_col_written"))
            ch_table.add_column(t("status_col_total"))

            for ch_id, ch_st in sorted(proj_state.chapters.items()):
                outline_str = "[green]✓[/green]" if ch_st.outline_done else "[dim]–[/dim]"
                done_s = sum(
                    1 for s in ch_st.sections.values()
                    if s.status.value in ("done", "reviewed")
                )
                total_s = len(ch_st.sections)
                ch_table.add_row(
                    f"{ch_id}: {ch_st.title}",
                    outline_str,
                    str(done_s),
                    str(total_s),
                )
            console.print(ch_table)
    except Exception:
        pass


@app.command(help=t("cmd_resume"), rich_help_panel=t("panel_tools"))
def resume(
    slug: str = typer.Argument(..., help=t("opt_slug")),
    yes: bool = typer.Option(False, "--yes", "-y", help=t("resume_opt_yes")),
    until: Optional[str] = typer.Option(
        None, "--until",
        help=t("resume_opt_until", choices=", ".join(PIPELINE_ORDER)),
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help=t("resume_opt_dry_run")),
    force: bool = typer.Option(False, "--force", help=t("resume_opt_force")),
    model: Optional[str] = typer.Option(None, "--model", help=t("opt_model"), rich_help_panel=t("panel_llm")),
    effort: Optional[str] = typer.Option(None, "--effort", help=t("opt_effort"), rich_help_panel=t("panel_llm")),
    temperature: Optional[float] = typer.Option(None, "--temperature", help=t("opt_temperature"), rich_help_panel=t("panel_llm")),
) -> None:
    if until and until not in PIPELINE_ORDER:
        console.print(t("resume_bad_until", choices=", ".join(PIPELINE_ORDER)))
        raise typer.Exit(1)

    project_dir, storage = _require_project(slug)

    # Detect "awaiting answers" — questions exist but none filled in
    import re as _re
    _q = storage.read_md("01_questions.md")
    if _q.strip() and not _re.search(r'\*\*你的答案：\*\*\s*\S', _q):
        console.print(t("resume_waiting", root=storage.root))
        raise typer.Exit(0)

    pending = _all_pending_steps(storage)

    if not pending:
        console.print(t("resume_all_done"))
        raise typer.Exit(0)

    # Apply --until filter
    if until:
        until_idx = PIPELINE_ORDER.index(until)
        pending = [s for s in pending if PIPELINE_ORDER.index(s) <= until_idx]

    if not pending:
        console.print(t("resume_until_done", until=until))
        raise typer.Exit(0)

    # Show the plan
    stop_label = t("resume_stop_label", until=until) if until else ""
    exec_label = t("resume_exec_label_all") if (yes or dry_run) else t("resume_exec_label_one")
    console.print(f"\n[bold]{exec_label}[/bold]")
    steps_to_show = pending if (yes or dry_run) else pending[:1]
    for i, step in enumerate(steps_to_show, 1):
        console.print(f"  {i}. {step}")
    if stop_label:
        console.print(stop_label)

    if dry_run:
        console.print(t("resume_dryrun_note"))
        raise typer.Exit(0)

    if not yes:
        console.print(t("resume_hint"))
        raise typer.Exit(0)

    _check_api_key()

    # Execute pending steps — recompute after each step so steps that become
    # visible only after their prerequisites run (e.g. outline after toc) are
    # picked up correctly.
    until_idx = PIPELINE_ORDER.index(until) if until else len(PIPELINE_ORDER) - 1
    while True:
        storage = ProjectStorage(project_dir)
        current_pending = [
            s for s in _all_pending_steps(storage)
            if PIPELINE_ORDER.index(s) <= until_idx
        ]
        if not current_pending:
            break
        step = current_pending[0]
        console.print(t("resume_running", step=step))
        _run(
            step, project_dir, slug,
            all_chapters=True,
            force=force, model=model, effort=effort, temperature=temperature,
        )
        console.print(t("resume_step_done", step=step))

    console.print(t("resume_done"))


if __name__ == "__main__":
    app()

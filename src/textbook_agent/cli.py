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
from .models import WorkflowStage
from .storage import ProjectStorage

app = typer.Typer(
    name="textbook-agent",
    help="AI-powered textbook writing assistant (DeepSeek + LangGraph)",
    add_completion=False,
)
console = Console()

# Ordered pipeline stages (used by resume --until)
PIPELINE_ORDER = ["ask", "brief", "plan", "toc", "style", "outline", "write", "assemble"]


# ─────────────────────────────────────────────────────────────── helpers ──────

def _resolve_project_dir(slug: str) -> Path:
    return Path(settings.output_dir) / slug


def _validate_slug(slug: str) -> None:
    """Exit with a clear message if slug contains characters invalid on any OS."""
    import re
    if not re.match(r'^[A-Za-z0-9_\-]+$', slug):
        console.print(
            f"[red]Invalid slug:[/red] '{slug}'\n"
            "Slug may only contain letters, digits, hyphens (-) and underscores (_)."
        )
        raise typer.Exit(1)


def _require_project(slug: str) -> tuple[Path, ProjectStorage]:
    project_dir = _resolve_project_dir(slug)
    if not (project_dir / "state.json").exists():
        console.print(
            f"[red]Project '{slug}' not found.[/red] "
            f"Run [bold]textbook-agent init --slug {slug}[/bold] first."
        )
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
            progress.add_task(description=f"Running [bold]{action}[/bold]…", total=None)
            result = run_action(
                action, project_dir, slug,
                force=force,
                model_override=model,
                temperature_override=temperature,
                effort_override=effort,
                **kwargs,
            )

    if result.get("error"):
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)


def _check_api_key() -> None:
    if not settings.deepseek_api_key:
        console.print(
            "[red]DEEPSEEK_API_KEY is not set.[/red]\n"
            "Copy [bold].env.example[/bold] to [bold].env[/bold] and fill in your key."
        )
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

@app.command()
def rename(
    old_slug: str = typer.Argument(..., help="Current project slug"),
    new_slug: str = typer.Argument(..., help="New project slug"),
) -> None:
    """Rename a project: moves its directory and updates slug in state files."""
    import shutil

    _validate_slug(new_slug)
    old_dir = _resolve_project_dir(old_slug)
    new_dir = _resolve_project_dir(new_slug)

    if not (old_dir / "state.json").exists():
        console.print(f"[red]Project '{old_slug}' not found.[/red]")
        raise typer.Exit(1)

    if new_dir.exists():
        console.print(f"[red]'{new_slug}' already exists at {new_dir}.[/red]")
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

    console.print(
        f"[green]✓[/green] Renamed [bold]{old_slug}[/bold] → [bold]{new_slug}[/bold]\n"
        f"  Directory: {new_dir}"
    )


@app.command()
def init(
    title: str = typer.Option(..., "--title", "-t", help="Textbook title"),
    slug: str = typer.Option(..., "--slug", "-s", help="Short project identifier (no spaces)"),
    info: str = typer.Option("", "--info", "-i", help="Brief description of the textbook"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Override output directory"),
) -> None:
    """Create a new textbook project."""
    _validate_slug(slug)
    if output_dir:
        settings.output_dir = output_dir

    project_dir = _resolve_project_dir(slug)

    if (project_dir / "state.json").exists():
        console.print(f"[yellow]Project '{slug}' already exists at {project_dir}[/yellow]")
        raise typer.Exit(0)

    project_dir.mkdir(parents=True, exist_ok=True)
    storage = ProjectStorage(project_dir)
    storage.init_project(slug=slug, title=title, info=info)

    console.print(
        Panel(
            f"[green]Project created![/green]\n\n"
            f"  [bold]Title:[/bold]  {title}\n"
            f"  [bold]Slug:[/bold]   {slug}\n"
            f"  [bold]Dir:[/bold]    {project_dir}\n\n"
            f"Next step: [bold]textbook-agent ask {slug}[/bold]",
            title="textbook-agent init",
            expand=False,
        )
    )


@app.command()
def ask(
    slug: str = typer.Argument(..., help="Project slug"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if output exists"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Generate clarification questions (saves 01_questions.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("01_questions.md") and not force:
        console.print("[yellow]01_questions.md already exists. Use --force to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("ask", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(
        f"[green]✓[/green] Questions saved to [bold]{project_dir}/01_questions.md[/bold]\n"
        f"Fill in [bold]{project_dir}/01_answers.md[/bold], then run: "
        f"[bold]textbook-agent brief {slug}[/bold]"
    )


@app.command()
def brief(
    slug: str = typer.Argument(..., help="Project slug"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if output exists"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Generate book brief from user input + answers (saves 02_book_brief.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if not storage.exists("01_answers.md"):
        console.print(
            f"[red]01_answers.md not found.[/red] "
            f"Create it at [bold]{project_dir}/01_answers.md[/bold] with your answers."
        )
        raise typer.Exit(1)

    if storage.exists("02_book_brief.md") and not force:
        console.print("[yellow]02_book_brief.md already exists. Use --force to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("brief", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(f"[green]✓[/green] Brief saved to [bold]{project_dir}/02_book_brief.md[/bold]")


@app.command()
def plan(
    slug: str = typer.Argument(..., help="Project slug"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if output exists"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Generate overall writing plan (saves 03_plan.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("03_plan.md") and not force:
        console.print("[yellow]03_plan.md already exists. Use --force to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("plan", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(f"[green]✓[/green] Plan saved to [bold]{project_dir}/03_plan.md[/bold]")


@app.command()
def toc(
    slug: str = typer.Argument(..., help="Project slug"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if output exists"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Generate table of contents (saves 04_toc.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("04_toc.md") and not force:
        console.print("[yellow]04_toc.md already exists. Use --force to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("toc", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(f"[green]✓[/green] TOC saved to [bold]{project_dir}/04_toc.md[/bold]")


@app.command()
def style(
    slug: str = typer.Argument(..., help="Project slug"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if output exists"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Generate style guide and glossary (saves style_guide.md + glossary.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("style_guide.md") and storage.exists("glossary.md") and not force:
        console.print("[yellow]style_guide.md and glossary.md already exist. Use --force to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("style", project_dir, slug, force=force, model=model, effort=effort, temperature=temperature)
    console.print(
        f"[green]✓[/green] Saved [bold]style_guide.md[/bold] and [bold]glossary.md[/bold] "
        f"to {project_dir}"
    )


@app.command()
def outline(
    slug: str = typer.Argument(..., help="Project slug"),
    chapter: Optional[int] = typer.Option(None, "--chapter", "-c", help="Generate outline for one chapter"),
    all_chapters: bool = typer.Option(False, "--all", "-a", help="Generate outlines for all chapters"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if output exists"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Generate chapter outline(s) (saves outlines/chXX_outline.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if not storage.exists("04_toc.md"):
        console.print("[red]04_toc.md not found.[/red] Run [bold]textbook-agent toc[/bold] first.")
        raise typer.Exit(1)

    _run(
        "outline", project_dir, slug,
        chapter=chapter,
        all_chapters=all_chapters or chapter is None,
        force=force, model=model, effort=effort, temperature=temperature,
    )
    console.print(f"[green]✓[/green] Outline(s) saved to [bold]{project_dir}/outlines/[/bold]")


@app.command()
def write(
    slug: str = typer.Argument(..., help="Project slug"),
    chapter: Optional[int] = typer.Option(None, "--chapter", "-c", help="Write sections for one chapter"),
    section: Optional[int] = typer.Option(None, "--section", "-s", help="Write one specific section (requires --chapter)"),
    all_chapters: bool = typer.Option(False, "--all", "-a", help="Write all chapters"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated without calling LLM"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if section files exist"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Write section content (saves sections/chXX/secXX_YY.md)."""
    if section is not None and chapter is None:
        console.print(
            "[red]--section requires --chapter.[/red] "
            "Use: textbook-agent write SLUG --chapter N --section M"
        )
        raise typer.Exit(1)

    project_dir, storage = _require_project(slug)

    if not storage.exists("style_guide.md"):
        console.print("[red]style_guide.md not found.[/red] Run [bold]textbook-agent style[/bold] first.")
        raise typer.Exit(1)

    # Determine scope
    is_all = all_chapters or (chapter is None and section is None)
    pending, done = _count_pending_sections(storage, chapter, section, force)

    if dry_run:
        console.print(f"[bold]Dry-run — sections that would be written:[/bold]")
        if pending:
            for p in pending:
                console.print(f"  [yellow]→[/yellow] {p}")
        else:
            console.print("  [green]Nothing to generate (all sections already exist).[/green]")
        console.print(
            f"\n[dim]{len(pending)} pending, {len(done)} already done, "
            f"{len(pending) + len(done)} total in scope[/dim]"
        )
        return

    if not pending:
        console.print("[green]✓[/green] All sections in scope already exist. Use [bold]--force[/bold] to regenerate.")
        raise typer.Exit(0)

    # Safety confirmation for bulk operations
    if is_all and not yes:
        console.print(
            f"[bold]About to generate {len(pending)} section(s)[/bold] "
            f"({len(done)} already done, {len(pending) + len(done)} total):\n"
        )
        for p in pending[:10]:
            console.print(f"  [yellow]→[/yellow] {p}")
        if len(pending) > 10:
            console.print(f"  [dim]... and {len(pending) - 10} more[/dim]")

        confirmed = typer.confirm("\nProceed?", default=False)
        if not confirmed:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    _check_api_key()

    _run(
        "write", project_dir, slug,
        chapter=chapter,
        section=section,
        all_chapters=is_all,
        force=force, model=model, effort=effort, temperature=temperature,
    )
    console.print(f"[green]✓[/green] Section(s) saved to [bold]{project_dir}/sections/[/bold]")


@app.command()
def assemble(
    slug: str = typer.Argument(..., help="Project slug"),
    force: bool = typer.Option(False, "--force", help="Reassemble even if final/textbook.md exists"),
) -> None:
    """Assemble all sections into final/textbook.md."""
    project_dir, storage = _require_project(slug)

    if storage.exists("final/textbook.md") and not force:
        console.print("[yellow]final/textbook.md already exists. Use --force to reassemble.[/yellow]")
        raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(description="Assembling textbook…", total=None)
        from .assembler import assemble as do_assemble
        do_assemble(storage)

    output_path = project_dir / "final" / "textbook.md"
    size_kb = output_path.stat().st_size // 1024 if output_path.exists() else 0
    console.print(
        f"[green]✓[/green] Final textbook saved to [bold]{output_path}[/bold] "
        f"({size_kb} KB)"
    )


@app.command()
def status(
    slug: str = typer.Argument(..., help="Project slug"),
) -> None:
    """Show current project generation progress."""
    project_dir, storage = _require_project(slug)

    # Load state safely
    try:
        proj_state = storage.load_state()
        title = proj_state.title
        stage = proj_state.stage.value
    except Exception:
        title = slug
        stage = "unknown"

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
    last_log_str = last_log.name if last_log else "none"

    # ── Final book ────────────────────────────────────────────────────────
    final_path = project_dir / "final" / "textbook.md"
    if final_path.exists():
        size_kb = final_path.stat().st_size // 1024
        final_str = f"[green]✓[/green] exists ({size_kb} KB)"
    else:
        final_str = "[dim]not assembled yet[/dim]"

    # ── Header panel ─────────────────────────────────────────────────────
    outline_info = (
        f"{outline_done_count}/{toc_ch_count} chapters"
        if toc_ch_count else "[dim]unknown (toc missing)[/dim]"
    )
    section_info = (
        f"{written_sections} written / {total_sections} total "
        f"([yellow]{pending_sections} pending[/yellow])"
        if total_sections else "[dim]unknown (outlines missing)[/dim]"
    )

    console.print(
        Panel(
            f"[bold]{title}[/bold]  [dim](slug: {slug})[/dim]\n"
            f"Current stage:  [cyan]{stage}[/cyan]\n\n"
            f"Outlines:       {outline_info}\n"
            f"Sections:       {section_info}\n"
            f"Final book:     {final_str}\n"
            f"Last LLM log:   [dim]{last_log_str}[/dim]",
            title="Project Status",
            expand=False,
        )
    )

    # ── Artifact checklist ────────────────────────────────────────────────
    checklist = Table(title="Artifact Checklist", show_header=True, header_style="bold")
    checklist.add_column("File")
    checklist.add_column("Status")

    artifact_files = [
        ("02_book_brief.md", "Book brief"),
        ("03_plan.md", "Writing plan"),
        ("04_toc.md", "Table of contents"),
        ("style_guide.md", "Style guide"),
        ("glossary.md", "Glossary"),
    ]
    for rel, label in artifact_files:
        if storage.exists(rel):
            checklist.add_row(label, "[green]✓ exists[/green]")
        else:
            checklist.add_row(label, "[yellow]pending[/yellow]")

    console.print(checklist)

    # ── Chapter details (if any) ──────────────────────────────────────────
    try:
        if proj_state.chapters:
            ch_table = Table(title="Chapter Progress", show_header=True)
            ch_table.add_column("Chapter", style="bold")
            ch_table.add_column("Outline")
            ch_table.add_column("Written")
            ch_table.add_column("Total")

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


@app.command()
def resume(
    slug: str = typer.Argument(..., help="Project slug"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Execute the pending steps (default: show only)"),
    until: Optional[str] = typer.Option(
        None, "--until",
        help=f"Stop after this step. Choices: {', '.join(PIPELINE_ORDER)}",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show pending steps without running anything"),
    force: bool = typer.Option(False, "--force", help="Regenerate even if output files exist"),
    model: Optional[str] = typer.Option(None, "--model", help="Override LLM model"),
    effort: Optional[str] = typer.Option(None, "--effort", help="Override reasoning_effort"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Override temperature"),
) -> None:
    """Show next pending step (default) or resume execution (--yes).

    Examples:
      textbook-agent resume my-book              # show next step only
      textbook-agent resume my-book --yes        # run all pending steps
      textbook-agent resume my-book --until toc --yes
      textbook-agent resume my-book --dry-run
    """
    if until and until not in PIPELINE_ORDER:
        console.print(
            f"[red]--until must be one of:[/red] {', '.join(PIPELINE_ORDER)}"
        )
        raise typer.Exit(1)

    project_dir, storage = _require_project(slug)

    # Detect "awaiting answers" — a special blocked state
    if storage.exists("01_questions.md") and not storage.exists("01_answers.md"):
        console.print(
            f"[yellow]Waiting for your answers.[/yellow]\n"
            f"Create [bold]{storage.root}/01_answers.md[/bold] "
            f"with responses to the questions in 01_questions.md, then run resume again."
        )
        raise typer.Exit(0)

    pending = _all_pending_steps(storage)

    if not pending:
        console.print("[green]✓[/green] All steps are complete. Nothing to resume.")
        raise typer.Exit(0)

    # Apply --until filter
    if until:
        until_idx = PIPELINE_ORDER.index(until)
        pending = [s for s in pending if PIPELINE_ORDER.index(s) <= until_idx]

    if not pending:
        console.print(
            f"[green]✓[/green] All steps up to [bold]{until}[/bold] are complete."
        )
        raise typer.Exit(0)

    # Show the plan
    stop_label = f"  [dim]Stop at: {until}[/dim]" if until else ""
    exec_label = "Will run:" if (yes or dry_run) else "Next pending step:"
    console.print(f"\n[bold]{exec_label}[/bold]")
    steps_to_show = pending if (yes or dry_run) else pending[:1]
    for i, step in enumerate(steps_to_show, 1):
        console.print(f"  {i}. {step}")
    if stop_label:
        console.print(stop_label)

    if dry_run:
        console.print("\n[dim](dry-run — no LLM calls made)[/dim]")
        raise typer.Exit(0)

    if not yes:
        console.print(
            "\n[dim]Run with [bold]--yes[/bold] to execute. "
            "Add [bold]--until STEP[/bold] to set a stopping point.[/dim]"
        )
        raise typer.Exit(0)

    _check_api_key()

    # Execute pending steps
    for step in pending:
        console.print(f"\n[bold cyan]▶ Running: {step}[/bold cyan]")
        _run(
            step, project_dir, slug,
            all_chapters=True,
            force=force, model=model, effort=effort, temperature=temperature,
        )
        console.print(f"[green]✓[/green] {step} complete.")
        # Reload storage after each step in case TOC changed
        storage = ProjectStorage(project_dir)

    console.print("\n[green]✓[/green] Resume complete.")


if __name__ == "__main__":
    app()

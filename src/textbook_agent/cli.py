"""Typer CLI — entry point for all textbook-agent commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
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


# ─────────────────────────────────────────────────────────────── helpers ──────

def _resolve_project_dir(slug: str) -> Path:
    """Return the project directory for a given slug."""
    return Path(settings.output_dir) / slug


def _require_project(slug: str) -> tuple[Path, ProjectStorage]:
    project_dir = _resolve_project_dir(slug)
    if not (project_dir / "state.json").exists():
        console.print(
            f"[red]Project '{slug}' not found.[/red] "
            f"Run [bold]textbook-agent init --slug {slug}[/bold] first."
        )
        raise typer.Exit(1)
    return project_dir, ProjectStorage(project_dir)


def _run(action: str, project_dir: Path, slug: str, **kwargs) -> None:
    """Run a graph action with a Rich spinner."""
    from .graph import run_action

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(description=f"Running [bold]{action}[/bold]…", total=None)
        result = run_action(action, project_dir, slug, **kwargs)

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


# ──────────────────────────────────────────────────────────── commands ────────

@app.command()
def init(
    title: str = typer.Option(..., "--title", "-t", help="Textbook title"),
    slug: str = typer.Option(..., "--slug", "-s", help="Short project identifier (no spaces)"),
    info: str = typer.Option("", "--info", "-i", help="Brief description of the textbook"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Override output directory"),
) -> None:
    """Create a new textbook project."""
    if output_dir:
        settings.output_dir = output_dir

    project_dir = _resolve_project_dir(slug)

    if (project_dir / "state.json").exists():
        console.print(f"[yellow]Project '{slug}' already exists at {project_dir}[/yellow]")
        raise typer.Exit(0)

    project_dir.mkdir(parents=True, exist_ok=True)
    storage = ProjectStorage(project_dir)
    state = storage.init_project(slug=slug, title=title, info=info)

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
) -> None:
    """Generate clarification questions (saves 01_questions.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("01_questions.md"):
        console.print("[yellow]01_questions.md already exists. Delete it to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("ask", project_dir, slug)
    console.print(
        f"[green]✓[/green] Questions saved to [bold]{project_dir}/01_questions.md[/bold]\n"
        f"Fill in [bold]{project_dir}/01_answers.md[/bold], then run: "
        f"[bold]textbook-agent brief {slug}[/bold]"
    )


@app.command()
def brief(
    slug: str = typer.Argument(..., help="Project slug"),
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

    if storage.exists("02_book_brief.md"):
        console.print("[yellow]02_book_brief.md already exists. Delete it to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("brief", project_dir, slug)
    console.print(f"[green]✓[/green] Brief saved to [bold]{project_dir}/02_book_brief.md[/bold]")


@app.command()
def plan(
    slug: str = typer.Argument(..., help="Project slug"),
) -> None:
    """Generate overall writing plan (saves 03_plan.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("03_plan.md"):
        console.print("[yellow]03_plan.md already exists. Delete it to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("plan", project_dir, slug)
    console.print(f"[green]✓[/green] Plan saved to [bold]{project_dir}/03_plan.md[/bold]")


@app.command()
def toc(
    slug: str = typer.Argument(..., help="Project slug"),
) -> None:
    """Generate table of contents (saves 04_toc.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("04_toc.md"):
        console.print("[yellow]04_toc.md already exists. Delete it to regenerate.[/yellow]")
        raise typer.Exit(0)

    _run("toc", project_dir, slug)
    console.print(f"[green]✓[/green] TOC saved to [bold]{project_dir}/04_toc.md[/bold]")


@app.command()
def style(
    slug: str = typer.Argument(..., help="Project slug"),
) -> None:
    """Generate style guide and glossary (saves style_guide.md + glossary.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if storage.exists("style_guide.md") and storage.exists("glossary.md"):
        console.print("[yellow]style_guide.md and glossary.md already exist.[/yellow]")
        raise typer.Exit(0)

    _run("style", project_dir, slug)
    console.print(
        f"[green]✓[/green] Saved [bold]style_guide.md[/bold] and [bold]glossary.md[/bold] "
        f"to {project_dir}"
    )


@app.command()
def outline(
    slug: str = typer.Argument(..., help="Project slug"),
    chapter: Optional[int] = typer.Option(None, "--chapter", "-c", help="Generate outline for one chapter"),
    all_chapters: bool = typer.Option(False, "--all", "-a", help="Generate outlines for all chapters"),
) -> None:
    """Generate chapter outline(s) (saves outlines/chXX_outline.md)."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

    if not storage.exists("04_toc.md"):
        console.print("[red]04_toc.md not found.[/red] Run [bold]textbook-agent toc[/bold] first.")
        raise typer.Exit(1)

    _run("outline", project_dir, slug, chapter=chapter, all_chapters=all_chapters or chapter is None)
    console.print(f"[green]✓[/green] Outline(s) saved to [bold]{project_dir}/outlines/[/bold]")


@app.command()
def write(
    slug: str = typer.Argument(..., help="Project slug"),
    chapter: Optional[int] = typer.Option(None, "--chapter", "-c", help="Write sections for one chapter"),
    section: Optional[int] = typer.Option(None, "--section", "-s", help="Write one specific section"),
    all_chapters: bool = typer.Option(False, "--all", "-a", help="Write all chapters"),
) -> None:
    """Write section content (saves sections/chXX/secXX_YY.md)."""
    _check_api_key()

    if section is not None and chapter is None:
        console.print("[red]--section requires --chapter.[/red] Use: textbook-agent write SLUG --chapter N --section M")
        raise typer.Exit(1)

    project_dir, storage = _require_project(slug)

    if not storage.exists("style_guide.md"):
        console.print("[red]style_guide.md not found.[/red] Run [bold]textbook-agent style[/bold] first.")
        raise typer.Exit(1)

    _run(
        "write",
        project_dir,
        slug,
        chapter=chapter,
        section=section,
        all_chapters=all_chapters or (chapter is None and section is None),
    )
    console.print(f"[green]✓[/green] Section(s) saved to [bold]{project_dir}/sections/[/bold]")


@app.command()
def assemble(
    slug: str = typer.Argument(..., help="Project slug"),
) -> None:
    """Assemble all sections into final/textbook.md."""
    _check_api_key()
    project_dir, storage = _require_project(slug)

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
    state = storage.load_state()

    # Header
    console.print(
        Panel(
            f"[bold]{state.title}[/bold]  [dim](slug: {state.slug})[/dim]\n"
            f"Current stage: [cyan]{state.stage.value}[/cyan]",
            title="Project Status",
            expand=False,
        )
    )

    # Pipeline stages
    stage_table = Table(title="Pipeline Stages", show_header=True)
    stage_table.add_column("Stage", style="bold")
    stage_table.add_column("Status")
    stage_table.add_column("File")

    stage_files = {
        WorkflowStage.ask: "01_questions.md",
        WorkflowStage.brief: "02_book_brief.md",
        WorkflowStage.plan: "03_plan.md",
        WorkflowStage.toc: "04_toc.md",
        WorkflowStage.style: "style_guide.md",
        WorkflowStage.outlines: "outlines/",
        WorkflowStage.write: "sections/",
        WorkflowStage.assemble: "final/textbook.md",
    }

    for stage, file_hint in stage_files.items():
        done = state.is_stage_done(stage)
        status_str = "[green]✓ done[/green]" if done else "[yellow]pending[/yellow]"
        stage_table.add_row(stage.value, status_str, file_hint)

    console.print(stage_table)

    # Chapter details (if any)
    if state.chapters:
        ch_table = Table(title="Chapter Progress", show_header=True)
        ch_table.add_column("Chapter", style="bold")
        ch_table.add_column("Outline")
        ch_table.add_column("Sections Written")
        ch_table.add_column("Total Sections")

        for ch_id, ch_state in sorted(state.chapters.items()):
            outline_str = "[green]✓[/green]" if ch_state.outline_done else "[dim]–[/dim]"
            done_secs = sum(
                1 for s in ch_state.sections.values() if s.status.value in ("done", "reviewed")
            )
            total_secs = len(ch_state.sections)
            ch_table.add_row(
                f"{ch_id}: {ch_state.title}",
                outline_str,
                str(done_secs),
                str(total_secs),
            )

        console.print(ch_table)


@app.command()
def resume(
    slug: str = typer.Argument(..., help="Project slug"),
) -> None:
    """Resume from the last incomplete step."""
    _check_api_key()
    project_dir, storage = _require_project(slug)
    state = storage.load_state()

    # Determine what the next action should be
    next_action = _next_action(storage, state)
    if next_action == "_awaiting_answers":
        # Message already printed inside _next_action; exit without misleading "all done"
        raise typer.Exit(0)
    if next_action is None:
        console.print("[green]✓[/green] All steps are complete. Nothing to resume.")
        raise typer.Exit(0)

    console.print(f"Resuming at step: [bold]{next_action}[/bold]")
    _run(next_action, project_dir, slug, all_chapters=True)
    console.print(f"[green]✓[/green] Step [bold]{next_action}[/bold] complete.")


def _next_action(storage: ProjectStorage, state) -> Optional[str]:
    """Infer the next incomplete action from file existence.

    Returns an action string, None (all done), or '_awaiting_answers' (blocked on user input).
    """
    if not storage.exists("01_questions.md"):
        return "ask"
    if not storage.exists("01_answers.md"):
        console.print(
            f"[yellow]Waiting for your answers.[/yellow] "
            f"Create [bold]{storage.root}/01_answers.md[/bold] "
            f"with responses to the questions in 01_questions.md, then run resume again."
        )
        return "_awaiting_answers"
    if not storage.exists("02_book_brief.md"):
        return "brief"
    if not storage.exists("03_plan.md"):
        return "plan"
    if not storage.exists("04_toc.md"):
        return "toc"
    if not storage.exists("style_guide.md") or not storage.exists("glossary.md"):
        return "style"
    # Check if all outlines exist
    from .parser import parse_toc
    toc_entries = parse_toc(storage.read_md("04_toc.md"))
    for entry in toc_entries:
        if not storage.exists(storage.outline_path(entry.chapter_num)):
            return "outline"
    # Check sections
    for entry in toc_entries:
        from .parser import parse_outline
        outline_md = storage.read_md(storage.outline_path(entry.chapter_num))
        sec_infos = parse_outline(outline_md, entry.chapter_num, entry.title)
        for si in sec_infos:
            if not storage.exists(storage.section_path(entry.chapter_num, si.section_num)):
                return "write"
    if not storage.exists("final/textbook.md"):
        return "assemble"
    return None


if __name__ == "__main__":
    app()

"""Minimal i18n for CLI user-facing strings.

Language is selected via TEXTBOOK_LANG env var or the lang setting in .env.
Supported values: "zh" (default, Chinese) | "en" (English).
"""

from __future__ import annotations

import os
from typing import Any

# Resolved at import time so --help strings (evaluated at decoration) also pick
# up the correct language.  Reading settings here is safe because config.py has
# no dependency on i18n.py (no circular import).
def _detect_lang() -> str:
    explicit = os.environ.get("TEXTBOOK_LANG", "").strip().lower()
    if explicit in ("zh", "en"):
        return explicit
    try:
        from .config import settings
        return (settings.lang or "zh").lower()
    except Exception:
        return "zh"


_lang: str = _detect_lang()


# ── String table ──────────────────────────────────────────────────────────────
# Keys use named {placeholders} for runtime substitution via t(key, **kwargs).

_S: dict[str, dict[str, str]] = {

    # ── Built-in Click / Typer panel titles ───────────────────────────────
    "help_option": {
        "zh": "显示此帮助信息并退出。",
        "en": "Show this message and exit.",
    },
    "panel_options": {
        "zh": "选项",
        "en": "Options",
    },
    "panel_arguments": {
        "zh": "参数",
        "en": "Arguments",
    },
    "panel_commands": {
        "zh": "命令",
        "en": "Commands",
    },
    "panel_errors": {
        "zh": "错误",
        "en": "Error",
    },

    # ── Help panels ───────────────────────────────────────────────────────
    "panel_project":  {"zh": "项目管理",   "en": "Project Management"},
    "panel_pipeline": {"zh": "流水线步骤", "en": "Pipeline Steps"},
    "panel_export":   {"zh": "导出",       "en": "Export"},
    "panel_tools":    {"zh": "工具",       "en": "Tools"},
    "panel_llm":      {"zh": "LLM 选项",   "en": "LLM Options"},
    "panel_scope":    {"zh": "目标范围",   "en": "Scope"},

    # ── App ───────────────────────────────────────────────────────────────
    "app_help": {
        "zh": "AI 辅助教材编写工具。",
        "en": "AI-powered textbook writing assistant.",
    },

    # ── Common option help ─────────────────────────────────────────────────
    "opt_slug": {
        "zh": "项目标识符（slug）",
        "en": "Project slug",
    },
    "opt_force": {
        "zh": "即使输出已存在也重新生成",
        "en": "Regenerate even if output exists",
    },
    "opt_model": {
        "zh": "覆盖 LLM 模型",
        "en": "Override LLM model",
    },
    "opt_effort": {
        "zh": "覆盖 reasoning_effort",
        "en": "Override reasoning_effort",
    },
    "opt_temperature": {
        "zh": "覆盖 temperature",
        "en": "Override temperature",
    },
    "opt_yes": {
        "zh": "跳过确认提示",
        "en": "Skip confirmation prompt",
    },
    "opt_dry_run": {
        "zh": "仅预览，不调用 LLM",
        "en": "Show what would run without calling LLM",
    },

    # ── Helpers ────────────────────────────────────────────────────────────
    "invalid_slug": {
        "zh": "[red]无效的 slug：[/red] '{slug}'\nSlug 只能包含字母、数字、连字符（-）和下划线（_）。",
        "en": "[red]Invalid slug:[/red] '{slug}'\nSlug may only contain letters, digits, hyphens (-) and underscores (_).",
    },
    "project_not_found": {
        "zh": "[red]项目 '{slug}' 不存在。[/red] 请先运行 [bold]textbook-agent init --slug {slug}[/bold]。",
        "en": "[red]Project '{slug}' not found.[/red] Run [bold]textbook-agent init --slug {slug}[/bold] first.",
    },
    "api_key_missing": {
        "zh": "[red]未设置 LLM_API_KEY。[/red]\n请将 [bold].env.example[/bold] 复制为 [bold].env[/bold] 并填入 API 密钥。",
        "en": "[red]LLM_API_KEY is not set.[/red]\nCopy [bold].env.example[/bold] to [bold].env[/bold] and fill in your key.",
    },
    "run_spinner": {
        "zh": "正在运行 [bold]{action}[/bold]…",
        "en": "Running [bold]{action}[/bold]…",
    },
    "run_error": {
        "zh": "[red]错误：[/red] {error}",
        "en": "[red]Error:[/red] {error}",
    },

    # ── rename ─────────────────────────────────────────────────────────────
    "cmd_rename": {
        "zh": "重命名项目：移动目录并更新状态文件中的 slug。",
        "en": "Rename a project: moves its directory and updates slug in state files.",
    },
    "rename_opt_old": {
        "zh": "当前项目 slug",
        "en": "Current project slug",
    },
    "rename_opt_new": {
        "zh": "新项目 slug",
        "en": "New project slug",
    },
    "rename_not_found": {
        "zh": "[red]项目 '{old_slug}' 不存在。[/red]",
        "en": "[red]Project '{old_slug}' not found.[/red]",
    },
    "rename_exists": {
        "zh": "[red]'{new_slug}' 已存在于 {new_dir}。[/red]",
        "en": "[red]'{new_slug}' already exists at {new_dir}.[/red]",
    },
    "rename_checkpoint_note": {
        "zh": "，已更新 {n} 条 checkpoint 记录",
        "en": ", {n} checkpoint row(s) updated",
    },
    "rename_success": {
        "zh": "[green]✓[/green] 已将 [bold]{old_slug}[/bold] 重命名为 [bold]{new_slug}[/bold]\n  目录：{new_dir}{note}",
        "en": "[green]✓[/green] Renamed [bold]{old_slug}[/bold] → [bold]{new_slug}[/bold]\n  Directory: {new_dir}{note}",
    },

    # ── init ───────────────────────────────────────────────────────────────
    "cmd_init": {
        "zh": "创建新教材项目。",
        "en": "Create a new textbook project.",
    },
    "init_opt_title": {
        "zh": "教材标题",
        "en": "Textbook title",
    },
    "init_opt_slug": {
        "zh": "项目短标识符（不含空格）",
        "en": "Short project identifier (no spaces)",
    },
    "init_opt_info": {
        "zh": "教材简要说明",
        "en": "Brief description of the textbook",
    },
    "init_opt_output_dir": {
        "zh": "覆盖输出目录",
        "en": "Override output directory",
    },
    "init_exists": {
        "zh": "[yellow]项目 '{slug}' 已存在于 {project_dir}[/yellow]",
        "en": "[yellow]Project '{slug}' already exists at {project_dir}[/yellow]",
    },
    "init_panel_body": {
        "zh": (
            "[green]项目已创建！[/green]\n\n"
            "  [bold]标题：[/bold]  {title}\n"
            "  [bold]Slug：[/bold]   {slug}\n"
            "  [bold]目录：[/bold]    {project_dir}\n\n"
            "下一步：[bold]textbook-agent ask {slug}[/bold]"
        ),
        "en": (
            "[green]Project created![/green]\n\n"
            "  [bold]Title:[/bold]  {title}\n"
            "  [bold]Slug:[/bold]   {slug}\n"
            "  [bold]Dir:[/bold]    {project_dir}\n\n"
            "Next step: [bold]textbook-agent ask {slug}[/bold]"
        ),
    },

    # ── ask ────────────────────────────────────────────────────────────────
    "cmd_ask": {
        "zh": "生成调研问卷（保存为 01_questions.md）。",
        "en": "Generate clarification questions (saves 01_questions.md).",
    },
    "ask_exists": {
        "zh": "[yellow]01_questions.md 已存在。使用 --force 重新生成。[/yellow]",
        "en": "[yellow]01_questions.md already exists. Use --force to regenerate.[/yellow]",
    },
    "ask_success": {
        "zh": (
            "[green]✓[/green] 问卷已保存至 [bold]{project_dir}/01_questions.md[/bold]\n"
            "请在该文件的每个 [bold]你的答案：[/bold] 字段中填写答案，"
            "然后运行：[bold]textbook-agent brief {slug}[/bold]"
        ),
        "en": (
            "[green]✓[/green] Questions saved to [bold]{project_dir}/01_questions.md[/bold]\n"
            "Fill in each [bold]你的答案：[/bold] field in that file, "
            "then run: [bold]textbook-agent brief {slug}[/bold]"
        ),
    },

    # ── brief ──────────────────────────────────────────────────────────────
    "cmd_brief": {
        "zh": "根据问卷答案生成教材规格说明书（保存为 02_book_brief.md）。",
        "en": "Generate book brief from user input + filled questionnaire (saves 02_book_brief.md).",
    },
    "brief_no_questions": {
        "zh": "[red]未找到 01_questions.md。[/red] 请先运行 [bold]textbook-agent ask {slug}[/bold]。",
        "en": "[red]01_questions.md not found.[/red] Run [bold]textbook-agent ask {slug}[/bold] first.",
    },
    "brief_not_filled": {
        "zh": (
            "[yellow]请先在 [bold]{project_dir}/01_questions.md[/bold] 中填写答案"
            "（在每个「你的答案：」后面填写内容），然后重新运行此命令。[/yellow]"
        ),
        "en": (
            "[yellow]Please fill in [bold]{project_dir}/01_questions.md[/bold] first "
            "(add your answer after each '你的答案：' field), then re-run this command.[/yellow]"
        ),
    },
    "brief_exists": {
        "zh": "[yellow]02_book_brief.md 已存在。使用 --force 重新生成。[/yellow]",
        "en": "[yellow]02_book_brief.md already exists. Use --force to regenerate.[/yellow]",
    },
    "brief_success": {
        "zh": "[green]✓[/green] 规格说明书已保存至 [bold]{project_dir}/02_book_brief.md[/bold]",
        "en": "[green]✓[/green] Brief saved to [bold]{project_dir}/02_book_brief.md[/bold]",
    },

    # ── plan ───────────────────────────────────────────────────────────────
    "cmd_plan": {
        "zh": "生成整体写作计划（保存为 03_plan.md）。",
        "en": "Generate overall writing plan (saves 03_plan.md).",
    },
    "plan_exists": {
        "zh": "[yellow]03_plan.md 已存在。使用 --force 重新生成。[/yellow]",
        "en": "[yellow]03_plan.md already exists. Use --force to regenerate.[/yellow]",
    },
    "plan_success": {
        "zh": "[green]✓[/green] 写作计划已保存至 [bold]{project_dir}/03_plan.md[/bold]",
        "en": "[green]✓[/green] Plan saved to [bold]{project_dir}/03_plan.md[/bold]",
    },

    # ── toc ────────────────────────────────────────────────────────────────
    "cmd_toc": {
        "zh": "生成目录（保存为 04_toc.md）。",
        "en": "Generate table of contents (saves 04_toc.md).",
    },
    "toc_exists": {
        "zh": "[yellow]04_toc.md 已存在。使用 --force 重新生成。[/yellow]",
        "en": "[yellow]04_toc.md already exists. Use --force to regenerate.[/yellow]",
    },
    "toc_success": {
        "zh": "[green]✓[/green] 目录已保存至 [bold]{project_dir}/04_toc.md[/bold]",
        "en": "[green]✓[/green] TOC saved to [bold]{project_dir}/04_toc.md[/bold]",
    },

    # ── style ──────────────────────────────────────────────────────────────
    "cmd_style": {
        "zh": "生成写作风格规范和术语表（保存为 style_guide.md + glossary.md）。",
        "en": "Generate style guide and glossary (saves style_guide.md + glossary.md).",
    },
    "style_exists": {
        "zh": "[yellow]style_guide.md 和 glossary.md 已存在。使用 --force 重新生成。[/yellow]",
        "en": "[yellow]style_guide.md and glossary.md already exist. Use --force to regenerate.[/yellow]",
    },
    "style_success": {
        "zh": "[green]✓[/green] 已保存 [bold]style_guide.md[/bold] 和 [bold]glossary.md[/bold] 至 {project_dir}",
        "en": "[green]✓[/green] Saved [bold]style_guide.md[/bold] and [bold]glossary.md[/bold] to {project_dir}",
    },

    # ── outline ────────────────────────────────────────────────────────────
    "cmd_outline": {
        "zh": "生成章节大纲（保存为 outlines/chXX_outline.md）。",
        "en": "Generate chapter outline(s) (saves outlines/chXX_outline.md).",
    },
    "outline_opt_chapter": {
        "zh": "仅生成指定章节的大纲",
        "en": "Generate outline for one chapter",
    },
    "outline_opt_all": {
        "zh": "生成所有章节的大纲",
        "en": "Generate outlines for all chapters",
    },
    "no_toc": {
        "zh": "[red]未找到 04_toc.md。[/red] 请先运行 [bold]textbook-agent toc[/bold]。",
        "en": "[red]04_toc.md not found.[/red] Run [bold]textbook-agent toc[/bold] first.",
    },
    "outline_success": {
        "zh": "[green]✓[/green] 大纲已保存至 [bold]{project_dir}/outlines/[/bold]",
        "en": "[green]✓[/green] Outline(s) saved to [bold]{project_dir}/outlines/[/bold]",
    },

    # ── concept_map ────────────────────────────────────────────────────────
    "cmd_concept_map": {
        "zh": "从所有章节大纲生成概念地图（并行写作的前置步骤）。",
        "en": "Generate concept_map.md from all chapter outlines (prerequisite for parallel write).",
    },
    "concept_map_exists": {
        "zh": "[yellow]concept_map.md 已存在。使用 --force 重新生成。[/yellow]",
        "en": "[yellow]concept_map.md already exists. Use --force to regenerate.[/yellow]",
    },
    "concept_map_success": {
        "zh": "[green]✓[/green] 概念地图已保存至 [bold]{project_dir}/concept_map.md[/bold]",
        "en": "[green]✓[/green] Concept map saved to [bold]{project_dir}/concept_map.md[/bold]",
    },

    # ── write ──────────────────────────────────────────────────────────────
    "cmd_write": {
        "zh": "编写小节正文（保存为 sections/chXX/secXX_YY.md）。",
        "en": "Write section content (saves sections/chXX/secXX_YY.md).",
    },
    "write_opt_section": {
        "zh": "仅编写指定小节（需同时指定 --chapter）",
        "en": "Write one specific section (requires --chapter)",
    },
    "write_opt_all": {
        "zh": "编写所有章节",
        "en": "Write all chapters",
    },
    "write_section_needs_chapter": {
        "zh": "[red]--section 需要同时指定 --chapter。[/red] 用法：textbook-agent write SLUG --chapter N --section M",
        "en": "[red]--section requires --chapter.[/red] Use: textbook-agent write SLUG --chapter N --section M",
    },
    "write_no_style": {
        "zh": "[red]未找到 style_guide.md。[/red] 请先运行 [bold]textbook-agent style[/bold]。",
        "en": "[red]style_guide.md not found.[/red] Run [bold]textbook-agent style[/bold] first.",
    },
    "write_dryrun_header": {
        "zh": "[bold]预览 — 将要编写的小节：[/bold]",
        "en": "[bold]Dry-run — sections that would be written:[/bold]",
    },
    "write_dryrun_empty": {
        "zh": "  [green]无需生成（所有小节已存在）。[/green]",
        "en": "  [green]Nothing to generate (all sections already exist).[/green]",
    },
    "write_dryrun_summary": {
        "zh": "\n[dim]{pending} 个待生成，{done} 个已完成，共 {total} 个[/dim]",
        "en": "\n[dim]{pending} pending, {done} already done, {total} total in scope[/dim]",
    },
    "write_all_exist": {
        "zh": "[green]✓[/green] 范围内所有小节已存在。使用 [bold]--force[/bold] 可重新生成。",
        "en": "[green]✓[/green] All sections in scope already exist. Use [bold]--force[/bold] to regenerate.",
    },
    "write_confirm_header": {
        "zh": "[bold]即将生成 {pending} 个小节[/bold]（{done} 个已完成，共 {total} 个）：\n",
        "en": "[bold]About to generate {pending} section(s)[/bold] ({done} already done, {total} total):\n",
    },
    "write_confirm_more": {
        "zh": "  [dim]... 还有 {n} 个[/dim]",
        "en": "  [dim]... and {n} more[/dim]",
    },
    "write_confirm_prompt": {
        "zh": "继续？",
        "en": "Proceed?",
    },
    "write_aborted": {
        "zh": "[yellow]已取消。[/yellow]",
        "en": "[yellow]Aborted.[/yellow]",
    },
    "write_success": {
        "zh": "[green]✓[/green] 小节已保存至 [bold]{project_dir}/sections/[/bold]",
        "en": "[green]✓[/green] Section(s) saved to [bold]{project_dir}/sections/[/bold]",
    },

    # ── assemble ───────────────────────────────────────────────────────────
    "cmd_assemble": {
        "zh": "将所有小节合并为 final/textbook.md。",
        "en": "Assemble all sections into final/textbook.md.",
    },
    "assemble_opt_force": {
        "zh": "即使 final/textbook.md 已存在也重新合并",
        "en": "Reassemble even if final/textbook.md exists",
    },
    "assemble_exists": {
        "zh": "[yellow]final/textbook.md 已存在。使用 --force 重新合并。[/yellow]",
        "en": "[yellow]final/textbook.md already exists. Use --force to reassemble.[/yellow]",
    },
    "assemble_spinner": {
        "zh": "正在合并教材…",
        "en": "Assembling textbook…",
    },
    "assemble_success": {
        "zh": "[green]✓[/green] 最终教材已保存至 [bold]{output_path}[/bold]（{size_kb} KB）",
        "en": "[green]✓[/green] Final textbook saved to [bold]{output_path}[/bold] ({size_kb} KB)",
    },

    # ── export ─────────────────────────────────────────────────────────────
    "cmd_export": {
        "zh": (
            "将 final/textbook.md 导出为 PDF / HTML。\n\n"
            "PDF 需要额外依赖：\n"
            "  pip install 'textbook-agent[export]'\n"
            "  python -m playwright install chromium"
        ),
        "en": (
            "Export final/textbook.md to PDF and/or HTML.\n\n"
            "PDF requires extra dependencies:\n"
            "  pip install 'textbook-agent[export]'\n"
            "  python -m playwright install chromium"
        ),
    },
    "export_opt_format": {
        "zh": "导出格式：pdf | html | all（默认：pdf）",
        "en": "Export format: pdf | html | all (default: pdf)",
    },
    "export_opt_output": {
        "zh": "输出目录（默认：output/{slug}/final/）",
        "en": "Output directory (default: output/{slug}/final/)",
    },
    "export_bad_format": {
        "zh": "[red]--format 必须是：[/red] {choices}",
        "en": "[red]--format must be one of:[/red] {choices}",
    },
    "export_no_md": {
        "zh": "[red]找不到 {md_path}。[/red]\n请先运行：[bold]textbook-agent assemble {slug}[/bold]",
        "en": "[red]{md_path} not found.[/red]\nRun [bold]textbook-agent assemble {slug}[/bold] first.",
    },
    "export_html_success": {
        "zh": "[green]✓[/green] HTML 已保存至 [bold]{html_path}[/bold]（{size_kb} KB）",
        "en": "[green]✓[/green] HTML saved to [bold]{html_path}[/bold] ({size_kb} KB)",
    },
    "export_pdf_spinner": {
        "zh": "正在生成 PDF…",
        "en": "Generating PDF…",
    },
    "export_pdf_error": {
        "zh": "[red]PDF 导出失败：[/red]\n{error}",
        "en": "[red]PDF export failed:[/red]\n{error}",
    },
    "export_pdf_success": {
        "zh": "[green]✓[/green] PDF 已保存至 [bold]{pdf_path}[/bold]（{size_kb} KB）",
        "en": "[green]✓[/green] PDF saved to [bold]{pdf_path}[/bold] ({size_kb} KB)",
    },

    # ── status ─────────────────────────────────────────────────────────────
    "cmd_status": {
        "zh": "显示当前项目的生成进度。",
        "en": "Show current project generation progress.",
    },
    "status_stage_unknown": {
        "zh": "未知",
        "en": "unknown",
    },
    "status_panel_title": {
        "zh": "项目状态",
        "en": "Project Status",
    },
    "status_panel_body": {
        "zh": (
            "[bold]{title}[/bold]  [dim](slug: {slug})[/dim]\n"
            "当前阶段：  [cyan]{stage}[/cyan]\n\n"
            "大纲：       {outline_info}\n"
            "小节：       {section_info}\n"
            "最终文件：  {final_str}\n"
            "最近日志：  [dim]{last_log_str}[/dim]"
        ),
        "en": (
            "[bold]{title}[/bold]  [dim](slug: {slug})[/dim]\n"
            "Current stage:  [cyan]{stage}[/cyan]\n\n"
            "Outlines:       {outline_info}\n"
            "Sections:       {section_info}\n"
            "Final book:     {final_str}\n"
            "Last LLM log:   [dim]{last_log_str}[/dim]"
        ),
    },
    "status_unknown_toc": {
        "zh": "[dim]未知（缺少目录文件）[/dim]",
        "en": "[dim]unknown (toc missing)[/dim]",
    },
    "status_unknown_outline": {
        "zh": "[dim]未知（缺少大纲文件）[/dim]",
        "en": "[dim]unknown (outlines missing)[/dim]",
    },
    "status_ch_count": {
        "zh": "{done}/{total} 章",
        "en": "{done}/{total} chapters",
    },
    "status_sec_count": {
        "zh": "{written} 已写 / {total} 共（[yellow]{pending} 待写[/yellow]）",
        "en": "{written} written / {total} total ([yellow]{pending} pending[/yellow])",
    },
    "status_final_exists": {
        "zh": "[green]✓[/green] 已存在（{size_kb} KB）",
        "en": "[green]✓[/green] exists ({size_kb} KB)",
    },
    "status_final_missing": {
        "zh": "[dim]尚未合并[/dim]",
        "en": "[dim]not assembled yet[/dim]",
    },
    "status_last_log_none": {
        "zh": "无",
        "en": "none",
    },
    "status_checklist_title": {
        "zh": "文件清单",
        "en": "Artifact Checklist",
    },
    "status_col_file": {
        "zh": "文件",
        "en": "File",
    },
    "status_col_status": {
        "zh": "状态",
        "en": "Status",
    },
    "status_artifact_brief": {
        "zh": "教材规格说明书",
        "en": "Book brief",
    },
    "status_artifact_plan": {
        "zh": "写作计划",
        "en": "Writing plan",
    },
    "status_artifact_toc": {
        "zh": "目录",
        "en": "Table of contents",
    },
    "status_artifact_style": {
        "zh": "写作风格规范",
        "en": "Style guide",
    },
    "status_artifact_glossary": {
        "zh": "术语表",
        "en": "Glossary",
    },
    "status_file_exists": {
        "zh": "[green]✓ 已存在[/green]",
        "en": "[green]✓ exists[/green]",
    },
    "status_file_pending": {
        "zh": "[yellow]待生成[/yellow]",
        "en": "[yellow]pending[/yellow]",
    },
    "status_ch_table_title": {
        "zh": "章节进度",
        "en": "Chapter Progress",
    },
    "status_col_chapter": {
        "zh": "章节",
        "en": "Chapter",
    },
    "status_col_outline": {
        "zh": "大纲",
        "en": "Outline",
    },
    "status_col_written": {
        "zh": "已写",
        "en": "Written",
    },
    "status_col_total": {
        "zh": "总计",
        "en": "Total",
    },

    # ── lang ──────────────────────────────────────────────────────────────
    "cmd_lang": {
        "zh": "切换 CLI 显示语言并写入 .env（下次运行生效）。",
        "en": "Switch the CLI display language and persist to .env (takes effect on next run).",
    },
    "lang_opt": {
        "zh": "目标语言：zh（中文）| en（英文）",
        "en": "Target language: zh (Chinese) | en (English)",
    },
    "lang_invalid": {
        "zh": "[red]无效的语言：[/red] 可选值为 {choices}",
        "en": "[red]Invalid language:[/red] must be one of {choices}",
    },
    "lang_set": {
        "zh": "[green]✓[/green] 语言已切换为 [bold]{language}[/bold]，已写入 [dim]{env_path}[/dim]\n[dim]重新运行命令后生效。[/dim]",
        "en": "[green]✓[/green] Language set to [bold]{language}[/bold], written to [dim]{env_path}[/dim]\n[dim]Takes effect on next invocation.[/dim]",
    },

    # ── Cascade invalidation ──────────────────────────────────────────────
    "cascade_cleared": {
        "zh": "[dim]已清除下游文件（{step} 重新生成后失效）：{items}[/dim]",
        "en": "[dim]Downstream files invalidated after re-running {step}: {items}[/dim]",
    },
    "cascade_hint": {
        "zh": "[dim]运行 [bold]textbook-agent resume {slug} --yes[/bold] 继续补全。[/dim]",
        "en": "[dim]Run [bold]textbook-agent resume {slug} --yes[/bold] to regenerate.[/dim]",
    },

    # ── resume ─────────────────────────────────────────────────────────────
    "cmd_resume": {
        "zh": (
            "显示下一个待执行步骤（默认）或继续执行（--yes）。\n\n"
            "示例：\n"
            "  textbook-agent resume my-book              # 仅显示下一步\n"
            "  textbook-agent resume my-book --yes        # 执行所有待完成步骤\n"
            "  textbook-agent resume my-book --until toc --yes\n"
            "  textbook-agent resume my-book --dry-run"
        ),
        "en": (
            "Show next pending step (default) or resume execution (--yes).\n\n"
            "Examples:\n"
            "  textbook-agent resume my-book              # show next step only\n"
            "  textbook-agent resume my-book --yes        # run all pending steps\n"
            "  textbook-agent resume my-book --until toc --yes\n"
            "  textbook-agent resume my-book --dry-run"
        ),
    },
    "resume_opt_yes": {
        "zh": "执行所有待完成步骤（默认：仅显示）",
        "en": "Execute the pending steps (default: show only)",
    },
    "resume_opt_until": {
        "zh": "在此步骤后停止。可选值：{choices}",
        "en": "Stop after this step. Choices: {choices}",
    },
    "resume_opt_dry_run": {
        "zh": "仅预览待执行步骤，不运行",
        "en": "Show pending steps without running anything",
    },
    "resume_opt_force": {
        "zh": "即使输出文件已存在也重新生成",
        "en": "Regenerate even if output files exist",
    },
    "resume_bad_until": {
        "zh": "[red]--until 必须是以下之一：[/red] {choices}",
        "en": "[red]--until must be one of:[/red] {choices}",
    },
    "resume_waiting": {
        "zh": (
            "[yellow]等待填写问卷。[/yellow]\n"
            "请在 [bold]{root}/01_questions.md[/bold] 的每个「你的答案：」字段中填写答案，"
            "然后重新运行 resume。"
        ),
        "en": (
            "[yellow]Waiting for questionnaire answers.[/yellow]\n"
            "Fill in each '你的答案：' field in [bold]{root}/01_questions.md[/bold], "
            "then re-run resume."
        ),
    },
    "resume_all_done": {
        "zh": "[green]✓[/green] 所有步骤已完成。无需继续。",
        "en": "[green]✓[/green] All steps are complete. Nothing to resume.",
    },
    "resume_until_done": {
        "zh": "[green]✓[/green] [bold]{until}[/bold] 之前的所有步骤已完成。",
        "en": "[green]✓[/green] All steps up to [bold]{until}[/bold] are complete.",
    },
    "resume_stop_label": {
        "zh": "  [dim]停止于：{until}[/dim]",
        "en": "  [dim]Stop at: {until}[/dim]",
    },
    "resume_exec_label_all": {
        "zh": "将执行：",
        "en": "Will run:",
    },
    "resume_exec_label_one": {
        "zh": "下一个待执行步骤：",
        "en": "Next pending step:",
    },
    "resume_dryrun_note": {
        "zh": "\n[dim]（预览模式 — 未调用 LLM）[/dim]",
        "en": "\n[dim](dry-run — no LLM calls made)[/dim]",
    },
    "resume_hint": {
        "zh": "\n[dim]使用 [bold]--yes[/bold] 执行。使用 [bold]--until STEP[/bold] 设置停止点。[/dim]",
        "en": "\n[dim]Run with [bold]--yes[/bold] to execute. Add [bold]--until STEP[/bold] to set a stopping point.[/dim]",
    },
    "resume_running": {
        "zh": "\n[bold cyan]▶ 正在运行：{step}[/bold cyan]",
        "en": "\n[bold cyan]▶ Running: {step}[/bold cyan]",
    },
    "resume_step_done": {
        "zh": "[green]✓[/green] {step} 完成。",
        "en": "[green]✓[/green] {step} complete.",
    },
    "resume_done": {
        "zh": "\n[green]✓[/green] 已全部完成。",
        "en": "\n[green]✓[/green] Resume complete.",
    },
}


# ── Public API ────────────────────────────────────────────────────────────────

def t(key: str, **kwargs: Any) -> str:
    """Return the localized string for *key*, formatted with *kwargs*."""
    entry = _S.get(key, {})
    s = entry.get(_lang) or entry.get("en") or key
    return s.format(**kwargs) if kwargs else s


# ── Patch Click's built-in --help text ────────────────────────────────────────
# Click 8.1.8+ caches the help option lazily per command via _help_option.
# Patching click.decorators.help_option before any command is invoked ensures
# every command picks up the translated text on first use.
def _patch_builtins() -> None:
    # 1. Click's --help option text
    try:
        import click.decorators as _cd
        _orig = _cd.help_option

        def _translated_help(*param_decls: str, **kwargs: Any) -> Any:
            kwargs.setdefault("help", t("help_option"))
            return _orig(*param_decls, **kwargs)

        _cd.help_option = _translated_help
    except Exception:
        pass

    # 2. Typer's rich panel titles (Options / Arguments / Commands / Error)
    try:
        import typer.rich_utils as _ru
        _ru.OPTIONS_PANEL_TITLE   = t("panel_options")
        _ru.ARGUMENTS_PANEL_TITLE = t("panel_arguments")
        _ru.COMMANDS_PANEL_TITLE  = t("panel_commands")
        _ru.ERRORS_PANEL_TITLE    = t("panel_errors")
    except Exception:
        pass

_patch_builtins()

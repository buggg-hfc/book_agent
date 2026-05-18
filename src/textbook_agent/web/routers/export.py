"""Export endpoints — serve finished textbook as HTML or PDF."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...config import settings

router = APIRouter(prefix="/api/projects", tags=["export"])


@router.post("/{slug}/export")
def export_project(slug: str, format: str = "html"):
    project_dir = Path(settings.output_dir) / slug
    md_path = project_dir / "final" / "textbook.md"

    if not md_path.exists():
        raise HTTPException(
            404,
            "final/textbook.md not found — run the assemble step first",
        )

    if format == "html":
        out_path = project_dir / "final" / "textbook.html"
        try:
            from ...exporter import export_html
        except ImportError as exc:
            raise HTTPException(422, f"HTML export dependency missing: {exc}") from exc
        export_html(md_path, out_path)
        return FileResponse(
            str(out_path),
            media_type="text/html",
            filename=f"{slug}.html",
        )

    if format == "pdf":
        out_path = project_dir / "final" / "textbook.pdf"
        try:
            from ...exporter import export_pdf
        except ImportError as exc:
            raise HTTPException(
                422,
                "PDF export requires optional deps: "
                "pip install 'textbook-agent[export]' && playwright install chromium",
            ) from exc
        try:
            export_pdf(md_path, out_path)
        except Exception as exc:
            raise HTTPException(500, f"PDF export failed: {exc}") from exc
        return FileResponse(
            str(out_path),
            media_type="application/pdf",
            filename=f"{slug}.pdf",
        )

    raise HTTPException(422, f"Unknown format '{format}' — use 'html' or 'pdf'")

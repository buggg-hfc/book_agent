"""File tree, read, and write endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...config import settings
from ..schemas import FileContent, FileTreeNode, FileWrite

router = APIRouter(prefix="/api/projects/{slug}/files", tags=["files"])

_TEXT_EXTS = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".html", ".css", ".js"}
_MAX_READ_BYTES = 2 * 1024 * 1024  # 2 MB


def _project_root(slug: str) -> Path:
    return (Path(settings.output_dir) / slug).resolve()


def _safe_path(slug: str, rel: str) -> Path:
    root = _project_root(slug)
    if not root.exists():
        raise HTTPException(404, f"Project '{slug}' not found")
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(403, "Path traversal denied")
    return target


def _build_tree(path: Path, root: Path) -> FileTreeNode:
    rel = str(path.relative_to(root))
    if path.is_dir():
        children = sorted(
            (_build_tree(c, root) for c in path.iterdir()),
            key=lambda n: (n.type == "file", n.name),
        )
        return FileTreeNode(name=path.name, path=rel, type="dir", children=children)
    return FileTreeNode(name=path.name, path=rel, type="file", size_bytes=path.stat().st_size)


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=FileTreeNode)
def file_tree(slug: str):
    root = _project_root(slug)
    if not root.exists():
        raise HTTPException(404, f"Project '{slug}' not found")
    # Exclude the SQLite checkpoint DB from the tree.
    tree = _build_tree(root, root)
    if tree.children:
        tree.children = [c for c in tree.children if not c.name.endswith(".db")]
    return tree


@router.get("/{path:path}", response_model=FileContent)
def read_file(slug: str, path: str):
    target = _safe_path(slug, path)
    if not target.exists():
        raise HTTPException(404, f"File '{path}' not found")
    if target.is_dir():
        raise HTTPException(400, "Path is a directory")
    size = target.stat().st_size
    if size > _MAX_READ_BYTES:
        raise HTTPException(413, "File too large to read via API")
    if target.suffix.lower() not in _TEXT_EXTS:
        raise HTTPException(415, "Binary file — use /download endpoint")
    content = target.read_text(encoding="utf-8", errors="replace")
    return FileContent(path=path, content=content, size_bytes=size)


@router.put("/{path:path}", response_model=FileContent)
def write_file(slug: str, path: str, body: FileWrite):
    target = _safe_path(slug, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return FileContent(path=path, content=body.content, size_bytes=len(body.content.encode()))


@router.get("/{path:path}/download")
def download_file(slug: str, path: str):
    target = _safe_path(slug, path)
    if not target.exists() or target.is_dir():
        raise HTTPException(404)
    return FileResponse(str(target), filename=target.name)

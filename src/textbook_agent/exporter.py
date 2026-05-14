"""Export assembled textbook Markdown to PDF via weasyprint.

Install optional deps:  pip install 'textbook-agent[export]'
On headless servers weasyprint needs:
  sudo apt-get install -y libpangocairo-1.0-0 libcairo2
"""

from __future__ import annotations

import re
from pathlib import Path

# ── CSS template ──────────────────────────────────────────────────────────────

CSS_TEMPLATE = """
@page {
    size: A4;
    margin: 25mm 30mm 25mm 30mm;
    @bottom-center {
        content: counter(page);
        font-family: "WenQuanYi Zen Hei", sans-serif;
        font-size: 9pt;
        color: #888;
    }
}
@page :first {
    @bottom-center { content: ""; }
}

body {
    font-family: "WenQuanYi Zen Hei", "文泉驿正黑", serif;
    font-size: 11pt;
    line-height: 1.9;
    color: #1a1a1a;
    text-align: justify;
    hyphens: none;
}

h1 {
    font-size: 24pt;
    font-weight: bold;
    text-align: center;
    margin: 60pt 0 40pt 0;
    padding-bottom: 12pt;
    border-bottom: 3px solid #2c3e50;
    page-break-after: always;
}

h2 {
    font-size: 18pt;
    font-weight: bold;
    margin-top: 0;
    padding: 16pt 0 8pt 0;
    border-bottom: 2px solid #3498db;
    page-break-before: always;
    color: #2c3e50;
}

h3 {
    font-size: 14pt;
    font-weight: bold;
    margin-top: 20pt;
    margin-bottom: 8pt;
    border-left: 4px solid #3498db;
    padding-left: 8pt;
    color: #34495e;
}

h4 { font-size: 12pt; font-weight: bold; margin-top: 14pt; }
h5 { font-size: 11pt; font-weight: bold; margin-top: 10pt; }

p { margin: 0 0 8pt 0; orphans: 3; widows: 3; }

pre {
    background: #f8f8f8;
    border: 1px solid #ddd;
    border-left: 4px solid #3498db;
    border-radius: 3px;
    padding: 10pt 12pt;
    font-size: 9pt;
    line-height: 1.5;
    page-break-inside: avoid;
    white-space: pre-wrap;
    word-break: break-all;
}

code {
    font-family: "WenQuanYi Zen Hei Mono", "文泉驿等宽正黑", monospace;
    font-size: 9pt;
}

p code, li code {
    background: #f0f0f0;
    border: 1px solid #ddd;
    border-radius: 2px;
    padding: 1pt 3pt;
    font-size: 9.5pt;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 12pt 0;
    font-size: 10pt;
    page-break-inside: avoid;
}

th {
    background: #2c3e50;
    color: #fff;
    padding: 7pt 10pt;
    text-align: left;
    font-weight: bold;
}

td {
    padding: 6pt 10pt;
    border-bottom: 1px solid #ddd;
    vertical-align: top;
}

tr:nth-child(even) td { background: #f5f5f5; }
tr:nth-child(odd) td  { background: #ffffff; }

blockquote {
    border-left: 4px solid #bdc3c7;
    margin: 10pt 0 10pt 20pt;
    padding: 6pt 12pt;
    background: #f9f9f9;
    color: #555;
    font-style: italic;
}

ul, ol { margin: 0 0 8pt 0; padding-left: 20pt; }
li { margin-bottom: 4pt; }

strong { font-weight: bold; }
em     { font-style: italic; }
a      { color: #2563eb; }

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 16pt 0;
}
"""

# ── Markdown → HTML ───────────────────────────────────────────────────────────

def _make_html(md_text: str) -> str:
    """Convert Markdown to a complete HTML document with syntax-highlighted code."""
    from markdown_it import MarkdownIt
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_by_name
    from pygments.util import ClassNotFound

    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    body_html = md.render(md_text)

    # Post-process: replace <pre><code class="language-LANG">…</code></pre>
    # with pygments-highlighted HTML (inline styles, no external CSS needed).
    formatter = HtmlFormatter(style="friendly", noclasses=True)

    def _highlight_block(match: re.Match) -> str:
        lang = match.group(1) or ""
        code = match.group(2)
        # markdown-it HTML-escapes content inside <code>; restore before highlighting
        code = (
            code.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&#39;", "'")
        )
        try:
            lexer = get_lexer_by_name(lang) if lang else TextLexer()
        except ClassNotFound:
            lexer = TextLexer()
        return highlight(code, lexer, formatter)

    body_html = re.sub(
        r'<pre><code class="language-([^"]*)">(.*?)</code></pre>',
        _highlight_block,
        body_html,
        flags=re.DOTALL,
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<style>
{CSS_TEMPLATE}
</style>
</head>
<body>
{body_html}
</body>
</html>"""


# ── PDF export ────────────────────────────────────────────────────────────────

def export_pdf(md_path: Path, out_path: Path) -> None:
    """Render Markdown → HTML → PDF via weasyprint."""
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            "weasyprint 未安装。请运行：pip install weasyprint\n"
            "或：pip install 'textbook-agent[export]'"
        )

    md_text = md_path.read_text(encoding="utf-8")
    html_str = _make_html(md_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str, base_url=str(md_path.parent)).write_pdf(str(out_path))

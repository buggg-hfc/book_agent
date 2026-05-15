"""Export assembled textbook Markdown to PDF via Playwright (Chromium).

Install optional deps:
  pip install playwright
  playwright install chromium
Or via the package extra:
  pip install 'textbook-agent[export]'
  playwright install chromium
"""

from __future__ import annotations

import re
from pathlib import Path

# ── CSS template ──────────────────────────────────────────────────────────────
# Margins and page numbers are handled by Playwright's pdf() options,
# so no @page margin-box rules are needed here.

CSS_TEMPLATE = """
body {
    font-family: "Microsoft YaHei", "微软雅黑",
                 "WenQuanYi Zen Hei", "文泉驿正黑",
                 "PingFang SC", "苹方", "Hiragino Sans GB",
                 STSong, SimSun, serif;
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
    break-after: page;
}

h2 {
    font-size: 18pt;
    font-weight: bold;
    margin-top: 0;
    padding: 16pt 0 8pt 0;
    border-bottom: 2px solid #3498db;
    break-before: page;
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
    break-inside: avoid;
    white-space: pre-wrap;
    word-break: break-all;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
}

code {
    font-family: "Cascadia Code", Consolas, "Source Code Pro",
                 "WenQuanYi Zen Hei Mono", "文泉驿等宽正黑", monospace;
    font-size: 9pt;
}

p code, li code {
    background: #f0f0f0;
    border: 1px solid #ddd;
    border-radius: 2px;
    padding: 1pt 3pt;
    font-size: 9.5pt;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 12pt 0;
    font-size: 10pt;
    break-inside: avoid;
}

th {
    background: #2c3e50;
    color: #fff;
    padding: 7pt 10pt;
    text-align: left;
    font-weight: bold;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
}

td {
    padding: 6pt 10pt;
    border-bottom: 1px solid #ddd;
    vertical-align: top;
}

tr:nth-child(even) td {
    background: #f5f5f5;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
}

blockquote {
    border-left: 4px solid #bdc3c7;
    margin: 10pt 0 10pt 20pt;
    padding: 6pt 12pt;
    background: #f9f9f9;
    color: #555;
    font-style: italic;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
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

/* Pygments code highlight blocks */
.highlight {
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
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

# Footer template rendered by Chromium inside the bottom margin area.
# Font and color are inline-styled because footer templates are isolated
# from the page stylesheet.
_FOOTER_TEMPLATE = (
    '<div style="'
    'font-family:\'Microsoft YaHei\',\'WenQuanYi Zen Hei\',sans-serif;'
    'font-size:9pt;color:#888;'
    'width:100%;text-align:center;'
    '">'
    '<span class="pageNumber"></span>'
    '</div>'
)


def export_html(md_path: Path, out_path: Path) -> None:
    """Save Markdown rendered as a self-contained HTML file."""
    html_str = _make_html(md_path.read_text(encoding="utf-8"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_str, encoding="utf-8")


def export_pdf(md_path: Path, out_path: Path) -> None:
    """Render Markdown → HTML → PDF via Playwright (Chromium)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "playwright 未安装。请运行：\n"
            "  pip install playwright\n"
            "  playwright install chromium\n"
            "或通过 extra 安装：\n"
            "  pip install 'textbook-agent[export]'\n"
            "  playwright install chromium"
        )

    html_str = _make_html(md_path.read_text(encoding="utf-8"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                raise RuntimeError(
                    "Playwright Chromium 未下载。请运行：\n"
                    "  python -m playwright install chromium"
                ) from e
            raise
        page = browser.new_page()
        page.set_content(html_str, wait_until="load")
        page.pdf(
            path=str(out_path),
            format="A4",
            margin={"top": "25mm", "bottom": "20mm",
                    "left": "30mm", "right": "30mm"},
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=_FOOTER_TEMPLATE,
        )
        browser.close()

"""
Report export utilities: Markdown → HTML and HTML → PDF conversion.
"""

import html as html_lib

import markdown as markdown_lib

_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem;
    color: #1a1a1a;
    line-height: 1.7;
}
h1 {
    font-size: 2rem;
    border-bottom: 2px solid #333;
    padding-bottom: .5rem;
    margin-top: 2rem;
}
h2 {
    font-size: 1.5rem;
    border-bottom: 1px solid #ccc;
    padding-bottom: .3rem;
    margin-top: 1.8rem;
}
h3 { font-size: 1.2rem; margin-top: 1.5rem; }
h4, h5, h6 { margin-top: 1.2rem; }
code {
    background: #f4f4f4;
    padding: .15em .4em;
    border-radius: 3px;
    font-size: .92em;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
pre {
    background: #f4f4f4;
    padding: 1rem;
    border-radius: 4px;
    overflow-x: auto;
    line-height: 1.45;
}
pre code {
    background: none;
    padding: 0;
    font-size: .9em;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1rem 0;
}
th, td {
    border: 1px solid #ddd;
    padding: .6rem 1rem;
    text-align: left;
}
th {
    background: #f0f0f0;
    font-weight: 600;
}
tr:nth-child(even) { background: #fafafa; }
blockquote {
    border-left: 4px solid #ccc;
    margin: 1rem 0;
    padding: .5rem 1rem;
    color: #555;
    background: #fafafa;
}
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid #ddd; margin: 2rem 0; }
img { max-width: 100%; height: auto; }
.toc { background: #f8f8f8; border: 1px solid #ddd; padding: 1rem 1.5rem; border-radius: 4px; margin-bottom: 2rem; }
.toc ul { margin: 0; padding-left: 1.2rem; }
@media print {
    body { padding: 1rem; max-width: none; }
    pre { white-space: pre-wrap; word-break: break-all; }
}
"""


def markdown_to_html(md_content: str, title: str = "MiroFish Report") -> str:
    """Convert a Markdown string to a full standalone HTML document with embedded CSS."""
    md = markdown_lib.Markdown(extensions=["tables", "fenced_code", "toc"])
    body = md.convert(md_content)
    safe_title = html_lib.escape(title)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{safe_title}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        f"<body>\n{body}\n</body>\n"
        "</html>"
    )


def html_to_pdf(html_content: str) -> bytes:
    """Convert an HTML string to PDF bytes using WeasyPrint."""
    from weasyprint import HTML  # imported lazily to avoid startup cost

    return HTML(string=html_content).write_pdf()

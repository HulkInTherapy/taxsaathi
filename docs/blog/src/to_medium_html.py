"""Convert the blog Markdown into Medium-friendly HTML (paste into the editor).
Images point at the public GitHub copy so Medium can import them."""
import html
import re
import sys
from pathlib import Path

RAW = "https://raw.githubusercontent.com/Champion1102/taxot/main/docs/blog/"


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def convert(md: str, skip: set[str]) -> str:
    out, lst, first_h1, first_h3 = [], None, True, True
    def close():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>"); lst = None
    for line in md.splitlines():
        if not line.strip():
            close(); continue
        if m := re.match(r"!\[[^\]]*\]\(([^)]+)\)", line):
            close()
            if Path(m.group(1)).name not in skip:
                out.append(f'<figure><img src="{RAW}{m.group(1)}"></figure>')
            continue
        if line.startswith("# "):
            close(); out.append(f"<h3>{inline(line[2:])}</h3>"); continue
        if line.startswith("### ") and first_h3:
            close(); out.append(f"<h4>{inline(line[4:])}</h4>"); first_h3 = False; continue
        if line.startswith("## "):
            close(); out.append(f"<h3>{inline(line[3:])}</h3>"); continue
        if line.startswith("### "):
            close(); out.append(f"<h4>{inline(line[4:])}</h4>"); continue
        if line.strip() == "---":
            close(); out.append("<hr>"); continue
        if line.startswith("> "):
            close(); out.append(f"<blockquote>{inline(line[2:])}</blockquote>"); continue
        if m := re.match(r"(\d+)\.\s+(.*)", line):
            if lst != "ol": close(); out.append("<ol>"); lst = "ol"
            out.append(f"<li>{inline(m.group(2))}</li>"); continue
        if line.startswith("- "):
            if lst != "ul": close(); out.append("<ul>"); lst = "ul"
            out.append(f"<li>{inline(line[2:])}</li>"); continue
        close(); out.append(f"<p>{inline(line)}</p>")
    close()
    return "".join(out)


if __name__ == "__main__":
    src = Path(__file__).resolve().parent.parent / "taxot-agents.md"
    print(convert(src.read_text(), set(sys.argv[1:])))

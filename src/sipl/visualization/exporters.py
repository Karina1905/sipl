from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

from .tree_view import TreeView


def to_text(root: TreeView, source: str | None = None, show_spans: bool = True) -> str:
    lines: list[str] = []

    def label(n: TreeView) -> str:
        text = n.label.replace("\n", " ")
        if n.edge_label:
            text = f"{n.edge_label}: {text}"
        if show_spans:
            text += f"  [{n.span}]"
        if source is not None and n.role != "terminal" and n.children:
            frag = " ".join(source[n.span.start:n.span.end].split())
            if len(frag) > 40:
                frag = frag[:37] + "..."
            text += f"  «{frag}»"
        return text

    def rec(n: TreeView, prefix: str, last: bool, is_root: bool) -> None:
        if is_root:
            lines.append(label(n))
            child_prefix = ""
        else:
            lines.append(prefix + ("└── " if last else "├── ") + label(n))
            child_prefix = prefix + ("    " if last else "│   ")
        for i, c in enumerate(n.children):
            rec(c, child_prefix, i == len(n.children) - 1, False)

    rec(root, "", True, True)
    return "\n".join(lines)


def to_json(root: TreeView, indent: int | None = 2) -> str:
    return json.dumps(root.to_dict(), ensure_ascii=False, indent=indent)


_DOT_STYLE = {
    "nonterminal": 'shape=ellipse, style=filled, fillcolor="#e8eefc", color="#5470c6"',
    "terminal": 'shape=box, style="rounded,filled", fillcolor="#fff4d6", color="#c79a1e"',
    "program": 'shape=box, style="filled", fillcolor="#e3e3e3"',
    "stmt": 'shape=box, style="rounded,filled", fillcolor="#e8eefc", color="#5470c6"',
    "aexp": 'shape=ellipse, style=filled, fillcolor="#e6f6ea", color="#3a9a5b"',
    "bexp": 'shape=ellipse, style=filled, fillcolor="#fde8e8", color="#c0504d"',
}


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_dot(root: TreeView, name: str = "tree") -> str:
    out = [f'digraph "{_dot_escape(name)}" {{',
           '  node [fontname="Helvetica", fontsize=11];',
           '  edge [fontname="Helvetica", fontsize=9, color="#777777"];',
           "  ordering=out;"]
    for n in root.walk():
        tooltip = f"{n.span}"
        out.append(f'  n{n.id} [label="{_dot_escape(n.label)}", tooltip="{tooltip}", '
                   f'{_DOT_STYLE[n.role]}];')
    for n in root.walk():
        for c in n.children:
            attr = f' [label="{_dot_escape(c.edge_label)}"]' if c.edge_label else ""
            out.append(f"  n{n.id} -> n{c.id}{attr};")
    out.append("}")
    return "\n".join(out) + "\n"


_SVG_COLORS = {
    "nonterminal": ("#e8eefc", "#5470c6"), "terminal": ("#fff4d6", "#c79a1e"),
    "program": ("#e3e3e3", "#777777"), "stmt": ("#e8eefc", "#5470c6"),
    "aexp": ("#e6f6ea", "#3a9a5b"), "bexp": ("#fde8e8", "#c0504d"),
}
CHAR_W = 7.2
LINE_H = 15
H_GAP = 14
LEVEL_H = 70
PAD = 20


@dataclass
class _Box:
    node: TreeView
    w: float
    h: float
    subtree_w: float = 0.0
    x: float = 0.0
    y: float = 0.0
    kids: list[_Box] | None = None


def _measure(n: TreeView) -> _Box:
    lines = n.label.split("\n")
    w = max(len(s) for s in lines) * CHAR_W + 18
    h = len(lines) * LINE_H + 10
    box = _Box(n, w, h, kids=[_measure(c) for c in n.children])
    assert box.kids is not None
    kids_w = sum(k.subtree_w for k in box.kids) + H_GAP * max(0, len(box.kids) - 1)
    box.subtree_w = max(w, kids_w)
    return box


def _place(box: _Box, left: float, depth: int) -> None:
    box.y = PAD + depth * LEVEL_H
    assert box.kids is not None
    kids_w = sum(k.subtree_w for k in box.kids) + H_GAP * max(0, len(box.kids) - 1)
    cur = left + (box.subtree_w - kids_w) / 2
    for k in box.kids:
        _place(k, cur, depth + 1)
        cur += k.subtree_w + H_GAP
    if box.kids:
        centre = (box.kids[0].x + box.kids[-1].x) / 2
        lo, hi = left + box.w / 2, left + box.subtree_w - box.w / 2
        box.x = min(max(centre, lo), hi)
    else:
        box.x = left + box.subtree_w / 2


def _all(box: _Box):
    yield box
    for k in box.kids or []:
        yield from _all(k)


def _tooltip(node: TreeView, source: str | None) -> str:
    text = f"{node.label.replace(chr(10), ' ')} [{node.span}]"
    if source is not None and node.id >= 0:
        fragment = " ".join(source[node.span.start:node.span.end].split())
        text += f"\n{fragment}"
    return text


def to_svg(root: TreeView, title: str = "", source: str | None = None) -> str:
    top = _measure(root)
    _place(top, PAD, 0)
    boxes = list(_all(top))
    width = top.subtree_w + 2 * PAD
    height = max(b.y + b.h for b in boxes) + PAD
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" preserveAspectRatio="xMidYMin meet" '
        f'font-family="Helvetica, Arial, sans-serif" font-size="12">',
        f"<title>{escape(title)}</title>",
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for b in boxes:
        for k in b.kids or []:
            y1, y2 = b.y + b.h, k.y
            my = y1 + (y2 - y1) / 2
            parts.append(f'<path d="M{b.x:.1f},{y1:.1f} V{my:.1f} H{k.x:.1f} V{y2:.1f}" '
                         f'fill="none" stroke="#7d8597" stroke-width="1"/>')
            if k.node.edge_label:
                parts.append(f'<text x="{k.x + 3:.1f}" y="{my + (y2 - my) / 2 + 3:.1f}" '
                             f'font-size="9" fill="#666">{escape(k.node.edge_label)}</text>')
    for b in boxes:
        fill, stroke = _SVG_COLORS[b.node.role]
        rx = 12 if b.node.role in ("nonterminal", "aexp", "bexp") else 4
        parts.append(
            f'<g data-node-id="{b.node.id}" data-span="{b.node.span.start}-{b.node.span.end}">'
            f"<title>{escape(_tooltip(b.node, source))}</title>"
            f'<rect x="{b.x - b.w / 2:.1f}" y="{b.y:.1f}" width="{b.w:.1f}" height="{b.h:.1f}" '
            f'rx="{rx}" fill="{fill}" stroke="{stroke}"/>'
        )
        for i, line in enumerate(b.node.label.split("\n")):
            ty = b.y + 5 + LINE_H * (i + 1) - 3
            weight = ' font-weight="bold"' if i == 0 and "\n" in b.node.label else ""
            parts.append(f'<text x="{b.x:.1f}" y="{ty:.1f}" text-anchor="middle"{weight}>'
                         f"{escape(line)}</text>")
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"

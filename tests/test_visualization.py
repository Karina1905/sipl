import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from sipl import parse_full
from sipl.visualization import (
    from_ast,
    from_parse_tree,
    to_dot,
    to_json,
    to_svg,
    to_text,
)

from .conftest import example

SRC = "begin if X > Y then M := X else M := (Y + 1) * 2 end"


@pytest.fixture
def res():
    return parse_full(SRC)


def test_parse_tree_view_matches_parse_tree(res):
    view = from_parse_tree(res.tree)
    assert [n.id for n in view.walk()] == [n.node_id for n in res.tree.walk()]
    terminals = [n.label for n in view.walk() if n.role == "terminal"]
    assert terminals[:4] == ["'begin'", "'if'", "X", "'>'"]
    nonterminals = {n.label for n in view.walk() if n.role == "nonterminal"}
    assert {"<program P>", "<if statement>", "<condition b>", "<arith expr a>"} <= nonterminals


def test_parse_tree_nodes_link_to_source(res):
    for n in from_parse_tree(res.tree).walk():
        frag = SRC[n.span.start:n.span.end]
        if n.role == "terminal":
            assert frag == n.label.strip("'")
        else:
            assert frag.strip() == frag and frag


def test_ast_view_is_smaller_and_has_edge_roles(res):
    pt = list(from_parse_tree(res.tree).walk())
    ast = list(from_ast(res.ast).walk())
    assert len(ast) < len(pt)
    edges = {n.edge_label for n in ast if n.edge_label}
    assert {"cond", "then", "else", "left", "right", "expr"} <= edges
    assert all(n.role != "terminal" for n in ast)


def test_text_export(res):
    text = to_text(from_parse_tree(res.tree), source=SRC)
    assert text.splitlines()[0].startswith("<program P>")
    assert "└── " in text and "«M := (Y + 1) * 2»" in text
    plain = to_text(from_ast(res.ast), show_spans=False)
    assert "[" not in plain and "cond: Compare >" in plain


def test_json_export(res):
    data = json.loads(to_json(from_ast(res.ast)))
    assert data["label"] == "Program" and data["children"][0]["edge"] == "body"
    assert data["span"]["start"] == 0


def test_dot_export(res):
    dot = to_dot(from_parse_tree(res.tree), "t")
    assert dot.startswith('digraph "t"')
    n_nodes = len(list(res.tree.walk()))
    assert dot.count("->") == n_nodes - 1


@pytest.mark.skipif(shutil.which("dot") is None, reason="graphviz not installed")
def test_dot_is_valid_graphviz(res):
    dot = to_dot(from_ast(res.ast))
    proc = subprocess.run(["dot", "-Tsvg"], input=dot, capture_output=True, text=True)
    assert proc.returncode == 0 and "<svg" in proc.stdout


@pytest.mark.parametrize("which", ["parse", "ast"])
def test_svg_is_well_formed_and_complete(res, which):
    view = from_parse_tree(res.tree) if which == "parse" else from_ast(res.ast)
    svg = to_svg(view, "t")
    root = ET.fromstring(svg)
    groups = root.findall(".//{http://www.w3.org/2000/svg}g")
    assert len(groups) == len(list(view.walk()))
    assert all(g.get("data-span") for g in groups)


def test_svg_nodes_do_not_overlap():
    res = parse_full(example("unicode_logic"))
    svg = to_svg(from_ast(res.ast))
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    rows: dict[float, list[tuple[float, float]]] = {}
    for rect in root.iter(f"{ns}rect"):
        if rect.get("rx") is None:
            continue
        x, w, y = float(rect.get("x")), float(rect.get("width")), float(rect.get("y"))
        rows.setdefault(y, []).append((x, x + w))
    for boxes in rows.values():
        boxes.sort()
        for (_, a1), (b0, _) in zip(boxes, boxes[1:], strict=False):
            assert a1 <= b0


def test_compact_parse_tree_keeps_tokens_and_drops_chains():
    from sipl.visualization import compact_parse_tree

    res = parse_full(example("power"))
    view = compact_parse_tree(res.tree)
    leaves = [n.label.strip("'") for n in view.walk() if n.role == "terminal"]
    assert leaves == res.tree.leaves()
    for n in view.walk():
        if n.role != "terminal" and len(n.children) == 1:
            assert n.children[0].role == "terminal", n.label
    full = len(list(from_parse_tree(res.tree).walk()))
    assert len(list(view.walk())) < full
    labels = {n.label for n in view.walk()}
    assert {"Program", "WhileStatement", "Assignment", "Variable", "Number"} <= labels


def test_compact_sequence_is_flattened():
    from sipl.visualization import compact_parse_tree

    view = compact_parse_tree(parse_full("begin A := 1; B := 2; C := 3 end").tree)
    seq = view.children[1]
    assert [c.label for c in seq.children] == ["Assignment", "';'", "Assignment", "';'",
                                               "Assignment"]


def test_combined_view_has_both_trees():
    from sipl.visualization import combined, compact_parse_tree

    res = parse_full(SRC)
    view = combined(compact_parse_tree(res.tree), from_ast(res.ast), "T")
    assert view.label == "T"
    assert [c.label for c in view.children] == ["Parse Tree", "AST"]
    assert all("\n" not in n.label for n in view.walk())
    root = ET.fromstring(to_svg(view))
    assert len(root.findall(".//{http://www.w3.org/2000/svg}g")) == len(list(view.walk()))


def test_bnf_rules_on_parse_tree():
    res = parse_full(example("unicode_logic"))
    rules = {n.rule for n in res.tree.walk() if n.rule}
    assert rules == {"P1", "S1", "S2", "S3", "S4", "S5", "A1", "A2", "A3", "A4", "B1", "B2",
                     "B3", "B4", "B5"}
    labels = [n.label for n in from_parse_tree(res.tree, rules=True).walk()]
    assert "<program P> [P1]" in labels and "<while statement> [S4]" in labels
    assert all("[" not in n.label for n in from_parse_tree(res.tree).walk())


def test_every_bnf_rule_is_recognised():
    src = "begin X := (1 + 2) * 3 - 4; if not (X = 1) or X > 2 then skip else begin skip end end"
    rules = {n.rule for n in parse_full(src).tree.walk() if n.rule}
    assert {"S1", "S2", "S3", "S5", "S6", "A1", "A2", "A3", "A4", "A5", "A6",
            "B1", "B2", "B3", "B4", "B5", "P1"} <= rules


def test_svg_tooltips_show_source_fragment(res):
    svg = to_svg(from_ast(res.ast), "t", SRC)
    root = ET.fromstring(svg)
    titles = [t.text for t in root.iter("{http://www.w3.org/2000/svg}title")]
    assert any(t.endswith("\nM := (Y + 1) * 2") for t in titles if t)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import ast as A
from ..diagnostics import SourceSpan
from ..parser import ParseNode


@dataclass
class TreeView:
    id: int
    label: str
    span: SourceSpan
    role: str
    children: list[TreeView] = field(default_factory=list)
    edge_label: str | None = None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id, "label": self.label, "role": self.role,
            "span": self.span.to_dict(),
        }
        if self.edge_label:
            data["edge"] = self.edge_label
        data["children"] = [c.to_dict() for c in self.children]
        return data


def _with_rule(label: str, node: ParseNode, rules: bool) -> str:
    return f"{label} [{node.rule}]" if rules and node.rule else label


def from_parse_tree(node: ParseNode, rules: bool = False) -> TreeView:
    return TreeView(
        id=node.node_id,
        label=_with_rule(node.label, node, rules),
        span=node.span,
        role="terminal" if node.is_terminal else "nonterminal",
        children=[from_parse_tree(c, rules) for c in node.children],
    )


_EDGE_FIELDS = {
    "Assign": ("expr",), "If": ("cond", "then_branch", "else_branch"),
    "While": ("cond", "body"), "Block": ("body",), "Program": ("body",),
    "BinOp": ("left", "right"), "BoolOp": ("left", "right"),
    "Compare": ("left", "right"), "Not": ("operand",),
}
_EDGE_NAMES = {"then_branch": "then", "else_branch": "else"}


def ast_label(node: A.Node) -> str:
    if isinstance(node, A.Assign):
        return f"{node.target} :="
    if isinstance(node, A.BoolOp):
        return "∨"
    if isinstance(node, (A.BinOp, A.Compare)):
        return node.op
    if isinstance(node, A.Num):
        return str(node.value)
    if isinstance(node, A.Var):
        return node.name
    if isinstance(node, A.Not):
        return "¬"
    if isinstance(node, A.Seq):
        return ";"
    return node.kind


def _ast_role(node: A.Node) -> str:
    if isinstance(node, A.Program):
        return "program"
    if isinstance(node, A.Stmt):
        return "stmt"
    if isinstance(node, A.AExpr):
        return "aexp"
    return "bexp"


def from_ast(node: A.Node, edge: str | None = None) -> TreeView:
    children: list[TreeView] = []
    if isinstance(node, A.Seq):
        children = [from_ast(s, f"S{i + 1}") for i, s in enumerate(node.statements)]
    else:
        for name in _EDGE_FIELDS.get(node.kind, ()):
            children.append(from_ast(getattr(node, name), _EDGE_NAMES.get(name, name)))
    return TreeView(
        id=node.node_id,
        label=f"{node.kind}\n{ast_label(node)}" if ast_label(node) != node.kind else node.kind,
        span=node.span,
        role=_ast_role(node),
        children=children,
        edge_label=edge,
    )


_COMPACT_NAMES = {
    "program": "Program", "seq": "Sequence", "assign": "Assignment",
    "if_stmt": "IfStatement", "while_stmt": "WhileStatement", "block": "Block", "skip_stmt": "Skip",
    "aexp": "ArithmeticExpression", "term": "ArithmeticExpression", "num": "Number",
    "bexp": "Condition", "bterm": "Condition", "bfactor": "Comparison",
}


def compact_parse_tree(node: ParseNode, rules: bool = False) -> TreeView:
    while not node.is_terminal and len(node.children) == 1 and not node.children[0].is_terminal:
        node = node.children[0]
    if node.is_terminal:
        return TreeView(node.node_id, node.label, node.span, "terminal")
    if node.symbol == "factor" and node.children[0].symbol == "NAME":
        leaf = node.children[0]
        return TreeView(node.node_id, _with_rule("Variable", node, rules), node.span, "nonterminal",
                        [TreeView(leaf.node_id, leaf.label, leaf.span, "terminal")])
    kids = node.children
    if node.symbol == "seq":
        flat: list[ParseNode] = []
        cur = node
        while cur.symbol == "seq" and len(cur.children) == 3:
            flat[:0] = cur.children[1:]
            cur = cur.children[0]
        kids = [cur, *flat]
    label = _COMPACT_NAMES.get(node.symbol, node.label)
    if node.symbol == "num" and rules:
        return TreeView(node.node_id, f"{label} [A1]", node.span, "nonterminal",
                        [compact_parse_tree(c, rules) for c in kids])
    if node.symbol == "bfactor" and len(kids) == 3 and kids[0].symbol == "LPAR":
        label = "Condition"
    return TreeView(node.node_id, _with_rule(label, node, rules), node.span, "nonterminal",
                    [compact_parse_tree(c, rules) for c in kids])


def _one_line(view: TreeView) -> TreeView:
    return TreeView(view.id, view.label.replace("\n", " "), view.span, view.role,
                    [_one_line(c) for c in view.children], view.edge_label)


def combined(parse_view: TreeView, ast_view: TreeView,
             title: str = "SIPL: Parse Tree ↔ AST") -> TreeView:
    span = parse_view.span
    return TreeView(-1, title, span, "program", [
        TreeView(-2, "Parse Tree", span, "program", [_one_line(parse_view)]),
        TreeView(-3, "AST", span, "program", [_one_line(ast_view)]),
    ])

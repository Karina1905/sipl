from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Iterator

from .diagnostics import SourceSpan

ARITH_OPS = ("+", "-", "*")
REL_OPS = ("=", ">")
BOOL_OPS = ("or",)


@dataclass(eq=False)
class Node:
    span: SourceSpan = field(repr=False, kw_only=True)
    node_id: int = field(default=-1, repr=False, kw_only=True)

    @property
    def kind(self) -> str:
        return type(self).__name__

    def children(self) -> Iterator[Node]:
        for f in fields(self):
            if f.name in ("span", "node_id"):
                continue
            value = getattr(self, f.name)
            if isinstance(value, Node):
                yield value
            elif isinstance(value, tuple):
                yield from (v for v in value if isinstance(v, Node))

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.children():
            yield from child.walk()

    def attributes(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):
            if f.name in ("span", "node_id"):
                continue
            value = getattr(self, f.name)
            if not isinstance(value, (Node, tuple)):
                out[f.name] = value
        return out

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.kind, "id": self.node_id}
        for f in fields(self):
            if f.name in ("span", "node_id"):
                continue
            value = getattr(self, f.name)
            if isinstance(value, Node):
                data[f.name] = value.to_dict()
            elif isinstance(value, tuple):
                data[f.name] = [v.to_dict() for v in value]
            else:
                data[f.name] = value
        data["span"] = self.span.to_dict()
        return data

    def structurally_equal(self, other: Node) -> bool:
        return _strip(self.to_dict()) == _strip(other.to_dict())


def _strip(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _strip(v) for k, v in data.items() if k not in ("span", "id")}
    if isinstance(data, list):
        return [_strip(v) for v in data]
    return data


@dataclass(eq=False)
class AExpr(Node):
    pass


@dataclass(eq=False)
class Num(AExpr):
    value: int


@dataclass(eq=False)
class Var(AExpr):
    name: str


@dataclass(eq=False)
class BinOp(AExpr):
    op: str
    left: AExpr
    right: AExpr


@dataclass(eq=False)
class BExpr(Node):
    pass


@dataclass(eq=False)
class Not(BExpr):
    operand: BExpr


@dataclass(eq=False)
class BoolOp(BExpr):
    op: str
    left: BExpr
    right: BExpr


@dataclass(eq=False)
class Compare(BExpr):
    op: str
    left: AExpr
    right: AExpr


@dataclass(eq=False)
class Stmt(Node):
    pass


@dataclass(eq=False)
class Assign(Stmt):
    target: str
    expr: AExpr


@dataclass(eq=False)
class Seq(Stmt):
    statements: tuple[Stmt, ...]


@dataclass(eq=False)
class If(Stmt):
    cond: BExpr
    then_branch: Stmt
    else_branch: Stmt


@dataclass(eq=False)
class While(Stmt):
    cond: BExpr
    body: Stmt


@dataclass(eq=False)
class Block(Stmt):
    body: Stmt


@dataclass(eq=False)
class Skip(Stmt):
    pass


@dataclass(eq=False)
class Program(Node):
    body: Stmt

    def number_nodes(self) -> Program:
        for i, node in enumerate(self.walk()):
            node.node_id = i
        return self

    def node_by_id(self, node_id: int) -> Node:
        for node in self.walk():
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def variables(self) -> list[str]:
        seen: dict[str, None] = {}
        for node in self.walk():
            if isinstance(node, Assign):
                seen.setdefault(node.target, None)
            elif isinstance(node, Var):
                seen.setdefault(node.name, None)
        return list(seen)


def from_dict(data: dict[str, Any]) -> Node:
    cls = _CLASSES[data["type"]]
    span = SourceSpan(**data["span"])
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name in ("span", "node_id"):
            continue
        value = data[f.name]
        if isinstance(value, dict):
            kwargs[f.name] = from_dict(value)
        elif isinstance(value, list):
            kwargs[f.name] = tuple(from_dict(v) for v in value)
        else:
            kwargs[f.name] = value
    return cls(**kwargs, span=span, node_id=data.get("id", -1))


_CLASSES: dict[str, type[Node]] = {
    c.__name__: c
    for c in (Num, Var, BinOp, Not, BoolOp, Compare,
              Assign, Seq, If, While, Block, Skip, Program)
}

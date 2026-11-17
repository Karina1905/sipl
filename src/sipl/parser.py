from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any, Iterator

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from . import ast as A
from .diagnostics import Diagnostic, SiplSyntaxError, SourceSpan

KEYWORDS = {
    "BEGIN": "begin", "END": "end", "IF": "if", "THEN": "then", "ELSE": "else",
    "WHILE": "while", "DO": "do", "SKIP": "skip", "OR": "or", "NOT": "not",
}
TERMINAL_NAMES = {
    **{k: f"'{v}'" for k, v in KEYWORDS.items()},
    "OR": "'or'/'∨'", "NOT": "'not'/'¬'",
    "ASSIGN": "':='", "SEMI": "';'", "LPAR": "'('", "RPAR": "')'", "PLUS": "'+'",
    "MINUS": "'-'", "STAR": "'*'", "EQ": "'='", "GT": "'>'",
    "NAME": "variable name", "NUMBER": "number", "$END": "end of file",
}

BNF_NAMES = {
    "program": "<program P>", "seq": "<sequence S>", "stmt": "<statement S>",
    "assign": "<assignment>", "if_stmt": "<if statement>", "while_stmt": "<while statement>",
    "block": "<block>", "skip_stmt": "<skip>", "aexp": "<arith expr a>", "term": "<term>",
    "factor": "<factor>", "num": "<number n>", "bexp": "<condition b>", "bterm": "<bool term>",
    "bfactor": "<bool factor>",
}

_NOT_IN_SIPL_CHARS = {
    "<": "SIPL has only '=' and '>' comparisons: write 'Y > X' instead of 'X < Y'",
    "/": "SIPL has no division; arithmetic is only '+', '-', '*'",
    "%": "SIPL has no remainder operator; arithmetic is only '+', '-', '*'",
    "!": "SIPL has no '!='; write 'not (a = b)'",
}
_NOT_IN_SIPL_WORDS = {
    "and": "SIPL has no 'and'; use 'not (not b1 or not b2)'",
    "true": "SIPL has no boolean literals; use a comparison, e.g. '0 = 0'",
    "false": "SIPL has no boolean literals; use a comparison, e.g. '0 > 0'",
}


_RULE_BY_SYMBOL = {
    "program": "P1", "assign": "S1", "if_stmt": "S3", "while_stmt": "S4",
    "block": "S5", "skip_stmt": "S6",
}
_RULE_BY_TOKEN = {
    ("seq", "SEMI"): "S2", ("aexp", "PLUS"): "A3", ("aexp", "MINUS"): "A4",
    ("term", "STAR"): "A5", ("factor", "num"): "A1", ("factor", "NAME"): "A2",
    ("factor", "LPAR"): "A6", ("bexp", "OR"): "B3", ("bterm", "NOT"): "B4",
    ("bfactor", "EQ"): "B1", ("bfactor", "GT"): "B2", ("bfactor", "LPAR"): "B5",
}


def bnf_rule(node: ParseNode) -> str | None:
    if node.is_terminal:
        return None
    if node.symbol in _RULE_BY_SYMBOL:
        return _RULE_BY_SYMBOL[node.symbol]
    for child in node.children:
        rule = _RULE_BY_TOKEN.get((node.symbol, child.symbol))
        if rule:
            return rule
    return None


@dataclass(eq=False)
class ParseNode:
    symbol: str
    span: SourceSpan
    children: list[ParseNode] = field(default_factory=list)
    text: str | None = None
    node_id: int = -1

    @property
    def is_terminal(self) -> bool:
        return self.text is not None

    @property
    def rule(self) -> str | None:
        return bnf_rule(self)

    @property
    def label(self) -> str:
        if self.is_terminal:
            return repr(self.text) if self.symbol not in ("NAME", "NUMBER") else str(self.text)
        return BNF_NAMES.get(self.symbol, self.symbol)

    def walk(self) -> Iterator[ParseNode]:
        yield self
        for c in self.children:
            yield from c.walk()

    def leaves(self) -> list[str]:
        return [n.text for n in self.walk() if n.text is not None]

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.node_id, "symbol": self.symbol, "label": self.label}
        if self.rule:
            data["rule"] = self.rule
        if self.is_terminal:
            data["text"] = self.text
        else:
            data["children"] = [c.to_dict() for c in self.children]
        data["span"] = self.span.to_dict()
        return data


@dataclass
class ParseResult:
    source: str
    tree: ParseNode
    ast: A.Program


@lru_cache(maxsize=1)
def _lark() -> Lark:
    grammar = resources.files("sipl").joinpath("grammar/sipl.lark").read_text(encoding="utf-8")
    return Lark(
        grammar,
        start="program",
        parser="lalr",
        keep_all_tokens=True,
        propagate_positions=True,
        maybe_placeholders=False,
        lexer="basic",
    )


def grammar_text() -> str:
    return resources.files("sipl").joinpath("grammar/sipl.lark").read_text(encoding="utf-8")


def parse_full(source: str) -> ParseResult:
    tree = parse_tree(source)
    program = _AstBuilder().build(tree)
    return ParseResult(source=source, tree=tree, ast=program)


def parse(source: str) -> A.Program:
    return parse_full(source).ast


def parse_tree(source: str) -> ParseNode:
    try:
        raw = _lark().parse(source)
    except UnexpectedInput as exc:
        raise SiplSyntaxError(_diagnostic_from_lark(exc, source)) from None
    node = _convert(raw, source)
    for i, n in enumerate(node.walk()):
        n.node_id = i
    return node


def check(source: str) -> list[Diagnostic]:
    try:
        parse(source)
    except SiplSyntaxError as exc:
        return [exc.diagnostic]
    return []


def _span_from_offsets(source: str, start: int, end: int) -> SourceSpan:
    line = source.count("\n", 0, start) + 1
    col = start - (source.rfind("\n", 0, start) + 1) + 1
    end_line = source.count("\n", 0, end) + 1
    end_col = end - (source.rfind("\n", 0, end) + 1) + 1
    return SourceSpan(line, col, end_line, end_col, start, end)


def _convert(item: Tree | Token, source: str) -> ParseNode:
    if isinstance(item, Token):
        assert item.start_pos is not None and item.end_pos is not None
        span = _span_from_offsets(source, item.start_pos, item.end_pos)
        return ParseNode(symbol=item.type, span=span, text=str(item))
    children = [_convert(c, source) for c in item.children]
    span = _span_from_offsets(source, children[0].span.start, children[-1].span.end)
    return ParseNode(symbol=str(item.data), span=span, children=children)


def _merge(a: SourceSpan, b: SourceSpan) -> SourceSpan:
    return SourceSpan(a.line, a.column, b.end_line, b.end_column, a.start, b.end)


class _AstBuilder:
    def build(self, tree: ParseNode) -> A.Program:
        body = self.seq(tree.children[1])
        return A.Program(body=body, span=tree.span).number_nodes()

    def seq(self, node: ParseNode) -> A.Stmt:
        stmts: list[A.Stmt] = []
        self._flatten_seq(node, stmts)
        if len(stmts) == 1:
            return stmts[0]
        return A.Seq(statements=tuple(stmts), span=node.span)

    def _flatten_seq(self, node: ParseNode, out: list[A.Stmt]) -> None:
        if len(node.children) == 1:
            out.append(self.stmt(node.children[0]))
        else:
            left, _semi, right = node.children
            self._flatten_seq(left, out)
            out.append(self.stmt(right))

    def stmt(self, node: ParseNode) -> A.Stmt:
        inner = node.children[0]
        c = inner.children
        span = inner.span
        if inner.symbol == "assign":
            return A.Assign(target=str(c[0].text), expr=self.aexp(c[2]), span=span)
        if inner.symbol == "if_stmt":
            return A.If(cond=self.bexp(c[1]), then_branch=self.seq(c[3]),
                        else_branch=self.stmt(c[5]), span=span)
        if inner.symbol == "while_stmt":
            return A.While(cond=self.bexp(c[1]), body=self.stmt(c[3]), span=span)
        if inner.symbol == "block":
            return A.Block(body=self.seq(c[1]), span=span)
        if inner.symbol == "skip_stmt":
            return A.Skip(span=span)
        raise AssertionError(inner.symbol)

    def aexp(self, node: ParseNode) -> A.AExpr:
        c = node.children
        if node.symbol == "factor":
            return self.factor(node)
        if len(c) == 1:
            return self.aexp(c[0])
        return A.BinOp(op=str(c[1].text), left=self.aexp(c[0]),
                       right=self.aexp(c[2]), span=node.span)

    def factor(self, node: ParseNode) -> A.AExpr:
        c = node.children
        if len(c) == 3:
            inner = self.aexp(c[1])
            inner.span = node.span
            return inner
        tok = c[0]
        if tok.symbol == "num":
            text = "".join(str(t.text) for t in tok.children)
            return A.Num(value=int(text), span=tok.span)
        return A.Var(name=str(tok.text), span=node.span)

    def bexp(self, node: ParseNode) -> A.BExpr:
        c = node.children
        if node.symbol == "bexp":
            if len(c) == 1:
                return self.bexp(c[0])
            return A.BoolOp(op="or", left=self.bexp(c[0]), right=self.bexp(c[2]),
                            span=node.span)
        if node.symbol == "bterm":
            if len(c) == 1:
                return self.bexp(c[0])
            return A.Not(operand=self.bexp(c[1]), span=node.span)
        if c[0].symbol == "LPAR":
            inner = self.bexp(c[1])
            inner.span = node.span
            return inner
        return A.Compare(op=str(c[1].text), left=self.aexp(c[0]), right=self.aexp(c[2]),
                         span=node.span)


def _diagnostic_from_lark(exc: UnexpectedInput, source: str) -> Diagnostic:
    pos = exc.pos_in_stream if exc.pos_in_stream is not None else len(source)
    if isinstance(exc, UnexpectedCharacters):
        ch = source[pos] if pos < len(source) else ""
        span = _span_from_offsets(source, pos, min(pos + 1, len(source)))
        hint = _NOT_IN_SIPL_CHARS.get(ch)
        if ch == ":":
            hint = "use ':=' for assignment"
        return Diagnostic("syntax_error", f"unexpected character {ch!r}", span, hint)

    assert isinstance(exc, UnexpectedToken)
    tok = exc.token
    raw_expected: set[str] = set(exc.expected)
    if exc.interactive_parser is not None:
        try:
            raw_expected = set(exc.interactive_parser.accepts()) or raw_expected
        except Exception:
            pass
    expected = sorted(TERMINAL_NAMES.get(e, e) for e in raw_expected)
    if tok.type == "$END":
        start = end = len(source.rstrip())
        span = _span_from_offsets(source, end, end)
        got = "end of file"
    else:
        start = tok.start_pos if tok.start_pos is not None else pos
        end = tok.end_pos if tok.end_pos is not None else start + len(str(tok))
        span = _span_from_offsets(source, start, end)
        got = f"'{tok}'"
    message = f"unexpected {got}; expected {', '.join(expected)}"
    before = source[:start].rstrip()
    return Diagnostic("syntax_error", message, span, _hint(tok, raw_expected, before),
                      extra={"expected": expected})


def _hint(tok: Token, expected: set[str], before: str) -> str | None:
    text = str(tok)
    if tok.type == "NAME" and text in _NOT_IN_SIPL_WORDS:
        return _NOT_IN_SIPL_WORDS[text]
    if not before and expected == {"BEGIN"}:
        return "a SIPL program has the form 'begin S end' (rule P1)"
    if expected == {"$END"}:
        return "the program ends with its final 'end'; remove the text after it"
    if tok.type == "EQ" and "ASSIGN" in expected:
        return "use ':=' for assignment, '=' is comparison"
    if before.endswith(";") and tok.type in ("END", "ELSE", "$END"):
        return "';' separates statements — remove the ';' before this word"
    prev_word = before.split()[-1] if before.split() else ""
    if prev_word in _NOT_IN_SIPL_WORDS:
        return _NOT_IN_SIPL_WORDS[prev_word]
    if tok.type == "ASSIGN" and prev_word in KEYWORDS.values():
        return f"'{prev_word}' is a reserved word and cannot be used as a variable name"
    if tok.type == "$END" and "END" in expected:
        return "a 'begin' is not closed with 'end'"
    if "ELSE" in expected:
        return "SIPL requires an else branch: 'if b then S1 else S2' (use 'else skip')"
    if tok.type == "NAME" and before.endswith("-") and expected == {"NUMBER"}:
        return "a minus sign is allowed only in numerals like -5; write '0 - x'"
    if tok.type in ("EQ", "GT") and not expected & {"EQ", "GT", "ASSIGN"}:
        return "a condition cannot be a value: only arithmetic expressions are assigned"
    if tok.type == "NAME" and "SEMI" in expected:
        return "missing ';' between statements?"
    if tok.type == "END" and before.endswith("begin"):
        return "a block cannot be empty; write 'begin skip end'"
    if "RPAR" in expected and tok.type != "RPAR":
        return "missing ')'?"
    if "DO" in expected:
        return "missing 'do': 'while b do S'"
    if "THEN" in expected:
        return "missing 'then': 'if b then S1 else S2'"
    if tok.type in ("THEN", "DO", "RPAR") and ("EQ" in expected or "GT" in expected):
        return "a condition needs a comparison, e.g. 'x > 0' or 'x = 0'"
    return None

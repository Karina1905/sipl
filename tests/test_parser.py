import json

import pytest

from sipl import SiplSyntaxError, parse, parse_full, parse_tree
from sipl import ast as A
from sipl.parser import ParseNode

from .conftest import example


def body(src: str) -> A.Stmt:
    return parse(src).body


def test_power_ast_shape():
    prog = parse(example("power"))
    assert isinstance(prog, A.Program)
    seq = prog.body
    assert isinstance(seq, A.Seq) and len(seq.statements) == 2
    assign, loop = seq.statements
    assert isinstance(assign, A.Assign) and assign.target == "R"
    assert isinstance(assign.expr, A.Num) and assign.expr.value == 1
    assert isinstance(loop, A.While)
    assert isinstance(loop.cond, A.Compare) and loop.cond.op == ">"
    assert isinstance(loop.body, A.Block)


def test_no_library_types_in_ast():
    for node in parse(example("power")).walk():
        assert type(node).__module__ == "sipl.ast"


def test_spans_point_to_source_text():
    src = "begin\n  X := 1;\n  while 10 > X do\n    X := X * 2\nend"
    prog = parse(src)
    loop = prog.body.statements[1]
    assert (loop.span.line, loop.span.column) == (3, 3)
    assert loop.span.text(src) == "while 10 > X do\n    X := X * 2"
    assert loop.cond.span.text(src) == "10 > X"
    assert (loop.body.span.line, loop.body.span.column, loop.body.span.end_column) == (4, 5, 15)
    assert loop.body.expr.span.text(src) == "X * 2"
    assert prog.span.text(src) == src


def test_parenthesised_span_includes_parentheses():
    src = "begin Y := (A + B) * C end"
    assert body(src).expr.left.span.text(src) == "(A + B)"


def _shape(e):
    if isinstance(e, A.Num):
        return e.value
    if isinstance(e, A.Var):
        return e.name
    return (e.op, _shape(e.left), _shape(e.right))


@pytest.mark.parametrize("expr,expected", [
    ("1 + 2 * 3", ("+", 1, ("*", 2, 3))),
    ("(1 + 2) * 3", ("*", ("+", 1, 2), 3)),
    ("8 - 4 - 2", ("-", ("-", 8, 4), 2)),
    ("2 * 3 * 4", ("*", ("*", 2, 3), 4)),
    ("X-1", ("-", "X", 1)),
    ("X - -2", ("-", "X", -2)),
    ("3 * -4", ("*", 3, -4)),
])
def test_arithmetic_precedence_and_associativity(expr, expected):
    assert _shape(body(f"begin R := {expr} end").expr) == expected


def test_negative_numeral_is_a_literal():
    e = body("begin X := -15 end").expr
    assert isinstance(e, A.Num) and e.value == -15


def test_boolean_precedence_not_binds_tighter_than_or():
    cond = body("begin if not A > 1 or B = 2 then skip else skip end").cond
    assert isinstance(cond, A.BoolOp) and cond.op == "or"
    assert isinstance(cond.left, A.Not) and isinstance(cond.right, A.Compare)


def test_or_is_left_associative():
    cond = body("begin if A = 1 or B = 2 or C = 3 then skip else skip end").cond
    assert isinstance(cond.left, A.BoolOp) and isinstance(cond.right, A.Compare)


def test_unicode_and_ascii_logic_give_the_same_ast():
    a = parse("begin while ¬(X = 0) ∨ Y > 1 do skip end")
    b = parse("begin while not (X = 0) or Y > 1 do skip end")
    assert a.structurally_equal(b)


def test_then_branch_may_be_a_sequence():
    stmt = body("begin if X > 0 then A := 1; B := 2 else C := 3 end")
    assert isinstance(stmt.then_branch, A.Seq) and len(stmt.then_branch.statements) == 2
    assert isinstance(stmt.else_branch, A.Assign)


def test_semicolon_ends_while_and_else():
    seq = body("begin while X > 0 do X := X - 1; Y := 1 end")
    assert isinstance(seq, A.Seq) and isinstance(seq.statements[0], A.While)
    seq = body("begin if X > 0 then skip else Y := 1; Z := 2 end")
    assert isinstance(seq, A.Seq) and isinstance(seq.statements[0], A.If)


def test_sequence_is_flattened():
    prog = parse("begin A := 1; B := 2; C := 3; D := 4 end")
    assert [s.target for s in prog.body.statements] == ["A", "B", "C", "D"]


def test_keyword_prefixes_are_names():
    names = [s.target for s in body("begin order := 1; nota := 2; beginX := 3 end").statements]
    assert names == ["order", "nota", "beginX"]


def test_node_ids_are_preorder_and_unique():
    prog = parse(example("gcd"))
    ids = [n.node_id for n in prog.walk()]
    assert ids == list(range(len(ids)))
    assert prog.node_by_id(3) is list(prog.walk())[3]
    with pytest.raises(KeyError):
        prog.node_by_id(10_000)


def test_to_dict_is_json_and_round_trips():
    prog = parse(example("unicode_logic"))
    data = json.loads(json.dumps(prog.to_dict()))
    rebuilt = A.from_dict(data)
    assert rebuilt.structurally_equal(prog)
    assert rebuilt.to_dict() == prog.to_dict()


def test_structural_equality_ignores_layout():
    assert parse("begin X:=1;Y:=2 end").structurally_equal(parse("begin\n X := 1;\n\n Y := 2 end"))
    assert not parse("begin X := 1 end").structurally_equal(parse("begin X := 2 end"))


def test_variables_in_order():
    assert parse(example("divmod")).variables() == ["Q", "R", "X", "Y"]


def test_parse_tree_leaves_are_tokens():
    tree = parse_tree("begin X := (1 + Y) end // tail")
    assert isinstance(tree, ParseNode)
    assert tree.leaves() == ["begin", "X", ":=", "(", "1", "+", "Y", ")", "end"]
    assert tree.symbol == "program"
    assert all(n.span.start <= n.span.end for n in tree.walk())


def test_parse_full_returns_both_levels():
    res = parse_full("begin X := 1 end")
    assert res.tree.symbol == "program" and isinstance(res.ast, A.Program)
    assert len(list(res.tree.walk())) > len(list(res.ast.walk()))


@pytest.mark.parametrize("src,line,col,hint_part", [
    ("X := 1", 1, 1, "begin S end"),
    ("begin X = 1 end", 1, 9, "':='"),
    ("begin\n  X := 1;\nend", 3, 1, "remove the ';'"),
    ("begin if X > 0 then skip end", 1, 26, "else"),
    ("begin\n X := 1", 2, 8, "not closed"),
    ("begin X := 1\nY := 2 end", 2, 1, "missing ';'"),
    ("begin while X do skip end", 1, 15, "comparison"),
    ("begin X := 1; if := 2 end", 1, 18, "reserved word"),
    ("begin X := 4 / 2 end", 1, 14, "no division"),
    ("begin X := 4 % 2 end", 1, 14, "remainder"),
    ("begin while X < 1 do skip end", 1, 15, "'Y > X'"),
    ("begin while X != 1 do skip end", 1, 15, "not (a = b)"),
    ("begin while X > 0 and Y > 0 do skip end", 1, 19, "no 'and'"),
    ("begin while true do skip end", 1, 18, "boolean literals"),
    ("begin X := -Y end", 1, 13, "numerals"),
    ("begin X := Y > 2 end", 1, 14, "cannot be a value"),
    ("begin skip end skip", 1, 16, "remove the text after it"),
    ("begin end", 1, 7, "cannot be empty"),
    ("begin X := (1 end", 1, 15, "')'"),
    ("begin while X > 0 skip end", 1, 19, "'do'"),
    ("begin if X > 0 skip else skip end", 1, 16, "'then'"),
    ("begin X : 1 end", 1, 9, "':='"),
    ("begin X := 1 # 2 end", 1, 14, None),
])
def test_syntax_diagnostics(src, line, col, hint_part):
    with pytest.raises(SiplSyntaxError) as info:
        parse(src)
    d = info.value.diagnostic
    assert d.kind == "syntax_error"
    assert (d.span.line, d.span.column) == (line, col)
    if hint_part:
        assert hint_part in (d.hint or ""), d.hint
    text = d.format(src, "prog.sipl")
    assert text.startswith(f"prog.sipl:{line}:{col}: syntax error")
    assert "^" in text
    assert "span" in d.to_dict()

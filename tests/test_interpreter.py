import pytest

from sipl import Interpreter, parse, run
from sipl.interpreter import ProgramFinished

from .conftest import example


def run_src(src, state=None, **kw):
    return run(parse(src), state, **kw)


@pytest.mark.parametrize("name,inp,expected", [
    ("power", {"X": 2, "Y": 10}, {"R": 1024, "Y": 0}),
    ("power", {"X": 7, "Y": 0}, {"R": 1}),
    ("power", {"X": -3, "Y": 3}, {"R": -27}),
    ("factorial", {"N": 5}, {"F": 120}),
    ("factorial", {"N": 0}, {"F": 1}),
    ("gcd", {"A": 21, "B": 14}, {"A": 7, "B": 7}),
    ("sum_to_n", {"N": 100}, {"S": 5050}),
    ("fibonacci", {"N": 20}, {"A": 6765}),
    ("max_of_two", {"X": 3, "Y": 9}, {"M": 9}),
    ("max_of_two", {"X": 9, "Y": 9}, {"M": 9}),
    ("max_of_three", {"A": 1, "B": 2, "C": 3}, {"M": 3}),
    ("max_of_three", {"A": 5, "B": 2, "C": 3}, {"M": 5}),
    ("int_sqrt", {"N": 50}, {"R": 7}),
    ("int_sqrt", {"N": 49}, {"R": 7}),
    ("divmod", {"X": 23, "Y": 4}, {"Q": 5, "R": 3}),
    ("divmod", {"X": 20, "Y": 4}, {"Q": 5, "R": 0}),
    ("abs_sign", {"X": 0}, {"A": 0, "S": 0}),
    ("abs_sign", {"X": 5}, {"A": 5, "S": 1}),
    ("abs_sign", {"X": -4}, {"A": 4, "S": -1}),
    ("multiply", {"A": 6, "B": 7}, {"P": 42}),
    ("swap", {"X": 1, "Y": 2}, {"X": 2, "Y": 1}),
    ("unicode_logic", {"X": 2, "Y": 1}, {"C": 3}),
])
def test_examples(name, inp, expected):
    res = run(parse(example(name)), inp)
    assert res.ok, res.diagnostic
    for key, value in expected.items():
        assert res.state[key] == value


@pytest.mark.parametrize("expr,value", [
    ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("10 - 2 - 3", 5), ("-7", -7),
    ("3 * -4", -12), ("1 - -1", 2), ("0 - 5", -5), ("2 * 3 * 4", 24),
])
def test_arithmetic(expr, value):
    assert run_src(f"begin R := {expr} end").state["R"] == value


@pytest.mark.parametrize("cond,value", [
    ("1 = 1", True), ("1 = 2", False), ("2 > 1", True), ("1 > 1", False),
    ("not 1 = 1", False), ("¬(1 > 2)", True), ("1 = 2 or 2 = 2", True),
    ("1 = 2 ∨ 3 = 4", False), ("not (1 = 2 or 1 > 0)", False),
    ("(1 + 1) > 1", True), ("not not 2 > 1", True),
])
def test_conditions(cond, value):
    res = run_src(f"begin if {cond} then R := 1 else R := 0 end")
    assert res.state["R"] == int(value)


def test_then_sequence_executes_all_statements():
    res = run_src("begin if 1 = 1 then A := 1; B := 2 else C := 3 end")
    assert res.state == {"A": 1, "B": 2}


def test_big_integers():
    res = run_src("begin X := 1; K := 0; while 100 > K do begin X := X * 2; K := K + 1 end end")
    assert res.state["X"] == 2 ** 100


def test_input_state_not_mutated():
    inp = {"X": 2, "Y": 3}
    run(parse(example("power")), inp)
    assert inp == {"X": 2, "Y": 3}


def test_undefined_variable_is_runtime_error():
    res = run_src("begin\n  X := 1;\n  Y := X + Z\nend")
    assert res.status == "runtime_error"
    assert res.state == {"X": 1}
    d = res.diagnostic
    assert "'Z'" in d.message and (d.span.line, d.span.column) == (3, 12)


def test_undefined_in_condition():
    assert run_src("begin while N > 0 do N := N - 1 end").status == "runtime_error"


def test_or_is_strict():
    assert run_src("begin if 1 = 1 or Z = 0 then skip else skip end").status == "runtime_error"


def test_step_limit_stops_infinite_loop():
    res = run_src("begin X := 0; while 0 = 0 do X := X + 1 end", max_steps=100)
    assert res.status == "step_limit"
    assert res.steps == 101
    assert res.state["X"] > 0
    assert "step limit" in res.diagnostic.message


def test_step_limit_not_hit_by_normal_program():
    assert run(parse(example("sum_to_n")), {"N": 10}, max_steps=100).ok


def test_invalid_max_steps():
    with pytest.raises(ValueError):
        Interpreter(parse("begin skip end"), max_steps=0)


def test_result_to_dict():
    data = run_src("begin X := 2 end", keep_trace=True).to_dict(include_trace=True)
    assert data["status"] == "ok" and data["state"] == {"X": 2}
    assert data["trace"][0]["event"] == "ProgramStarted"


def test_interpreter_is_lazy():
    interp = Interpreter(parse("begin X := 1; X := 2; X := 3 end"))
    it = interp.events()
    while True:
        e = next(it)
        if getattr(e, "name", None) == "X" and e.new == 2:
            break
    assert interp.state == {"X": 2}
    rest = list(it)
    assert isinstance(rest[-1], ProgramFinished) and interp.state == {"X": 3}

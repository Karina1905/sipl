import json

from sipl import parse, trace
from sipl.interpreter import (
    EVENT_TYPES,
    AfterStatement,
    BeforeStatement,
    ConditionEvaluated,
    ProgramFinished,
    ProgramStarted,
    VariableChanged,
)

from .conftest import example


def kinds(events):
    return [type(e).__name__ for e in events]


def test_event_sequence_for_simple_program():
    res = trace(parse("begin x := 1; if x > 0 then y := 2 else skip end"))
    assert kinds(res.events) == [
        "ProgramStarted",
        "BeforeStatement", "VariableChanged", "AfterStatement",
        "BeforeStatement", "ConditionEvaluated",
        "BeforeStatement", "VariableChanged", "AfterStatement",
        "AfterStatement",
        "ProgramFinished",
    ]


def test_variable_changed_reports_old_and_new():
    res = trace(parse("begin x := 1; x := x + 4 end"), {})
    changes = [e for e in res.events if isinstance(e, VariableChanged)]
    assert [(c.name, c.old, c.new) for c in changes] == [("x", None, 1), ("x", 1, 5)]


def test_while_condition_iterations():
    res = trace(parse(example("power")), {"X": 2, "Y": 3})
    checks = [e for e in res.events if isinstance(e, ConditionEvaluated)]
    assert [(c.iteration, c.value) for c in checks] == [(1, True), (2, True), (3, True),
                                                        (4, False)]
    assert all(c.construct == "while" for c in checks)


def test_events_link_to_ast_and_source():
    src = example("max_of_two")
    prog = parse(src)
    res = trace(prog, {"X": 1, "Y": 2})
    for e in res.events:
        if isinstance(e, (BeforeStatement, AfterStatement)):
            node = prog.node_by_id(e.node_id)
            assert node.kind == e.kind and node.span == e.span
        if isinstance(e, ConditionEvaluated):
            assert prog.node_by_id(e.cond_id).span.text(src) == "X > Y"


def test_before_after_balanced_and_steps_monotonic():
    res = trace(parse(example("gcd")), {"A": 35, "B": 15})
    depth = 0
    last_step = 0
    for e in res.events:
        assert e.step >= last_step
        last_step = e.step
        if isinstance(e, BeforeStatement):
            depth += 1
        elif isinstance(e, AfterStatement):
            depth -= 1
        assert depth >= 0
    assert depth == 0


def test_states_are_snapshots():
    res = trace(parse("begin x := 1; x := 2 end"))
    befores = [e for e in res.events if isinstance(e, BeforeStatement)]
    assert befores[0].state == {} and befores[1].state == {"x": 1}


def test_start_and_finish():
    res = trace(parse("begin x := 1 end"), {"a": 5})
    assert isinstance(res.events[0], ProgramStarted) and res.events[0].state == {"a": 5}
    fin = res.events[-1]
    assert isinstance(fin, ProgramFinished)
    assert fin.status == "ok" and fin.state == {"a": 5, "x": 1}


def test_error_finishes_trace_with_diagnostic():
    res = trace(parse("begin x := y end"))
    fin = res.events[-1]
    assert fin.status == "runtime_error" and fin.diagnostic is not None
    assert not any(isinstance(e, AfterStatement) for e in res.events)


def test_events_serialise_to_json():
    res = trace(parse(example("gcd")), {"A": 4, "B": 6})
    for e in res.events:
        data = json.loads(json.dumps(e.to_dict()))
        assert data["event"] in {t.__name__ for t in EVENT_TYPES}
        assert "step" in data
    err = trace(parse("begin x := y end"))
    assert json.dumps(err.events[-1].to_dict())

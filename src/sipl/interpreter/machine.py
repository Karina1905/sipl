from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Mapping

from .. import ast as A
from ..diagnostics import Diagnostic, SiplRuntimeError, StepLimitExceeded
from .events import (
    AfterStatement,
    BeforeStatement,
    ConditionEvaluated,
    Event,
    ProgramFinished,
    ProgramStarted,
    State,
    VariableChanged,
)

DEFAULT_MAX_STEPS = 100_000


@dataclass
class ExecutionResult:
    status: str
    state: State
    steps: int
    diagnostic: Diagnostic | None = None
    events: list[Event] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self, include_trace: bool = False) -> dict:
        data: dict = {"status": self.status, "state": dict(self.state), "steps": self.steps}
        if self.diagnostic is not None:
            data["diagnostic"] = self.diagnostic.to_dict()
        if include_trace:
            data["trace"] = [e.to_dict() for e in self.events]
        return data


class Interpreter:
    def __init__(self, program: A.Program, max_steps: int = DEFAULT_MAX_STEPS):
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self.program = program
        self.max_steps = max_steps
        self.steps = 0
        self.state: State = {}

    def events(self, initial_state: Mapping[str, int] | None = None) -> Iterator[Event]:
        self.state = dict(initial_state or {})
        self.steps = 0
        yield ProgramStarted(step=0, state=dict(self.state))
        try:
            yield from self._exec(self.program.body)
        except StepLimitExceeded as exc:
            yield ProgramFinished(self.steps, "step_limit", dict(self.state), exc.diagnostic)
            return
        except SiplRuntimeError as exc:
            yield ProgramFinished(self.steps, "runtime_error", dict(self.state), exc.diagnostic)
            return
        yield ProgramFinished(self.steps, "ok", dict(self.state))

    def _exec(self, stmt: A.Stmt) -> Iterator[Event]:
        if isinstance(stmt, A.Seq):
            for s in stmt.statements:
                yield from self._exec(s)
            return

        self.steps += 1
        if self.steps > self.max_steps:
            raise StepLimitExceeded(Diagnostic(
                "step_limit",
                f"step limit of {self.max_steps} exceeded (possible infinite loop)",
                stmt.span,
                hint="increase the limit with --max-steps or check the loop condition",
            ))
        yield BeforeStatement(self.steps, stmt.node_id, stmt.kind, stmt.span, dict(self.state))

        if isinstance(stmt, A.Assign):
            value = self.eval_aexp(stmt.expr)
            old = self.state.get(stmt.target)
            self.state[stmt.target] = value
            yield VariableChanged(self.steps, stmt.node_id, stmt.target, old, value, stmt.span)
        elif isinstance(stmt, A.If):
            cond = self.eval_bexp(stmt.cond)
            yield ConditionEvaluated(self.steps, stmt.node_id, stmt.cond.node_id, "if",
                                     cond, stmt.cond.span)
            yield from self._exec(stmt.then_branch if cond else stmt.else_branch)
        elif isinstance(stmt, A.While):
            iteration = 0
            while True:
                iteration += 1
                cond = self.eval_bexp(stmt.cond)
                yield ConditionEvaluated(self.steps, stmt.node_id, stmt.cond.node_id, "while",
                                         cond, stmt.cond.span, iteration)
                if not cond:
                    break
                yield from self._exec(stmt.body)
        elif isinstance(stmt, A.Block):
            yield from self._exec(stmt.body)
        elif isinstance(stmt, A.Skip):
            pass
        else:
            raise TypeError(stmt)

        yield AfterStatement(self.steps, stmt.node_id, stmt.kind, stmt.span, dict(self.state))

    def eval_aexp(self, e: A.AExpr) -> int:
        if isinstance(e, A.Num):
            return e.value
        if isinstance(e, A.Var):
            if e.name not in self.state:
                raise SiplRuntimeError(Diagnostic(
                    "runtime_error", f"variable '{e.name}' is undefined in the current state",
                    e.span, hint=f"assign it first or pass an input value, e.g. --set {e.name}=0",
                ))
            return self.state[e.name]
        if isinstance(e, A.BinOp):
            left = self.eval_aexp(e.left)
            right = self.eval_aexp(e.right)
            if e.op == "+":
                return left + right
            if e.op == "-":
                return left - right
            return left * right
        raise TypeError(e)

    def eval_bexp(self, e: A.BExpr) -> bool:
        if isinstance(e, A.Not):
            return not self.eval_bexp(e.operand)
        if isinstance(e, A.BoolOp):
            left = self.eval_bexp(e.left)
            right = self.eval_bexp(e.right)
            return left or right
        if isinstance(e, A.Compare):
            a = self.eval_aexp(e.left)
            b = self.eval_aexp(e.right)
            return a == b if e.op == "=" else a > b
        raise TypeError(e)


def run(program: A.Program, state: Mapping[str, int] | None = None,
        max_steps: int = DEFAULT_MAX_STEPS, keep_trace: bool = False) -> ExecutionResult:
    interp = Interpreter(program, max_steps)
    events: list[Event] = []
    final: ProgramFinished | None = None
    for event in interp.events(state):
        if keep_trace:
            events.append(event)
        if isinstance(event, ProgramFinished):
            final = event
    assert final is not None
    return ExecutionResult(final.status, final.state, interp.steps, final.diagnostic, events)


def trace(program: A.Program, state: Mapping[str, int] | None = None,
          max_steps: int = DEFAULT_MAX_STEPS) -> ExecutionResult:
    return run(program, state, max_steps, keep_trace=True)

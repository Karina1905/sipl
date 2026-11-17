from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..diagnostics import Diagnostic, SourceSpan

State = dict[str, int]


@dataclass
class Event:
    step: int

    @property
    def type(self) -> str:
        return type(self).__name__

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"event": self.type}
        for key, value in self.__dict__.items():
            if isinstance(value, SourceSpan):
                data[key] = value.to_dict()
            elif isinstance(value, Diagnostic):
                data[key] = value.to_dict()
            elif isinstance(value, dict):
                data[key] = dict(value)
            else:
                data[key] = value
        return data


@dataclass
class ProgramStarted(Event):
    state: State


@dataclass
class BeforeStatement(Event):
    node_id: int
    kind: str
    span: SourceSpan
    state: State


@dataclass
class VariableChanged(Event):
    node_id: int
    name: str
    old: int | None
    new: int
    span: SourceSpan


@dataclass
class ConditionEvaluated(Event):
    node_id: int
    cond_id: int
    construct: str
    value: bool
    span: SourceSpan
    iteration: int | None = None


@dataclass
class AfterStatement(Event):
    node_id: int
    kind: str
    span: SourceSpan
    state: State


@dataclass
class ProgramFinished(Event):
    status: str
    state: State
    diagnostic: Diagnostic | None = field(default=None)


EVENT_TYPES = (ProgramStarted, BeforeStatement, VariableChanged,
               ConditionEvaluated, AfterStatement, ProgramFinished)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int
    end_line: int
    end_column: int
    start: int
    end: int

    def to_dict(self) -> dict[str, int]:
        return {
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "start": self.start,
            "end": self.end,
        }

    def text(self, source: str) -> str:
        return source[self.start : self.end]

    def __str__(self) -> str:
        return f"{self.line}:{self.column}-{self.end_line}:{self.end_column}"


@dataclass
class Diagnostic:
    kind: str
    message: str
    span: SourceSpan | None = None
    hint: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"kind": self.kind, "message": self.message}
        if self.span is not None:
            data["span"] = self.span.to_dict()
        if self.hint:
            data["hint"] = self.hint
        data.update(self.extra)
        return data

    def format(self, source: str | None = None, filename: str = "<input>") -> str:
        if self.span is None:
            head = f"{filename}: {self.kind.replace('_', ' ')}: {self.message}"
        else:
            head = (
                f"{filename}:{self.span.line}:{self.span.column}: "
                f"{self.kind.replace('_', ' ')}: {self.message}"
            )
        lines = [head]
        if source is not None and self.span is not None:
            src_lines = source.splitlines()
            if 0 < self.span.line <= len(src_lines):
                text = src_lines[self.span.line - 1]
                width = 1
                if self.span.end_line == self.span.line:
                    width = max(1, self.span.end_column - self.span.column)
                lines.append(f"  {self.span.line:>4} | {text}")
                lines.append("       | " + " " * (self.span.column - 1) + "^" * width)
        if self.hint:
            lines.append(f"  hint: {self.hint}")
        return "\n".join(lines)


class SiplError(Exception):
    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class SiplSyntaxError(SiplError):
    pass


class SiplRuntimeError(SiplError):
    pass


class StepLimitExceeded(SiplError):
    pass

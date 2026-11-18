from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .diagnostics import Diagnostic, SiplSyntaxError
from .interpreter import DEFAULT_MAX_STEPS, Event, run, trace
from .interpreter.events import (
    AfterStatement,
    BeforeStatement,
    ConditionEvaluated,
    ProgramFinished,
    ProgramStarted,
    VariableChanged,
)
from .parser import ParseResult, grammar_text, parse_full
from .visualization import (
    combined,
    compact_parse_tree,
    from_ast,
    from_parse_tree,
    to_dot,
    to_svg,
    to_text,
)

SCHEMA_VERSION = 1

EXIT_OK = 0
EXIT_SYNTAX = 1
EXIT_USAGE = 2
EXIT_RUNTIME = 3
EXIT_STEP_LIMIT = 4
EXIT_IO = 5

_STATUS_EXIT = {"ok": EXIT_OK, "runtime_error": EXIT_RUNTIME, "step_limit": EXIT_STEP_LIMIT}


class CliError(Exception):
    def __init__(self, diagnostic: Diagnostic, code: int, source: str | None = None):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic
        self.code = code
        self.source = source


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(Diagnostic("io_error", f"cannot read '{path}': {exc.strerror}"),
                       EXIT_IO) from None


def _parse_state(pairs: list[str], json_input: str | None) -> dict[str, int]:
    state: dict[str, int] = {}
    if json_input:
        try:
            raw = json.loads(Path(json_input).read_text(encoding="utf-8")
                             if Path(json_input).is_file() else json_input)
        except (json.JSONDecodeError, OSError) as exc:
            raise CliError(Diagnostic("input_error", f"invalid --input: {exc}"),
                           EXIT_USAGE) from None
        if not isinstance(raw, dict):
            raise CliError(Diagnostic("input_error", "--input must be a JSON object"), EXIT_USAGE)
        for key, value in raw.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise CliError(Diagnostic("input_error", f"value of '{key}' must be an integer"),
                               EXIT_USAGE)
            state[key] = value
    for pair in pairs:
        name, sep, value = pair.partition("=")
        name = name.strip()
        if not sep or not name.isidentifier():
            raise CliError(Diagnostic("input_error", f"expected NAME=INTEGER, got '{pair}'"),
                           EXIT_USAGE)
        try:
            state[name] = int(value)
        except ValueError:
            raise CliError(Diagnostic("input_error", f"value of '{name}' must be an integer, "
                                                     f"got '{value}'"), EXIT_USAGE) from None
    return state


def _emit_json(command: str, file: str, ok: bool, payload: dict[str, Any]) -> None:
    out = {"schema_version": SCHEMA_VERSION, "command": command, "file": file, "ok": ok}
    out.update(payload)
    print(json.dumps(out, ensure_ascii=False, indent=2))


def _write_output(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"written {output}", file=sys.stderr)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _load(args: argparse.Namespace) -> tuple[str, ParseResult]:
    source = _read(args.file)
    try:
        return source, parse_full(source)
    except SiplSyntaxError as exc:
        raise CliError(exc.diagnostic, EXIT_SYNTAX, source) from None


def _state_str(state: dict[str, int]) -> str:
    if not state:
        return "{}"
    return "{" + ", ".join(f"{k}={v}" for k, v in state.items()) + "}"


def cmd_parse(args: argparse.Namespace) -> int:
    source, result = _load(args)
    if args.json:
        _emit_json("parse", args.file, True, {"ast": result.ast.to_dict()})
    else:
        print(to_text(from_ast(result.ast), show_spans=args.spans))
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    source, result = _load(args)
    variables = result.ast.variables()
    if args.json:
        _emit_json("check", args.file, True, {"diagnostics": [], "variables": variables})
    else:
        print(f"{args.file}: OK ({len(list(result.ast.walk()))} AST nodes; "
              f"variables: {', '.join(variables) or '-'})")
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    source, result = _load(args)
    state = _parse_state(args.set, args.input)
    res = run(result.ast, state, max_steps=args.max_steps)
    if args.json:
        _emit_json("run", args.file, res.ok, {"input": state, **res.to_dict()})
    else:
        if res.ok:
            for name, value in res.state.items():
                print(f"{name} = {value}")
        else:
            assert res.diagnostic is not None
            print(res.diagnostic.format(source, args.file), file=sys.stderr)
            print(f"state at failure: {_state_str(res.state)}", file=sys.stderr)
    return _STATUS_EXIT[res.status]


def format_event(e: Event, source: str) -> str:
    if isinstance(e, ProgramStarted):
        return f"start                 state {_state_str(e.state)}"
    if isinstance(e, BeforeStatement):
        frag = " ".join(source[e.span.start:e.span.end].split())
        if len(frag) > 50:
            frag = frag[:47] + "..."
        return f"#{e.step:<4} {e.kind:<8} @{e.span.line}:{e.span.column:<4} {frag}"
    if isinstance(e, VariableChanged):
        old = "⊥" if e.old is None else e.old
        return f"        {e.name}: {old} -> {e.new}"
    if isinstance(e, ConditionEvaluated):
        cond = " ".join(source[e.span.start:e.span.end].split())
        it = f" (check {e.iteration})" if e.iteration else ""
        return f"        {e.construct} [{cond}] = {str(e.value).lower()}{it}"
    if isinstance(e, AfterStatement):
        return f"        end {e.kind} #{e.node_id}  state {_state_str(e.state)}"
    if isinstance(e, ProgramFinished):
        line = f"finish {e.status}       state {_state_str(e.state)}"
        if e.diagnostic is not None:
            line += f"\n  {e.diagnostic.kind}: {e.diagnostic.message}"
        return line
    return repr(e)


def cmd_trace(args: argparse.Namespace) -> int:
    source, result = _load(args)
    state = _parse_state(args.set, args.input)
    res = trace(result.ast, state, max_steps=args.max_steps)
    events = res.events
    if not args.verbose:
        events = [e for e in events if not isinstance(e, AfterStatement)]
    if args.format == "json":
        _emit_json("trace", args.file, res.ok, {"input": state, **res.to_dict(include_trace=True)})
    elif args.format == "jsonl":
        for e in res.events:
            print(json.dumps(e.to_dict(), ensure_ascii=False))
    else:
        for e in events:
            print(format_event(e, source))
    return _STATUS_EXIT[res.status]


def cmd_tree(args: argparse.Namespace) -> int:
    source, result = _load(args)
    compact = args.compact or args.kind == "both"
    parse_view = (compact_parse_tree(result.tree, args.rules) if compact
                  else from_parse_tree(result.tree, args.rules))
    if args.kind == "both":
        view = combined(parse_view, from_ast(result.ast),
                        f"SIPL: Parse Tree ↔ AST — {Path(args.file).name}")
    else:
        view = parse_view if args.kind == "parse" else from_ast(result.ast)
    name = f"{Path(args.file).stem} ({args.kind})"
    if args.format == "text":
        text = to_text(view, source=source if args.kind == "parse" else None,
                       show_spans=args.spans)
    elif args.format == "json":
        payload: Any
        if args.kind == "both":
            payload = view.to_dict()
        elif args.kind == "parse":
            payload = parse_view.to_dict() if compact else result.tree.to_dict()
        else:
            payload = result.ast.to_dict()
        text = json.dumps({"schema_version": SCHEMA_VERSION, "kind": args.kind, "source": source,
                           "tree": payload}, ensure_ascii=False, indent=2)
    elif args.format == "dot":
        text = to_dot(view, name)
    else:
        text = to_svg(view, name, source)
    _write_output(text, args.output)
    return EXIT_OK


def cmd_grammar(args: argparse.Namespace) -> int:
    sys.stdout.write(grammar_text())
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sipl", description="SIPL Language Toolkit")
    p.add_argument("--version", action="version", version=f"sipl {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def add(name: str, func, help_: str, json_flag: bool = True) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.add_argument("file", help="SIPL source file ('-' for stdin)")
        if json_flag:
            sp.add_argument("--json", action="store_true", help="machine-readable JSON output")
        sp.set_defaults(func=func, json=False)
        return sp

    def add_exec_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("-s", "--set", action="append", default=[], metavar="NAME=INT",
                        help="initial value of a variable (repeatable)")
        sp.add_argument("--input", metavar="JSON", help="initial state as JSON object or file")
        sp.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                        help=f"step limit against infinite loops (default {DEFAULT_MAX_STEPS})")

    sp = add("parse", cmd_parse, "parse a program and print its AST")
    sp.add_argument("--no-spans", dest="spans", action="store_false", help="hide source spans")
    add("check", cmd_check, "check syntax and report diagnostics")
    sp = add("run", cmd_run, "execute a program and print the final state")
    add_exec_opts(sp)
    sp = add("trace", cmd_trace, "execute a program and print the execution trace", False)
    add_exec_opts(sp)
    sp.add_argument("--format", choices=["text", "json", "jsonl"], default="text")
    sp.add_argument("-v", "--verbose", action="store_true", help="also show AfterStatement")
    sp.add_argument("--json", dest="format", action="store_const", const="json",
                    help="same as --format json")
    sp = add("tree", cmd_tree, "export the parse tree or AST (text/json/dot/svg)", False)
    sp.add_argument("--kind", choices=["parse", "ast", "both"], default="parse",
                    help="parse tree, AST, or both side by side in one picture")
    sp.add_argument("--rules", action="store_true",
                    help="show the course BNF rule of each node (P1, S1-S6, A1-A6, B1-B5)")
    sp.add_argument("--compact", action="store_true",
                    help="parse tree without single-child chains (always on for --kind both)")
    sp.add_argument("--format", choices=["text", "json", "dot", "svg"], default="text")
    sp.add_argument("-o", "--output", help="output file (default: stdout)")
    sp.add_argument("--no-spans", dest="spans", action="store_false", help="hide source spans")
    gp = sub.add_parser("grammar", help="print the Lark grammar of SIPL")
    gp.set_defaults(func=cmd_grammar, json=False, file="-")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "max_steps", 1) <= 0:
        parser.error("--max-steps must be positive")
    use_json = getattr(args, "json", False) or getattr(args, "format", None) in ("json", "jsonl")
    try:
        return int(args.func(args))
    except CliError as exc:
        if use_json and args.command != "tree":
            _emit_json(args.command, args.file, False, {
                "status": exc.diagnostic.kind,
                "diagnostics": [exc.diagnostic.to_dict()],
            })
        else:
            print(exc.diagnostic.format(exc.source, args.file), file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())

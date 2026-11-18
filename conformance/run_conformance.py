from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "cases"
VALID_STATUSES = {"ok", "syntax_error", "runtime_error", "step_limit"}
EXIT_CODES = {"ok": 0, "syntax_error": 1, "runtime_error": 3, "step_limit": 4}


def call(impl: list[str], args: list[str], timeout: float) -> dict[str, Any]:
    proc = subprocess.run(impl + args, capture_output=True, text=True, timeout=timeout)
    try:
        out = json.loads(proc.stdout)
        out["_exit"] = proc.returncode
        return out
    except json.JSONDecodeError:
        raise AssertionError(
            f"implementation did not print JSON (exit {proc.returncode}).\n"
            f"stdout: {proc.stdout[:500]}\nstderr: {proc.stderr[:500]}"
        ) from None


def first_diagnostic(out: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(out.get("diagnostic"), dict):
        return out["diagnostic"]
    diags = out.get("diagnostics") or []
    return diags[0] if diags else None


def strip_ids(data: Any, ignore_spans: bool) -> Any:
    drop = {"id"} | ({"span"} if ignore_spans else set())
    if isinstance(data, dict):
        return {k: strip_ids(v, ignore_spans) for k, v in data.items() if k not in drop}
    if isinstance(data, list):
        return [strip_ids(v, ignore_spans) for v in data]
    return data


def check_case(spec_path: Path, impl: list[str], opts: argparse.Namespace) -> list[str]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    source = spec_path.with_suffix(".sipl")
    expect = spec["expect"]
    if expect["status"] not in VALID_STATUSES:
        return [f"bad case file: unknown status {expect['status']!r}"]
    errors: list[str] = []

    args = ["run", "--json", "--input", json.dumps(spec.get("input", {}))]
    if "max_steps" in spec:
        args += ["--max-steps", str(spec["max_steps"])]
    out = call(impl, args + [str(source)], opts.timeout)

    status = out.get("status")
    if status != expect["status"]:
        errors.append(f"status: expected {expect['status']!r}, got {status!r}")
    wanted_exit = expect.get("exit_code", EXIT_CODES[expect["status"]])
    if out["_exit"] != wanted_exit:
        errors.append(f"exit code: expected {wanted_exit}, got {out['_exit']}")
    if "state" in expect and out.get("state") != expect["state"]:
        errors.append(f"state: expected {expect['state']}, got {out.get('state')}")
    if "error" in expect:
        diag = first_diagnostic(out)
        if diag is None:
            errors.append("expected a diagnostic, got none")
        else:
            span = diag.get("span") or {}
            for key in ("line", "column"):
                if key in expect["error"] and span.get(key) != expect["error"][key]:
                    errors.append(f"error {key}: expected {expect['error'][key]}, "
                                  f"got {span.get(key)}")
            needle = expect["error"].get("message_contains")
            if needle and needle not in diag.get("message", ""):
                errors.append(f"error message {diag.get('message')!r} lacks {needle!r}")

    if "ast" in expect:
        golden = spec_path.parent / expect["ast"]
        parsed = call(impl, ["parse", "--json", str(source)], opts.timeout)
        actual = parsed.get("ast")
        if opts.bless:
            golden.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        elif not golden.exists():
            errors.append(f"missing golden file {golden.name} (run with --bless)")
        else:
            wanted = json.loads(golden.read_text(encoding="utf-8"))
            if strip_ids(actual, opts.ignore_spans) != strip_ids(wanted, opts.ignore_spans):
                errors.append(f"AST differs from {golden.name}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--impl", default="sipl", help="command prefix of the implementation")
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="directory with cases")
    ap.add_argument("-k", dest="filter", help="run only cases whose name contains this")
    ap.add_argument("--ignore-spans", action="store_true", help="compare ASTs without spans")
    ap.add_argument("--bless", action="store_true", help="write AST golden files")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    opts = ap.parse_args(argv)

    impl = shlex.split(opts.impl)
    specs = sorted(p for p in opts.cases.glob("*.json") if not p.name.endswith(".ast.json"))
    if opts.filter:
        specs = [p for p in specs if opts.filter in p.stem]
    if not specs:
        print("no cases found", file=sys.stderr)
        return 2

    failed = 0
    for spec in specs:
        try:
            errors = check_case(spec, impl, opts)
        except (AssertionError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            errors = [str(exc)]
        if errors:
            failed += 1
            print(f"FAIL {spec.stem}")
            for e in errors:
                print(f"     {e}")
        elif opts.verbose:
            print(f"ok   {spec.stem}")
    passed = len(specs) - failed
    print(f"\n{passed}/{len(specs)} conformance cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sipl.cli import (
    EXIT_IO,
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_STEP_LIMIT,
    EXIT_SYNTAX,
    EXIT_USAGE,
    SCHEMA_VERSION,
    main,
)

EX = Path(__file__).resolve().parent.parent / "examples"
POWER = str(EX / "valid" / "power.sipl")
BAD = str(EX / "invalid" / "assign_with_eq.sipl")


def run_cli(capsys, *args):
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def write(tmp_path, text, name="p.sipl"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def envelope(out, command, ok):
    data = json.loads(out)
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["command"] == command and data["ok"] is ok
    return data


def test_parse_text(capsys):
    code, out, _ = run_cli(capsys, "parse", POWER)
    assert code == EXIT_OK and "While" in out and "[" in out


def test_parse_json(capsys):
    code, out, _ = run_cli(capsys, "parse", "--json", POWER)
    data = envelope(out, "parse", True)
    assert code == EXIT_OK and data["ast"]["type"] == "Program"


def test_check_ok(capsys):
    code, out, _ = run_cli(capsys, "check", POWER)
    assert code == EXIT_OK and "OK" in out and "R, Y, X" in out


def test_check_json_ok(capsys):
    code, out, _ = run_cli(capsys, "check", "--json", POWER)
    data = envelope(out, "check", True)
    assert data["diagnostics"] == [] and data["variables"] == ["R", "Y", "X"]


def test_check_syntax_error_text(capsys):
    code, out, err = run_cli(capsys, "check", BAD)
    assert code == EXIT_SYNTAX
    assert "assign_with_eq.sipl:2:5: syntax error" in err and "^" in err


def test_check_syntax_error_json(capsys):
    code, out, _ = run_cli(capsys, "check", "--json", BAD)
    data = envelope(out, "check", False)
    assert code == EXIT_SYNTAX and data["status"] == "syntax_error"
    d = data["diagnostics"][0]
    assert d["span"]["line"] == 2 and d["span"]["column"] == 5 and d["hint"]


def test_run_text(capsys):
    code, out, _ = run_cli(capsys, "run", POWER, "-s", "X=3", "--set", "Y=4")
    assert code == EXIT_OK and "R = 81" in out


def test_run_json_with_input(capsys):
    code, out, _ = run_cli(capsys, "run", "--json", "--input", '{"X": 2, "Y": 5}', POWER)
    data = envelope(out, "run", True)
    assert data["status"] == "ok" and data["state"]["R"] == 32 and data["input"]["Y"] == 5


def test_run_input_from_file(capsys, tmp_path):
    inp = tmp_path / "in.json"
    inp.write_text('{"X": 5, "Y": 2}')
    code, out, _ = run_cli(capsys, "run", "--json", "--input", str(inp), POWER)
    assert json.loads(out)["state"]["R"] == 25


def test_run_runtime_error(capsys, tmp_path):
    code, out, err = run_cli(capsys, "run", write(tmp_path, "begin x := 1; y := z end"))
    assert code == EXIT_RUNTIME and "'z' is undefined" in err and "state at failure" in err


def test_run_runtime_error_json(capsys, tmp_path):
    code, out, _ = run_cli(capsys, "run", "--json", write(tmp_path, "begin x := y end"))
    data = envelope(out, "run", False)
    assert code == EXIT_RUNTIME and data["status"] == "runtime_error"
    assert data["diagnostic"]["span"]["column"] == 12


def test_run_step_limit(capsys, tmp_path):
    code, out, _ = run_cli(capsys, "run", "--json", "--max-steps", "20",
                           write(tmp_path, "begin while 0 = 0 do skip end"))
    assert code == EXIT_STEP_LIMIT and json.loads(out)["status"] == "step_limit"


@pytest.mark.parametrize("args", [
    ["-s", "X"], ["-s", "X=abc"], ["-s", "1X=2"], ["--input", "[1,2]"],
    ["--input", "{bad json"], ["--input", '{"X": "2"}'],
])
def test_run_bad_input(capsys, args):
    code, out, err = run_cli(capsys, "run", POWER, *args)
    assert code == EXIT_USAGE and "input error" in err


def test_bad_input_json(capsys):
    code, out, _ = run_cli(capsys, "run", "--json", POWER, "-s", "X=q")
    assert code == EXIT_USAGE and json.loads(out)["status"] == "input_error"


def test_negative_max_steps(capsys):
    with pytest.raises(SystemExit) as info:
        main(["run", POWER, "--max-steps", "0"])
    assert info.value.code == EXIT_USAGE


def test_missing_file(capsys):
    code, out, err = run_cli(capsys, "run", "no/such/file.sipl")
    assert code == EXIT_IO and "cannot read" in err


def test_stdin(capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("begin x := 6 * 7 end"))
    code, out, _ = run_cli(capsys, "run", "-")
    assert code == EXIT_OK and "x = 42" in out


def test_usage_error_exit_code():
    with pytest.raises(SystemExit) as info:
        main(["frobnicate"])
    assert info.value.code == EXIT_USAGE


def test_trace_text(capsys):
    code, out, _ = run_cli(capsys, "trace", POWER, "-s", "X=2", "-s", "Y=1")
    assert code == EXIT_OK
    assert "R: ⊥ -> 1" in out and "while [Y > 0] = true (check 1)" in out
    assert out.strip().splitlines()[-1].startswith("finish ok")
    assert "end Assign" not in out


def test_trace_verbose(capsys):
    _, out, _ = run_cli(capsys, "trace", "-v", POWER, "-s", "X=2", "-s", "Y=1")
    assert "end Assign" in out


def test_trace_json(capsys):
    code, out, _ = run_cli(capsys, "trace", "--json", POWER, "-s", "X=2", "-s", "Y=1")
    data = envelope(out, "trace", True)
    events = [e["event"] for e in data["trace"]]
    assert events[0] == "ProgramStarted" and events[-1] == "ProgramFinished"


def test_trace_jsonl(capsys):
    _, out, _ = run_cli(capsys, "trace", "--format", "jsonl", POWER, "-s", "X=2", "-s", "Y=0")
    lines = [json.loads(line) for line in out.strip().splitlines()]
    assert lines[-1]["event"] == "ProgramFinished" and lines[-1]["state"]["R"] == 1


def test_trace_error(capsys, tmp_path):
    code, out, _ = run_cli(capsys, "trace", write(tmp_path, "begin x := 1;\ny := x * z end"))
    assert code == EXIT_RUNTIME and "runtime_error" in out and "'z' is undefined" in out


@pytest.mark.parametrize("kind", ["parse", "ast"])
@pytest.mark.parametrize("fmt", ["text", "json", "dot", "svg"])
def test_tree_formats(capsys, kind, fmt):
    code, out, _ = run_cli(capsys, "tree", POWER, "--kind", kind, "--format", fmt)
    assert code == EXIT_OK and out.strip()
    if fmt == "json":
        assert json.loads(out)["kind"] == kind
    if fmt == "dot":
        assert out.startswith("digraph")
    if fmt == "svg":
        assert out.lstrip().startswith("<svg")


@pytest.mark.parametrize("fmt", ["text", "json", "svg"])
def test_tree_both_and_compact(capsys, fmt):
    code, out, _ = run_cli(capsys, "tree", POWER, "--kind", "both", "--format", fmt)
    assert code == EXIT_OK and "AST" in out and "Parse Tree" in out
    code, out, _ = run_cli(capsys, "tree", POWER, "--compact", "--format", fmt)
    assert code == EXIT_OK and "Assignment" in out


def test_tree_rules(capsys):
    code, out, _ = run_cli(capsys, "tree", POWER, "--rules", "--no-spans")
    assert code == EXIT_OK and "[P1]" in out and "[S4]" in out and "[A5]" in out


def test_tree_to_file(capsys, tmp_path):
    out_file = tmp_path / "t.svg"
    code, _, err = run_cli(capsys, "tree", POWER, "--format", "svg", "-o", str(out_file))
    assert code == EXIT_OK and out_file.read_text().startswith("<svg") and "written" in err


def test_tree_syntax_error(capsys):
    code, _, err = run_cli(capsys, "tree", BAD)
    assert code == EXIT_SYNTAX and "syntax error" in err


def test_grammar(capsys):
    code, out, _ = run_cli(capsys, "grammar")
    assert code == EXIT_OK and "while_stmt" in out


def test_console_entry_point():
    proc = subprocess.run([sys.executable, "-m", "sipl", "run", "--json", POWER,
                           "-s", "X=2", "-s", "Y=3"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["state"]["R"] == 8

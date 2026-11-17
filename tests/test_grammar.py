from pathlib import Path

import pytest

from sipl import SiplSyntaxError, check, parse
from sipl.parser import grammar_text

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
VALID_FILES = sorted((EXAMPLES / "valid").glob("*.sipl"))
INVALID_FILES = sorted((EXAMPLES / "invalid").glob("*.sipl"))

VALID_SNIPPETS = [
    "begin skip end",
    "begin X := 1 end",
    "begin X := 1; Y := 2 end",
    "begin begin X := 1 end end",
    "begin if X > 0 then Y := 1 else Y := 2 end",
    "begin if X > 0 then Y := 1; Z := 2 else skip end",
    "begin while X > 0 do X := X - 1 end",
    "begin while not (X = 0) or Y > 3 do skip end",
    "begin while ¬(X = 0) ∨ Y > 3 do skip end",
    "begin X := ((1 + 2) * (3 - 4)) * 5 end",
    "begin X := -1; Y := X-1; Z := X - -2; W := 3 * -4 end",
    "begin if (X + 1) > 2 then skip else if X = 2 then skip else skip end",
    "begin X_1 := beginning + ending; order := nota; doX := 1 end",
    "begin X:=1;Y:=X+1 end",
    "// comment\nbegin X := 0 /* inline */ end",
]

INVALID_SNIPPETS = [
    "",
    "X := 1",
    "skip",
    "begin end",
    "begin X = 1 end",
    "begin X := 1; end",
    "begin X := 1",
    "begin if X > 0 then skip end",
    "begin while X > 0 skip end",
    "begin while X do skip end",
    "begin X := 4 / 2 end",
    "begin X := 4 % 2 end",
    "begin while X < 1 do skip end",
    "begin while X >= 1 do skip end",
    "begin while X > 0 and Y > 0 do skip end",
    "begin while true do skip end",
    "begin X := -Y end",
    "begin X := 1 < 2 end",
    "begin X := Y > 2 end",
    "begin if := 3 end",
    "begin X := 1 Y := 2 end",
    "begin X := (1 end",
    "begin skip end skip",
    "begin 1X := 2 end",
]


def test_grammar_file_is_packaged():
    text = grammar_text()
    assert "while_stmt" in text and "if_stmt" in text


def test_requirement_counts():
    assert len(VALID_FILES) + len(VALID_SNIPPETS) >= 10
    assert len(INVALID_FILES) + len(INVALID_SNIPPETS) >= 10


@pytest.mark.parametrize("path", VALID_FILES, ids=lambda p: p.stem)
def test_valid_example_files(path: Path):
    assert check(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("path", INVALID_FILES, ids=lambda p: p.stem)
def test_invalid_example_files(path: Path):
    diags = check(path.read_text(encoding="utf-8"))
    assert len(diags) == 1
    assert diags[0].kind == "syntax_error"
    assert diags[0].span is not None


@pytest.mark.parametrize("source", VALID_SNIPPETS)
def test_valid_snippets(source: str):
    parse(source)


@pytest.mark.parametrize("source", INVALID_SNIPPETS)
def test_invalid_snippets(source: str):
    with pytest.raises(SiplSyntaxError):
        parse(source)

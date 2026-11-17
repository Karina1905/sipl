from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


def example(name: str) -> str:
    return (EXAMPLES / "valid" / f"{name}.sipl").read_text(encoding="utf-8")

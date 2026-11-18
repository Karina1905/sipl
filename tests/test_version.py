import re
from importlib.metadata import version
from pathlib import Path

import sipl

ROOT = Path(__file__).resolve().parent.parent


def test_version_consistent():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.M)
    assert match and match.group(1) == sipl.__version__
    assert version("sipl-lang-toolkit") == sipl.__version__


def test_version_is_semver_and_in_changelog():
    assert re.fullmatch(r"\d+\.\d+\.\d+", sipl.__version__)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{sipl.__version__}]" in changelog

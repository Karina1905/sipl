import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "conformance" / "run_conformance.py"


def test_conformance_suite_passes():
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--impl", f"{sys.executable} -m sipl"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "conformance cases passed" in proc.stdout


def test_runner_detects_wrong_implementation(tmp_path):
    fake = tmp_path / "fake_impl.py"
    fake.write_text(
        "import json\n"
        "print(json.dumps({'schema_version': 1, 'ok': True, 'status': 'ok', 'state': {},"
        " 'ast': {}}))\n"
    )
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--impl", f"{sys.executable} {fake}", "-k", "00"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1 and "FAIL" in proc.stdout

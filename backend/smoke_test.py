"""Offline smoke: sandbox + executor. Optional full job if OPENAI_API_KEY is set."""
from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.executor import run_script  # noqa: E402
from app.sandbox import SandboxError, validate_code  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample.csv"

SAFE = '''
import matplotlib
matplotlib.use("Agg")
import pandas as pd
import matplotlib.pyplot as plt
df = pd.read_csv("data.csv")
plt.figure(figsize=(6, 4))
plt.plot([1, 2, 3], [1, 2, 3])
plt.savefig("v1.0.png", dpi=80)
'''

BAD = "import os\nos.system('echo hi')\n"


def test_sandbox() -> None:
    validate_code(SAFE)
    try:
        validate_code(BAD)
    except SandboxError:
        return
    raise SystemExit("sandbox should reject os.system")


def test_executor() -> None:
    if not SAMPLE.is_file():
        raise SystemExit(f"missing {SAMPLE}")
    tmp = Path(tempfile.mkdtemp())
    try:
        shutil.copy(SAMPLE, tmp / "data.csv")
        (tmp / "v1.0.py").write_text(SAFE, encoding="utf-8")
        result = run_script(tmp, "v1.0.py", "v1.0.png")
        if not result.ok:
            raise SystemExit(f"executor failed: {result.error}\n{result.stderr}")
        print("executor ok", result.image_bytes, "bytes")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_health() -> None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as r:
            body = r.read().decode()
        if "ok" not in body:
            raise SystemExit(body)
        print("health ok")
    except urllib.error.URLError:
        print("health skipped (backend not running)")


if __name__ == "__main__":
    test_sandbox()
    print("sandbox ok")
    test_executor()
    test_health()
    print("smoke passed")

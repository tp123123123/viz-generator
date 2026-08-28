from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .config import EXEC_TIMEOUT_SEC, PYTHON_BIN
from .models import ExecutionResult


def run_script(job_dir: Path, script_name: str, image_name: str) -> ExecutionResult:
    script = job_dir / script_name
    image = job_dir / image_name
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [PYTHON_BIN, str(script)],
            cwd=str(job_dir),
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_SEC,
            env=env,
        )
        elapsed = time.perf_counter() - started
        size = image.stat().st_size if image.is_file() else 0
        ok = proc.returncode == 0 and size > 0
        error = None
        if proc.returncode != 0:
            error = (proc.stderr or proc.stdout or "非零退出码")[:4000]
        elif size <= 0:
            error = f"未生成图片 {image_name}"
        return ExecutionResult(
            ok=ok,
            exit_code=proc.returncode,
            stdout=(proc.stdout or "")[:4000],
            stderr=(proc.stderr or "")[:4000],
            elapsed_sec=round(elapsed, 3),
            image_path=image_name if size > 0 else None,
            image_bytes=size,
            error=error,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            ok=False,
            exit_code=None,
            elapsed_sec=float(EXEC_TIMEOUT_SEC),
            error=f"执行超时（{EXEC_TIMEOUT_SEC}s）",
        )
    except OSError as exc:
        return ExecutionResult(ok=False, error=str(exc))

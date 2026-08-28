from __future__ import annotations

import threading
import traceback
from pathlib import Path

from . import coder, critic, executor
from .config import MAX_CSV_BYTES, MAX_ITERATIONS, RUNS_DIR
from .llm import LLMNotConfigured
from .models import JobState, VersionRecord
from .sandbox import SandboxError, validate_code

_jobs: dict[str, JobState] = {}
_lock = threading.Lock()


def job_dir(job_id: str) -> Path:
    return RUNS_DIR / job_id


def get_job(job_id: str) -> JobState | None:
    with _lock:
        cached = _jobs.get(job_id)
    if cached:
        return cached
    disk = job_dir(job_id) / "state.json"
    if not disk.is_file():
        return None
    state = JobState.model_validate_json(disk.read_text(encoding="utf-8"))
    with _lock:
        _jobs[job_id] = state
    return state


def _save(state: JobState) -> None:
    path = job_dir(state.id) / "state.json"
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def _update(state: JobState) -> None:
    with _lock:
        _jobs[state.id] = state
    _save(state)


def _csv_preview(path: Path, limit: int = 20) -> str:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    return "\n".join(lines[:limit])


def _version_name(index: int) -> str:
    return f"v1.{index}"


def _last_code(state: JobState, d: Path) -> str | None:
    for rec in reversed(state.versions):
        p = d / rec.script_name
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return None


def create_job(prompt: str, csv_bytes: bytes, filename: str) -> JobState:
    import uuid

    if not prompt.strip():
        raise ValueError("需求不能为空")
    if not csv_bytes:
        raise ValueError("请上传 CSV")
    if len(csv_bytes) > MAX_CSV_BYTES:
        raise ValueError("CSV 过大")
    if not filename.lower().endswith(".csv"):
        raise ValueError("仅支持 .csv")

    job_id = uuid.uuid4().hex[:12]
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "data.csv").write_bytes(csv_bytes)
    state = JobState(id=job_id, prompt=prompt.strip(), max_iterations=MAX_ITERATIONS)
    _update(state)
    threading.Thread(target=_run_loop, args=(job_id, None), daemon=True).start()
    return state


def accept_job(job_id: str) -> JobState:
    state = get_job(job_id)
    if not state:
        raise ValueError("作业不存在")
    if state.status not in {"succeeded", "failed"}:
        raise ValueError("迭代尚未结束，无法确认")
    state.human_review = "accepted"
    state.stop_reason = "人工确认满意"
    _update(state)
    return state


def revise_job(job_id: str, feedback: str) -> JobState:
    state = get_job(job_id)
    if not state:
        raise ValueError("作业不存在")
    if state.status not in {"succeeded", "failed"}:
        raise ValueError("迭代尚未结束，无法提交改进")
    if state.human_review == "accepted":
        raise ValueError("已确认满意，如需重做请新建作业")
    text = feedback.strip()
    if not text:
        raise ValueError("请填写改进建议或新需求")
    state.human_notes.append(text)
    state.human_review = "none"
    state.error = None
    state.status = "queued"
    state.stop_reason = "根据人工反馈继续迭代"
    _update(state)
    threading.Thread(target=_run_loop, args=(job_id, text), daemon=True).start()
    return state


def _suggestions(state: JobState) -> str | None:
    finished = [v for v in state.versions if v.review]
    if not finished:
        return None
    last = finished[-1]
    if not last.review.issues:
        return None
    lines = [f"- {i.description} | {i.severity} | {i.suggestion}" for i in last.review.issues]
    if last.review.next_advice:
        lines.append(f"总体: {last.review.next_advice}")
    return "\n".join(lines)


def _finish_for_human(state: JobState, rec: VersionRecord, reason: str) -> None:
    state.status = "succeeded"
    state.stop_reason = reason
    state.human_review = "awaiting"
    rec.stage = "done"
    _update(state)


def _run_loop(job_id: str, extra_suggestions: str | None) -> None:
    state = get_job(job_id)
    if not state:
        return
    d = job_dir(job_id)
    csv_path = d / "data.csv"
    preview = _csv_preview(csv_path)
    exec_fails = 0
    previous_code = _last_code(state, d)
    started_len = len(state.versions)

    try:
        for round_i in range(MAX_ITERATIONS):
            index = started_len + round_i
            version = _version_name(index)
            script_name = f"{version}.py"
            image_name = f"{version}.png"
            rec = VersionRecord(
                version=version,
                iteration=index,
                script_name=script_name,
                stage="coding",
            )
            state.iteration = index
            state.current_version = version
            state.status = "coding"
            state.human_review = "none"
            state.versions.append(rec)
            _update(state)

            if round_i == 0 and extra_suggestions:
                suggestions = "人工反馈（必须落实）:\n" + extra_suggestions
            elif index == 0:
                suggestions = None
            else:
                suggestions = _suggestions(state)

            rec.stage = "coding"
            code = coder.generate_script(
                user_prompt=state.prompt,
                csv_preview=preview,
                version=version,
                image_name=image_name,
                previous_code=previous_code,
                review_suggestions=suggestions,
            )
            validate_code(code)
            (d / script_name).write_text(code, encoding="utf-8")
            previous_code = code

            state.status = "executing"
            rec.stage = "executing"
            _update(state)
            rec.execution = executor.run_script(d, script_name, image_name)
            rec.image_name = rec.execution.image_path
            if not rec.execution.ok:
                exec_fails += 1
            else:
                exec_fails = 0

            if exec_fails >= 2:
                state.status = "failed"
                state.error = rec.execution.error or "连续两次执行失败"
                state.stop_reason = "连续 2 次执行失败"
                state.human_review = "awaiting"
                rec.stage = "failed"
                _update(state)
                return

            state.status = "reviewing"
            rec.stage = "reviewing"
            _update(state)
            image_bytes = None
            img = d / image_name
            if img.is_file():
                image_bytes = img.read_bytes()
            rec.review = critic.review(
                user_prompt=state.prompt,
                version=version,
                code=code,
                execution=rec.execution,
                image_bytes=image_bytes,
            )

            if rec.review.passed:
                _finish_for_human(state, rec, "审查通过，等待人工确认")
                return

            if round_i >= MAX_ITERATIONS - 1:
                _finish_for_human(state, rec, "本轮自动迭代结束，等待人工确认")
                return

            state.status = "iterating"
            rec.stage = "iterating"
            _update(state)

        _finish_for_human(state, state.versions[-1], "本轮自动迭代结束，等待人工确认")
    except LLMNotConfigured as exc:
        state.status = "failed"
        state.error = str(exc)
        state.stop_reason = "未配置模型密钥"
        state.human_review = "awaiting"
        _update(state)
    except SandboxError as exc:
        state.status = "failed"
        state.error = str(exc)
        state.stop_reason = "代码未通过安全检查"
        state.human_review = "awaiting"
        _update(state)
    except Exception as exc:
        state.status = "failed"
        state.error = f"{exc}\n{traceback.format_exc()[-1500:]}"
        state.stop_reason = "内部错误"
        state.human_review = "awaiting"
        _update(state)

from __future__ import annotations

import json
from pathlib import Path

from .llm import chat_vision, extract_json
from .models import ExecutionResult, Issue, ReviewResult

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "critic.md"


def _system() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _passed(verdict: str, acc: float, cla: float, aes: float, issues: list[Issue]) -> bool:
    if any(i.severity == "高" for i in issues):
        return False
    if verdict != "通过":
        return False
    return acc >= 7 and cla >= 7 and aes >= 7


def review(
    *,
    user_prompt: str,
    version: str,
    code: str,
    execution: ExecutionResult,
    image_bytes: bytes | None,
) -> ReviewResult:
    if not image_bytes or not execution.ok:
        issues = [
            Issue(
                description=execution.error or "执行失败或未生成图片",
                severity="高",
                suggestion="修复运行错误，确保 savefig 写出指定 png 且退出码为 0",
            )
        ]
        return ReviewResult(
            verdict="不通过",
            accuracy=0,
            clarity=0,
            aesthetics=0,
            total=0,
            passed=False,
            issues=issues,
            summary="无法审查图片",
            next_advice="先让脚本成功出图",
        )

    user = "\n".join(
        [
            f"用户需求: {user_prompt}",
            f"代码版本: {version}",
            f"退出码: {execution.exit_code}",
            f"stderr: {execution.stderr[:2000]}",
            "代码:",
            code[:8000],
        ]
    )
    raw = chat_vision(_system(), user, image_bytes)
    try:
        data = extract_json(raw)
    except (ValueError, json.JSONDecodeError):
        return ReviewResult(
            verdict="不通过",
            accuracy=5,
            clarity=5,
            aesthetics=5,
            total=5,
            passed=False,
            issues=[
                Issue(
                    description="审查模型返回了无法解析的 JSON",
                    severity="中",
                    suggestion="保持图表逻辑，仅做小幅可读性优化后重新出图",
                )
            ],
            summary="自动审查解析失败，本轮视为未通过，可按建议继续或请人工确认",
            next_advice="继续优化可读性，或等待人工审查",
        )
    issues = []
    for item in data.get("issues") or []:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "中")
        if sev.lower() in {"high", "h"}:
            sev = "高"
        elif sev.lower() in {"medium", "m", "mid"}:
            sev = "中"
        elif sev.lower() in {"low", "l"}:
            sev = "低"
        if sev not in {"高", "中", "低"}:
            sev = "中"
        issues.append(
            Issue(
                description=str(item.get("description") or item.get("problem") or ""),
                severity=sev,  # type: ignore[arg-type]
                suggestion=str(item.get("suggestion") or ""),
            )
        )
    acc = float(data.get("accuracy", 0))
    cla = float(data.get("clarity", 0))
    aes = float(data.get("aesthetics", 0))
    total = float(data.get("total") or round((acc + cla + aes) / 3, 2))
    verdict = str(data.get("verdict") or "不通过")
    if verdict not in ("通过", "有条件通过", "不通过"):
        verdict = "不通过"
    return ReviewResult(
        verdict=verdict,  # type: ignore[arg-type]
        accuracy=acc,
        clarity=cla,
        aesthetics=aes,
        total=total,
        passed=_passed(verdict, acc, cla, aes, issues),
        issues=issues,
        summary=str(data.get("summary") or ""),
        next_advice=str(data.get("next_advice") or ""),
    )

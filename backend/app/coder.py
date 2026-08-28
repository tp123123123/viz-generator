from __future__ import annotations

from pathlib import Path

from .llm import chat_text, extract_python

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "coder.md"


def _system() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def generate_script(
    *,
    user_prompt: str,
    csv_preview: str,
    version: str,
    image_name: str,
    previous_code: str | None = None,
    review_suggestions: str | None = None,
) -> str:
    task = "优化修改" if previous_code else "初次生成"
    parts = [
        f"任务类型: {task}",
        f"代码版本: {version}",
        f"图片文件名: {image_name}",
        f"用户需求: {user_prompt}",
        "数据文件: data.csv",
        "数据预览:",
        csv_preview,
    ]
    if review_suggestions:
        parts.extend(["改进建议（必须逐条落实）:", review_suggestions])
    if previous_code:
        parts.extend(["上次代码:", previous_code])
    return extract_python(chat_text(_system(), "\n\n".join(parts)))

from __future__ import annotations

import ast
from typing import Iterable

FORBIDDEN_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "pathlib",
    "ctypes",
    "multiprocessing",
    "importlib",
    "pickle",
    "pty",
    "signal",
    "webbrowser",
    "tempfile",
}

FORBIDDEN_NAMES = {"eval", "exec", "compile", "__import__", "breakpoint"}


class SandboxError(ValueError):
    pass


def _iter_imported_modules(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module.split(".")[0]


def validate_code(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SandboxError(f"语法错误: {exc}") from exc

    for mod in _iter_imported_modules(tree):
        if mod in FORBIDDEN_MODULES:
            raise SandboxError(f"禁止导入模块: {mod}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise SandboxError(f"禁止使用: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr in {"system", "popen", "rmtree"}:
            raise SandboxError(f"禁止调用: {node.attr}")

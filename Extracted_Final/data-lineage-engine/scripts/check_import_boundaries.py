"""Import-boundary check (Pack Section 18). Exit code 1 on any violation.

Absolute imports only. Rules are prefix-based, on module names.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List

RULES = [
    ("research/", ["backend", "frontend"]),
    ("research/reasoning/", ["research.ground_truth", "contracts.truth", "contracts.interfaces", "contracts.mocks", "ingestion"]),
    ("research/baselines/", ["research.ground_truth", "contracts.truth", "contracts.interfaces", "contracts.mocks", "ingestion"]),
    ("research/ground_truth/", ["ingestion", "sqlglot", "research.reasoning", "research.baselines"]),
]


def _modules(tree: ast.AST) -> List[str]:
    mods: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.append(node.module)
            mods += [f"{node.module}.{a.name}" for a in node.names]
    return mods


def _hit(mod: str, prefix: str) -> bool:
    return mod == prefix or mod.startswith(prefix + ".")


def check(root: Path) -> List[str]:
    problems: List[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if "/.venv/" in rel or rel.startswith("."):
            continue
        applicable = [(p, forb) for p, forb in RULES if rel.startswith(p)]
        if not applicable:
            continue
        try:
            mods = _modules(ast.parse(path.read_text(encoding="utf8")))
        except SyntaxError as e:
            problems.append(f"{rel}: cannot parse ({e})")
            continue
        for prefix, forbidden in applicable:
            for f in forbidden:
                hit = next((m for m in mods if _hit(m, f)), None)
                if hit:
                    problems.append(f"{rel}: imports {hit} (forbidden under {prefix})")
    return sorted(set(problems))


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    issues = check(root)
    for i in issues:
        print("VIOLATION:", i)
    print("import boundaries:", "FAILED" if issues else "ok")
    sys.exit(1 if issues else 0)

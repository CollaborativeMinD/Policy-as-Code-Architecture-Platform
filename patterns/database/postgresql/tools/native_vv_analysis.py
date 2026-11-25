"""Fresh compiler and analyzer observations, with source identity held constant."""

import ast
import os
from pathlib import Path

from .admission_evidence import source_snapshot, write_json
from .admission_harness import binary_identity
from .admission_process import run_command
from .admission_structure import check_structure


def fresh_analysis(root, output, interpreter, source_digest):
    interpreter = Path(interpreter).absolute()
    if not interpreter.is_file():
        raise ValueError("ANALYZER_INTERPRETER_MISSING")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment["PATH"] = str(interpreter.parent) + os.pathsep + environment.get("PATH", "")
    checks = {}
    commands = {
        "ruff": ["-m", "ruff", "check", "src"],
        "mypy": ["-m", "mypy", "src/hmt_pg_patterns"],
        "pyrefly": ["-m", "pyrefly", "check", "src/hmt_pg_patterns"],
    }
    for name, arguments in commands.items():
        folder = output / name
        folder.mkdir()
        checks[name] = run_command([str(interpreter), *arguments], root, folder, environment, 120)
        write_json(folder / "receipt.json", checks[name])
    checks["structure"] = check_structure(root)
    checks["current_source"] = {
        "status": "PASS" if source_snapshot(root)["source_digest"] == source_digest else "FAIL"
    }
    result = {
        "id": "POWER10:ANALYZERS",
        "method": "executed",
        "source_digest": source_digest,
        "passed": all(row["status"] == "PASS" for row in checks.values()),
        "actual": checks,
        "interpreter": binary_identity(interpreter),
    }
    write_json(output / "analysis.json", result)
    return result


def observations(root):
    from hmt_policy.codec import digest

    result = []
    for path in sorted((root / "src/hmt_pg_patterns").glob("*.py")):
        tree = ast.parse(path.read_text())
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.comprehension, ast.Global)):
                position = node
                while not hasattr(position, "lineno"):
                    position = parents[position]
                result.append(
                    {
                        "rule": "P10-06" if isinstance(node, ast.Global) else "P10-02",
                        "line": position.lineno,
                        "path": path.relative_to(root).as_posix(),
                        "mechanism": "mutable_global"
                        if isinstance(node, ast.Global)
                        else "loop_bound",
                        "ast_digest": digest(ast.dump(node)),
                    }
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "compile"}:
                    result.append({"rule": "P10-01", "line": node.lineno, "blocked": True})
    return result

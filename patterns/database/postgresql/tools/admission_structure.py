"""PG-ADMIT-001: current-policy physical LOC, control depth, and test integrity."""

import ast
from pathlib import Path


def band(size, function=False):
    thresholds = (45, 50, 60) if function else (100, 150, 180)
    labels = ("NOMINAL", "WATCH", "REFACTOR_REQUIRED", "BLOCK")
    return labels[sum(size >= value for value in thresholds)]


def control_depth(node, level=0):
    controls = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Match,
    )
    depth = level + isinstance(node, controls)
    return max([depth, *(control_depth(child, depth) for child in ast.iter_child_nodes(node))])


def function_metrics(node):
    arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    implicit = bool(arguments and arguments[0].arg in {"self", "cls"})
    size = node.end_lineno - node.lineno + 1
    return {
        "name": node.name,
        "line": node.lineno,
        "physical_loc": size,
        "band": band(size, True),
        "arguments": len(arguments) - implicit,
        "control_depth": control_depth(node),
    }


def suppressed(tree):
    names = {"skip", "skipif", "xfail", "skipIf", "skipUnless", "expectedFailure"}
    aliases = set(names)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(item.asname or item.name for item in node.names if item.name in names)
    return any(
        (isinstance(node, ast.Attribute) and node.attr in names)
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in aliases
        )
        for node in ast.walk(tree)
    )


def inspect_file(path, root):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    functions = [
        function_metrics(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    record = {
        "path": path.relative_to(root).as_posix(),
        "physical_loc": len(lines),
        "counted_loc": sum(
            bool(line.strip()) and not line.lstrip().startswith("#") for line in lines
        ),
        "band": band(len(lines)),
        "functions": functions,
        "test_suppression": suppressed(tree),
    }
    return record


def violations(record):
    findings = []
    if record["band"] in {"REFACTOR_REQUIRED", "BLOCK"}:
        findings.append("MODULE_LOC_" + record["band"])
    if record["test_suppression"]:
        findings.append("TEST_SUPPRESSION")
    for item in record["functions"]:
        if item["band"] in {"REFACTOR_REQUIRED", "BLOCK"}:
            findings.append(item["name"] + ":FUNCTION_LOC_" + item["band"])
        if item["arguments"] > 5 or item["control_depth"] > 5:
            findings.append(item["name"] + ":ARGUMENT_OR_NESTING_LIMIT")
    return findings


def check_structure(root):
    root = Path(root).resolve()
    paths = sorted(
        path for folder in ("src", "tests", "tools") for path in (root / folder).rglob("*.py")
    )
    records, errors = [], []
    if not list((root / "src").rglob("*.py")):
        errors.append({"path": "src", "reason": "EMPTY_PRODUCTION_SOURCE"})
    for path in paths:
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("SOURCE_LINK_OR_ESCAPE")
            record = inspect_file(path, root)
            records.append(record)
            errors.extend(
                {"path": record["path"], "reason": reason} for reason in violations(record)
            )
        except (OSError, ValueError, SyntaxError, UnicodeError) as error:
            errors.append({"path": str(path), "reason": type(error).__name__})
    return {
        "status": "FAIL" if errors else "PASS",
        "files": records,
        "errors": errors,
        "metric": "physical lines including comments and blanks",
        "watch_count": sum(row["band"] == "WATCH" for row in records),
    }

"""
Pre-commit hook: every Pydantic/SQLModel model must document its own fields.

Statically parses (never imports) the given Python sources, so it needs no
installed project dependencies. A model's docstring must carry a
``:param <field>:`` line for every field the class declares itself; fields
inherited from another model are documented on that model instead.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_MODEL_BASES = ("BaseModel", "SQLModel", "RootModel")
_DEFAULT_EXCLUDE = r"(^|/)(tests?|\.?venv|\.git|build|node_modules)/"


@dataclass
class _ClassInfo:
    location: str
    bases: list[str]
    fields: list[str]
    docstring: str
    parents: list[_ClassInfo] = field(default_factory=list)


def _base_name(node: ast.expr) -> str | None:
    """
    Simple name of a base class expression.

    :param node: Base expression, e.g. ``BaseModel``, ``sqlmodel.SQLModel`` or
        ``RootModel[int]``.

    :return: The last name component, or ``None`` if it has none.
    """
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_class_var(annotation: ast.expr) -> bool:
    return _base_name(annotation) == "ClassVar"


def _is_relationship(value: ast.expr | None) -> bool:
    # SQLModel relationships are not fields (absent from ``model_fields``).
    return isinstance(value, ast.Call) and _base_name(value.func) == "Relationship"


def _python_files(paths: Sequence[str], exclude: re.Pattern[str]) -> list[Path]:
    """
    Expand the given files and directories into the Python files to parse.

    :param paths: Files or directories to scan.
    :param exclude: Pattern matched against each file's POSIX path to skip it.

    :return: Sorted, de-duplicated Python files.
    """
    files: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        candidates = path.rglob("*.py") if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.suffix == ".py" and not exclude.search(candidate.as_posix()):
                files.add(candidate)
    return sorted(files)


def _collect_classes(
    files: Sequence[Path], errors: list[str]
) -> dict[str, list[_ClassInfo]]:
    """
    Parse the given files and collect all class definitions.

    :param files: Python files to parse.
    :param errors: Receives a message for every file that fails to parse.

    :return: Class infos keyed by simple class name.
    """
    classes: dict[str, list[_ClassInfo]] = {}
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as error:
            errors.append(f"{path}: failed to parse: {error}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            fields = [
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and not stmt.target.id.startswith("_")
                and stmt.target.id != "model_config"
                and not _is_class_var(stmt.annotation)
                and not _is_relationship(stmt.value)
            ]
            info = _ClassInfo(
                location=f"{path.as_posix()}:{node.lineno}",
                bases=[b for b in map(_base_name, node.bases) if b],
                fields=fields,
                docstring=ast.get_docstring(node) or "",
            )
            classes.setdefault(node.name, []).append(info)
    return classes


def _find_models(
    classes: dict[str, list[_ClassInfo]], model_bases: Sequence[str]
) -> list[_ClassInfo]:
    """
    Resolve which classes are models, following base classes across files by
    simple name.

    :param classes: Class infos keyed by simple class name.
    :param model_bases: Names of the root model classes.

    :return: Every class that is (transitively) a model.
    """
    model_names = set(model_bases)
    changed = True
    while changed:
        changed = False
        for name, infos in classes.items():
            if name in model_names:
                continue
            if any(base in model_names for info in infos for base in info.bases):
                model_names.add(name)
                changed = True

    models = []
    for infos in classes.values():
        for info in infos:
            if any(base in model_names for base in info.bases):
                info.parents = [p for b in info.bases for p in classes.get(b, [])]
                models.append(info)
    return models


def _inherited_fields(info: _ClassInfo, seen: set[int] | None = None) -> set[str]:
    # ``seen`` stops the recursion on name-based cycles, e.g. ``class A(x.A)``.
    seen = {id(info)} if seen is None else seen
    inherited: set[str] = set()
    for parent in info.parents:
        if id(parent) in seen:
            continue
        seen.add(id(parent))
        inherited |= set(parent.fields) | _inherited_fields(parent, seen)
    return inherited


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan (default: current directory).",
    )
    parser.add_argument(
        "--exclude",
        default=_DEFAULT_EXCLUDE,
        help="Regex matched against file paths to skip them.",
    )
    parser.add_argument(
        "--model-base",
        action="append",
        dest="model_bases",
        help="Root model class name; repeatable "
        f"(default: {', '.join(_DEFAULT_MODEL_BASES)}).",
    )
    args = parser.parse_args(argv)

    violations: list[str] = []
    files = _python_files(args.paths, re.compile(args.exclude))
    classes = _collect_classes(files, violations)
    models = _find_models(classes, args.model_bases or _DEFAULT_MODEL_BASES)
    for model in models:
        if not model.docstring.strip():
            violations.append(f"{model.location}: no docstring")
            continue
        inherited = _inherited_fields(model)
        missing = [
            name
            for name in model.fields
            if name not in inherited and f":param {name}:" not in model.docstring
        ]
        if missing:
            violations.append(f"{model.location}: missing :param: for {missing}")

    for violation in sorted(violations):
        print(violation)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())

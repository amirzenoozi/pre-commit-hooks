from pathlib import Path

import pytest

from pre_commit_hooks.check_model_docstrings import main


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def _run(root: Path, capsys: pytest.CaptureFixture[str], *args: str):
    code = main([str(root), *args])
    lines = capsys.readouterr().out.splitlines()
    return code, [line.split(": ", 1)[1] for line in lines]


def test_documented_model_passes(tmp_path, capsys):
    _write(
        tmp_path,
        "models.py",
        '''
from pydantic import BaseModel

class User(BaseModel):
    """A user.

    :param name: Name of the user.
    """

    name: str
''',
    )
    assert _run(tmp_path, capsys) == (0, [])


def test_missing_docstring_and_param_fail(tmp_path, capsys):
    _write(
        tmp_path,
        "models.py",
        '''
from pydantic import BaseModel

class NoDoc(BaseModel):
    a: int

class Partial(BaseModel):
    """Partial.

    :param a: A.
    """

    a: int
    b: int
''',
    )
    code, violations = _run(tmp_path, capsys)
    assert code == 1
    assert sorted(violations) == ["missing :param: for ['b']", "no docstring"]


def test_inherited_fields_across_files_are_not_required(tmp_path, capsys):
    _write(
        tmp_path,
        "base.py",
        '''
from pydantic import BaseModel

class Base(BaseModel):
    """Base.

    :param a: A.
    """

    a: int
''',
    )
    _write(
        tmp_path,
        "child.py",
        '''
from base import Base

class Child(Base):
    """Child.

    :param b: B.
    """

    a: int
    b: int
''',
    )
    assert _run(tmp_path, capsys) == (0, [])


def test_non_field_attributes_are_skipped(tmp_path, capsys):
    _write(
        tmp_path,
        "models.py",
        '''
from typing import ClassVar

from pydantic import ConfigDict
from sqlmodel import Relationship, SQLModel

class Team(SQLModel, table=True):
    """Team."""

    model_config = ConfigDict()
    _cache: dict
    KIND: ClassVar[str] = "team"
    members: list["Member"] = Relationship(back_populates="team")
''',
    )
    assert _run(tmp_path, capsys) == (0, [])


def test_non_model_classes_are_ignored(tmp_path, capsys):
    _write(tmp_path, "plain.py", "class Plain:\n    a: int\n")
    assert _run(tmp_path, capsys) == (0, [])


def test_excluded_paths_are_skipped(tmp_path, capsys):
    model = "from pydantic import BaseModel\nclass T(BaseModel):\n    a: int\n"
    _write(tmp_path, "tests/test_models.py", model)
    assert _run(tmp_path, capsys) == (0, [])

    _write(tmp_path, "generated/models.py", model)
    assert _run(tmp_path, capsys, "--exclude", "generated/|tests/")[0] == 0


def test_custom_model_base(tmp_path, capsys):
    _write(tmp_path, "models.py", "class Custom(MyBase):\n    a: int\n")
    assert _run(tmp_path, capsys) == (0, [])
    assert _run(tmp_path, capsys, "--model-base", "MyBase") == (1, ["no docstring"])


def test_syntax_error_is_reported(tmp_path, capsys):
    _write(tmp_path, "broken.py", "class Broken(\n")
    code, violations = _run(tmp_path, capsys)
    assert code == 1
    assert violations[0].startswith("failed to parse")


def test_self_referencing_base_does_not_recurse(tmp_path, capsys):
    _write(
        tmp_path,
        "models.py",
        '''
import other
from pydantic import BaseModel

class Loop(other.Loop, BaseModel):
    """Loop.

    :param a: A.
    """

    a: int
''',
    )
    assert _run(tmp_path, capsys) == (0, [])

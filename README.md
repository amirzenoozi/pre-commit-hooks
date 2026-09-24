# pre-commit-hooks

Static [pre-commit](https://pre-commit.com) hooks for Python projects. The hooks
parse source code with `ast` and never import it, so they need none of the
checked project's dependencies and run in milliseconds.

## Hooks

### `check-model-docstrings`

Every [Pydantic](https://docs.pydantic.dev) / [SQLModel](https://sqlmodel.tiangolo.com)
model must have a docstring with a Sphinx-style `:param <field>:` line for each
field it declares itself.

```python
class User(BaseModel):
    """
    A registered user.

    :param name: Display name of the user.
    :param email: Contact email address.
    """

    name: str
    email: str | None = None
```

**What counts as a model:** any class whose base is `BaseModel`, `SQLModel` or
`RootModel` (plain or dotted, e.g. `sqlmodel.SQLModel`), or whose base is another
model found in the scanned files, however deep the chain. Bases are matched by
simple class name across all scanned files.

**What counts as a field:** each annotated attribute in the class body
(`name: type` or `name: type = default`), except:

- fields inherited from a parent model (document them on the parent),
- private attributes (`_name`),
- `model_config`,
- `ClassVar[...]` attributes,
- SQLModel `Relationship(...)` attributes.

**Output:** one line per violation, then exit code `1`:

```
app/models.py:12: no docstring
app/models.py:30: missing :param: for ['email']
```

## Usage

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/amirzenoozi/pre-commit-hooks
    rev: v0.1.0
    hooks:
      - id: check-model-docstrings
        # Directories (or files) to scan; defaults to the whole repository.
        args: [ src/ ]
```

The hook always scans every path in `args`, not only the changed files, because
a model's parent can live in another file. Use `files:` to run it only when
relevant files change:

```yaml
      - id: check-model-docstrings
        args: [ src/ ]
        files: ^src/.*\.py$
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `PATH ...` | `.` | Files or directories to scan. |
| `--exclude REGEX` | `(^\|/)(tests?\|\.?venv\|\.git\|build\|node_modules)/` | Skip files whose POSIX path matches. |
| `--model-base NAME` | `BaseModel`, `SQLModel`, `RootModel` | Root model class name. Repeatable; replaces the defaults. |

### Command line

```bash
pip install git+https://github.com/amirzenoozi/pre-commit-hooks@v0.1.0
check-model-docstrings src/ --exclude 'migrations/'
```

## Limitations

- Bases are matched by simple name, so two unrelated classes with the same name
  are treated as one when resolving inheritance.
- Only fields written as annotated class attributes are detected; fields
  created dynamically (e.g. `create_model(...)`) are not.
- Requires Python 3.9+.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]" pre-commit
pre-commit install
pytest -v
pre-commit run --all-files
```

Try a hook against another repository without releasing it:

```bash
cd /path/to/other/repo
pre-commit try-repo /path/to/pre-commit-hooks check-model-docstrings --all-files
```

### Releasing

1. Move the `Unreleased` entries in [CHANGELOG.md](CHANGELOG.md) under a new version.
2. Bump `version` in `pyproject.toml`.
3. Commit, then tag and push: `git tag vX.Y.Z && git push origin main --tags`.
4. Consumers update with `pre-commit autoupdate`.

## License

[MIT](LICENSE)

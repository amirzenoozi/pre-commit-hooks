# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-09-24

### Fixed

- Exit with an error when a given path does not exist or contains no Python
  files, instead of passing without checking anything (e.g. after a package
  directory is renamed).

## [0.1.0] - 2026-09-24

### Added

- `check-model-docstrings` hook: every Pydantic/SQLModel model must have a
  docstring with a `:param <field>:` line for each field it declares itself.
  - Static (AST) check; never imports the checked code.
  - Resolves model inheritance across files by class name.
  - Skips inherited fields, private attributes, `ClassVar`, `model_config` and
    SQLModel `Relationship(...)` attributes.
  - `--exclude` and `--model-base` options.

[Unreleased]: https://github.com/amirzenoozi/pre-commit-hooks/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/amirzenoozi/pre-commit-hooks/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/amirzenoozi/pre-commit-hooks/releases/tag/v0.1.0

# Python Development Standard

## Purpose

Use this standard when adding or changing Python code. Keep Python projects easy to read, type-aware where useful, testable, and configured through standard project files.

## Source Baseline

- [PEP 8: Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [Python Packaging User Guide: declaring project metadata](https://packaging.python.org/specifications/declaring-project-metadata/)
- [Typing documentation: best practices](https://typing.python.org/en/latest/reference/best_practices.html)
- [pytest: good integration practices](https://pytest.org/en/7.4.x/goodpractices.html)

## Rules

1. Follow PEP 8 for naming, imports, whitespace, and code layout unless the existing project already has a stricter local rule.
2. Prefer a `pyproject.toml` for project metadata and tool configuration once the project has Python dependencies, packaging, linting, formatting, or tests.
3. Use type hints on public functions, cross-module boundaries, and non-obvious data structures. Avoid noisy annotations that do not improve understanding.
4. Keep side effects out of import time. Put executable behavior behind functions or explicit entrypoints.
5. Prefer small modules with clear ownership. Avoid large utility buckets that mix unrelated concerns.
6. Use explicit exceptions and error messages. Do not silently swallow errors unless the caller explicitly requested best-effort behavior.
7. Keep tests close to observable behavior. Use `pytest` for new Python test suites unless the project already standardizes on another runner.
8. Add dependencies deliberately. Each new runtime dependency should solve a real problem and fit the project size.

## Expected Project Shape

- Small scripts can start with a single module plus focused tests.
- Reusable Python packages should move toward `src/<package_name>/`, `tests/`, and `pyproject.toml`.
- CLI or service entrypoints should be thin and delegate business behavior to testable modules.

## Verification

When Python code exists, `./scripts/check.sh` should eventually include the project-appropriate checks, such as:

```bash
python3 -m compileall <python-source-dir>
pytest
```

Add formatting, linting, or type checking only when the project has selected tools for them.

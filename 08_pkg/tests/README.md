# Package Tests

Status: ships empty — this directory is for YOUR project's package tests.

Add test modules here when the project packages reusable code, and record the
discovery command in `PROJECT_STATE.md` (typically
`python -m unittest discover -s 08_pkg/tests`; note that discovery of an
empty directory exits non-zero on Python 3.12+, so add the command to the
validation gate only once the first test exists).

The reusable template's own behavior is covered by the top-level `tests/`
suite (`python -m unittest discover -s tests`); nothing in this directory is
required by the template. Do not invent test names or pretend future behavior
exists.

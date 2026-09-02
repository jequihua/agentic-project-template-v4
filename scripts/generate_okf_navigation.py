#!/usr/bin/env python3
"""Deterministic, disposable OKF-backbone navigation-view generator.

Renders one fixed navigation read model, ``08_pkg/generated/okf_navigation.md``,
from one explicit human-authored manifest, ``08_pkg/okf_navigation_manifest.json``.
The view lowers the cost of locating canonical sources; it is never canonical, never
copies live state, and loses no information when deleted.

Standard library only. PyYAML is installed for the profile checker but is neither
needed nor permitted here (the manifest is JSON). The two repository-facing commands
are::

    python scripts/generate_okf_navigation.py            # render, write only if changed
    python scripts/generate_okf_navigation.py --check     # read-only staleness check

Exit codes: generate returns 0 on success, 2 on an invalid/unsafe manifest, source,
or output state. ``--check`` returns 0 (current), 1 (missing or stale), or 2
(invalid arguments or an invalid/unsafe manifest/source/output). Expected failures
print a concise diagnostic without a traceback and leave any existing output
byte-identical.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import sys
import tempfile
from pathlib import Path

# Fixed slice paths (repository-relative, POSIX). The CLI never exposes an arbitrary
# root, manifest, source directory, or output path.
MANIFEST_REL = "08_pkg/okf_navigation_manifest.json"
OUTPUT_REL = "08_pkg/generated/okf_navigation.md"
GENERATED_DIR_REL = "08_pkg/generated"
REGEN_COMMAND = "python scripts/generate_okf_navigation.py"

MANIFEST_SCHEMA = "template.okf_navigation_manifest.v1"

# Deliberately small finite bounds: this drives exactly one modest manifest, not a
# large-repository crawler.
MAX_MANIFEST_BYTES = 16_384
MAX_GROUPS = 16
MAX_SOURCES = 64
MAX_ID_LEN = 64
MAX_TITLE_LEN = 120
MAX_LABEL_LEN = 120
MAX_PATH_LEN = 256

_TOP_KEYS = {"manifest_schema", "view_id", "title", "output_path", "groups"}
_GROUP_KEYS = {"group_id", "title", "sources"}
_SOURCE_KEYS = {"path", "label"}

# Non-rendered identifiers must be diagnostic-safe ASCII so control/line content
# cannot enter error messages.
_IDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
# A portable source-path segment: starts with an ASCII letter or digit, then ASCII
# letters/digits/dots/underscores/hyphens (final-dot rejection is enforced separately).
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Markdown structure delimiters that must never appear in a rendered value. Rejection
# (not escaping) keeps the current benign output byte-identical.
_FORBIDDEN_MARKDOWN = ("\\", "`", "[", "]", "<", ">")


class NavError(Exception):
    """An expected, reportable generation failure (invalid/unsafe input or state)."""


def repo_root() -> Path:
    """Resolve the repository root independently of the caller's directory."""
    return Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def _need_str(value: object, what: str, limit: int) -> str:
    if not isinstance(value, str):
        raise NavError(f"{what} must be a string")
    if not value:
        raise NavError(f"{what} must not be empty")
    if len(value) > limit:
        raise NavError(f"{what} exceeds the {limit}-character limit")
    return value


def _need_ident(value: object, what: str, limit: int) -> str:
    """A non-rendered identifier: a valid string within bound and diagnostic-safe
    ASCII (`[A-Za-z0-9][A-Za-z0-9_-]*`)."""
    text = _need_str(value, what, limit)
    if not _IDENT_RE.match(text):
        raise NavError(f"{what} must match [A-Za-z0-9][A-Za-z0-9_-]*")
    return text


def _need_rendered_text(value: object, what: str, limit: int) -> str:
    """A value rendered into a heading or link: a valid string within bound that is
    stripped, single-line, entirely printable (no CR/LF/tab/NUL/control/format
    character), and free of the Markdown structure delimiters. Unsafe values are
    rejected, never trimmed, normalized, or escaped."""
    text = _need_str(value, what, limit)
    if text != text.strip():
        raise NavError(f"{what} must not have leading or trailing whitespace")
    if not text.isprintable():
        raise NavError(f"{what} must be a single line of printable characters")
    hit = next((d for d in _FORBIDDEN_MARKDOWN if d in text), None)
    if hit is not None:
        raise NavError(f"{what} must not contain the Markdown delimiter {hit!r}")
    return text


def _no_unknown_keys(obj: dict, allowed: set, what: str) -> None:
    extra = set(obj) - allowed
    if extra:
        raise NavError(f"{what} has unknown keys: {', '.join(sorted(extra))}")
    missing = allowed - set(obj)
    if missing:
        raise NavError(f"{what} is missing keys: {', '.join(sorted(missing))}")


def _validate_source_path(rel: str) -> None:
    """Reject every unsafe path form before any filesystem access."""
    if len(rel) > MAX_PATH_LEN:
        raise NavError(f"source path exceeds the {MAX_PATH_LEN}-character limit: {rel!r}")
    if "\\" in rel:
        raise NavError(f"source path must use POSIX separators, not backslashes: {rel!r}")
    if rel.startswith("/"):
        raise NavError(f"source path must be repository-relative, not absolute: {rel!r}")
    if len(rel) >= 2 and rel[1] == ":":
        raise NavError(f"source path must not be a drive-letter path: {rel!r}")
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise NavError(f"source path must not contain empty, '.', or '..' segments: {rel!r}")
    for part in parts:
        if not _SEGMENT_RE.match(part) or part.endswith("."):
            raise NavError(
                "source path segments must be portable ASCII "
                "(letter/digit start; letters/digits/dots/underscores/hyphens; "
                f"no trailing dot): {rel!r}")
    if rel == OUTPUT_REL:
        raise NavError("the generated output must not be a manifest source (output-as-input)")


def load_and_validate_manifest(root: Path) -> dict:
    """Read, size-bound, parse, and strictly validate the fixed manifest."""
    manifest_path = root / MANIFEST_REL
    try:
        raw = manifest_path.read_bytes()
    except FileNotFoundError as exc:
        raise NavError(f"manifest not found: {MANIFEST_REL}") from exc
    except OSError as exc:
        raise NavError(f"cannot read manifest {MANIFEST_REL}: {exc}") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise NavError(f"manifest exceeds the {MAX_MANIFEST_BYTES}-byte limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NavError("manifest is not valid UTF-8") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NavError(f"manifest is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise NavError("manifest root must be a JSON object")

    _no_unknown_keys(data, _TOP_KEYS, "manifest")
    if data["manifest_schema"] != MANIFEST_SCHEMA:
        raise NavError(f"unsupported manifest_schema (expected {MANIFEST_SCHEMA})")
    _need_ident(data["view_id"], "view_id", MAX_ID_LEN)
    _need_rendered_text(data["title"], "title", MAX_TITLE_LEN)
    if data["output_path"] != OUTPUT_REL:
        raise NavError(f"manifest output_path must be exactly {OUTPUT_REL}")

    groups = data["groups"]
    if not isinstance(groups, list) or not groups:
        raise NavError("manifest groups must be a non-empty list")
    if len(groups) > MAX_GROUPS:
        raise NavError(f"manifest declares more than {MAX_GROUPS} groups")

    seen_groups: set[str] = set()
    seen_paths: set[str] = set()
    total_sources = 0
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            raise NavError(f"group #{gi} must be an object")
        _no_unknown_keys(group, _GROUP_KEYS, f"group #{gi}")
        gid = _need_ident(group["group_id"], f"group #{gi} group_id", MAX_ID_LEN)
        _need_rendered_text(group["title"], f"group #{gi} title", MAX_TITLE_LEN)
        if gid in seen_groups:
            raise NavError(f"duplicate group_id: {gid}")
        seen_groups.add(gid)
        sources = group["sources"]
        if not isinstance(sources, list) or not sources:
            raise NavError(f"group {gid} sources must be a non-empty list")
        for si, source in enumerate(sources):
            if not isinstance(source, dict):
                raise NavError(f"group {gid} source #{si} must be an object")
            _no_unknown_keys(source, _SOURCE_KEYS, f"group {gid} source #{si}")
            path = _need_str(source["path"], f"group {gid} source #{si} path", MAX_PATH_LEN)
            _need_rendered_text(source["label"], f"group {gid} source #{si} label", MAX_LABEL_LEN)
            _validate_source_path(path)
            if path in seen_paths:
                raise NavError(f"duplicate source path: {path}")
            seen_paths.add(path)
            total_sources += 1
    if total_sources > MAX_SOURCES:
        raise NavError(f"manifest declares more than {MAX_SOURCES} sources")
    return data


# --------------------------------------------------------------------------- #
# Path safety
# --------------------------------------------------------------------------- #

def _within(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # different drives on Windows
        return False


def _safe_real_file(root_real: str, rel: str) -> None:
    """Confirm ``rel`` resolves to a contained, existing regular file with no
    symlink-based escape at the leaf or any parent component."""
    target = os.path.join(root_real, *rel.split("/"))
    real = os.path.realpath(target)
    if not _within(real, root_real):
        raise NavError(f"source path escapes the repository root: {rel}")
    if not os.path.exists(real):
        raise NavError(f"source path does not exist: {rel}")
    if not os.path.isfile(real):
        raise NavError(f"source path is not a regular file: {rel}")


def _safe_output_path(root_real: str) -> Path:
    """Confirm the fixed output stays beneath ``08_pkg/generated/`` with no parent or
    leaf symlink escape and is not a non-regular file, and return the concrete output
    Path.

    Any expected ``OSError`` raised while resolving or stat-inspecting the fixed
    generated directory, output, or output parent (both ``os.path.realpath`` calls and
    the existence/type/symlink checks) is translated into a ``NavError`` carrying only
    the relative fixed path and sanitized OS-error text, never a machine-local path, so
    it becomes the documented concise exit 2 rather than escaping the CLI. The
    ``NavError``s raised for a genuine unsafe/non-regular state are not ``OSError``s and
    pass through unchanged.
    """
    try:
        generated_dir = os.path.join(root_real, *GENERATED_DIR_REL.split("/"))
        if os.path.exists(generated_dir):
            real_dir = os.path.realpath(generated_dir)
            if not _within(real_dir, root_real):
                raise NavError("generated directory escapes the repository (unsafe parent)")
            if not os.path.isdir(real_dir):
                raise NavError("generated path exists but is not a directory")
        out = os.path.join(root_real, *OUTPUT_REL.split("/"))
        if os.path.islink(out):
            raise NavError("refusing to write through a symlinked output file")
        if os.path.exists(out) and not os.path.isfile(out):
            # A directory, device, or other non-regular file at the fixed output path
            # is rejected before any read/write, so it becomes the documented exit 2.
            raise NavError(f"existing output is not a regular file: {OUTPUT_REL}")
        parent_real = os.path.realpath(os.path.dirname(out))
        if not _within(parent_real, root_real):
            raise NavError("generated output parent escapes the repository root")
        return Path(out)
    except OSError as exc:
        raise NavError(f"cannot inspect output path {OUTPUT_REL}: {_oserr(exc)}") from exc


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _rel_link(from_dir_rel: str, source_rel: str) -> str:
    """A POSIX relative link from the generated file's directory to a source."""
    return posixpath.relpath(source_rel, start=from_dir_rel)


def render(data: dict) -> bytes:
    """Render the exact view bytes from an already-validated manifest.

    Order is manifest order. Output is UTF-8 with LF endings, exactly one trailing
    newline, and no timestamp, hostname, absolute path, environment value, or
    run-specific data.
    """
    from_dir = posixpath.dirname(OUTPUT_REL)
    lines: list[str] = []
    lines.append(
        f"<!-- GENERATED read model — do not edit by hand. "
        f"Source manifest: {MANIFEST_REL}. Regenerate: {REGEN_COMMAND} -->"
    )
    lines.append("")
    lines.append(f"# {data['title']}")
    lines.append("")
    lines.append("> This navigation view is **generated and disposable**. It is **not")
    lines.append("> authoritative** and intentionally does **not reproduce live project")
    lines.append("> state**. Deleting it loses no canonical information. Follow the links")
    lines.append("> below to the canonical sources; current routing lives only in")
    lines.append("> `PROJECT_STATE.md`.")
    for group in data["groups"]:
        lines.append("")
        lines.append(f"## {group['title']}")
        lines.append("")
        for source in group["sources"]:
            path = source["path"]
            label = source["label"]
            link = _rel_link(from_dir, path)
            lines.append(f"- [{label}]({link}) — `{path}`")
    text = "\n".join(lines) + "\n"
    return text.encode("utf-8")


# --------------------------------------------------------------------------- #
# Generate / check
# --------------------------------------------------------------------------- #

def expected_bytes(root: Path) -> tuple[bytes, Path]:
    """Validate manifest + every source + output safety and return (bytes, out_path).

    This is the shared, read-only core of both commands.
    """
    root_real = os.path.realpath(root)
    data = load_and_validate_manifest(root)
    for group in data["groups"]:
        for source in group["sources"]:
            _safe_real_file(root_real, source["path"])
    out_path = _safe_output_path(root_real)
    return render(data), out_path


def _oserr(exc: OSError) -> str:
    """A stable, machine-local-path-free description of a filesystem error (the
    exception type only; the raw ``str(exc)`` may embed an absolute path)."""
    return type(exc).__name__


def _read_existing_output(out_path: Path) -> bytes | None:
    """Return the existing output bytes, or ``None`` if it is absent. An expected
    existence/stat/read failure is translated to a concise ``NavError`` with a
    relative path so it becomes the documented exit 2 without a traceback."""
    try:
        if not out_path.exists():
            return None
        return out_path.read_bytes()
    except OSError as exc:
        raise NavError(f"cannot read existing output {OUTPUT_REL}: {_oserr(exc)}") from exc


def _atomic_write(out_path: Path, data: bytes) -> None:
    """Write ``data`` to ``out_path`` atomically within its directory.

    Expected create/open/write/replace ``OSError``s are translated into a ``NavError``.
    The raw descriptor returned by ``tempfile.mkstemp`` is owned by this function until
    ``os.fdopen`` returns successfully; if ``os.fdopen`` raises before that transfer,
    the raw descriptor is closed exactly once (with ``os.close``) before the temporary
    path is unlinked, so no descriptor or ``.okfnav-*.tmp`` residue is left. After a
    successful transfer the file object owns the descriptor and this function never
    closes it again (no double close on the write, context-manager close, replace, or
    cleanup paths). Any failure removes the temporary file and leaves a pre-existing
    output byte-for-byte; interrupts/programming errors still trigger descriptor/path
    cleanup, then propagate.
    """
    directory = out_path.parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise NavError(
            f"cannot create output directory {GENERATED_DIR_REL}: {_oserr(exc)}") from exc
    try:
        fd, tmp = tempfile.mkstemp(dir=str(directory), prefix=".okfnav-", suffix=".tmp")
    except OSError as exc:
        raise NavError(
            f"cannot create temporary output in {GENERATED_DIR_REL}: {_oserr(exc)}") from exc

    fd_open = True      # this function owns the raw descriptor until os.fdopen returns
    replaced = False
    try:
        try:
            handle = os.fdopen(fd, "wb")
        except OSError as exc:
            raise NavError(
                f"cannot open temporary output in {GENERATED_DIR_REL}: {_oserr(exc)}") from exc
        fd_open = False   # ownership has transferred to the file object
        try:
            with handle:
                handle.write(data)
            os.replace(tmp, out_path)
            replaced = True
        except OSError as exc:
            raise NavError(f"cannot write output {OUTPUT_REL}: {_oserr(exc)}") from exc
    finally:
        # Close the raw descriptor only if os.fdopen never took ownership, and remove
        # the temporary file unless the atomic replace already consumed it.
        if fd_open:
            try:
                os.close(fd)
            except OSError:
                pass
        if not replaced:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def generate(root: Path) -> str:
    """Render and write only when the output differs. Returns 'written' or
    'unchanged'."""
    data, out_path = expected_bytes(root)
    if _read_existing_output(out_path) == data:
        return "unchanged"
    _atomic_write(out_path, data)
    return "written"


def check(root: Path) -> str:
    """Read-only: return 'current', 'missing', or 'stale'. Never writes."""
    data, out_path = expected_bytes(root)
    existing = _read_existing_output(out_path)
    if existing is None:
        return "missing"
    if existing != data:
        return "stale"
    return "current"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = repo_root()
    if not argv:
        try:
            status = generate(root)
        except NavError as exc:
            sys.stderr.write(f"generate: {exc}\n")
            return 2
        sys.stdout.write(f"{status}: {OUTPUT_REL}\n")
        return 0
    if argv == ["--check"]:
        try:
            status = check(root)
        except NavError as exc:
            sys.stderr.write(f"check: {exc}\n")
            return 2
        if status == "current":
            sys.stdout.write(f"current: {OUTPUT_REL}\n")
            return 0
        sys.stderr.write(f"{status}: {OUTPUT_REL} (run {REGEN_COMMAND})\n")
        return 1
    sys.stderr.write("usage: generate_okf_navigation.py [--check]\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

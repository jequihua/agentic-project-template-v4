"""Review grammar and Git evidence shared by prompt and ledger commands."""
from __future__ import annotations

import hashlib
import json
import re

import _common as c


DIFF_LIMIT = 32 * 1024


def bounded_text(text, rel, limit=4096):
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    clipped = raw[:limit].decode("utf-8", "ignore")
    return clipped + f"\n\n[Embedded text truncated; read the full artifact at `{rel}`.]"


def _visible_lines(text):
    output = []
    fence = None
    for line in text.splitlines():
        mark = re.match(r"^\s*(`{3,}|~{3,})", line)
        if mark:
            token = mark.group(1)[0]
            fence = token if fence is None else None if fence == token else fence
            continue
        if fence is None:
            output.append(line)
    return output


def parse_review(text):
    lines = _visible_lines(text)
    names = ("## Findings", "## Closure Decision", "## Verdict")
    headings = {
        name: [index for index, line in enumerate(lines) if line.strip() == name]
        for name in names
    }
    if any(len(found) != 1 for found in headings.values()):
        raise ValueError(
            "review requires exactly one Findings, Closure Decision, and Verdict heading"
        )
    findings_at, closure_at, verdict_at = (headings[name][0] for name in names)
    if not findings_at < closure_at < verdict_at:
        raise ValueError("review sections are out of order")
    title_pattern = r"# Review: M\d{3}(?:-S\d{2})? round (?:\d+|holistic)"
    title = next(
        (line for line in lines[:findings_at] if re.fullmatch(title_pattern, line.strip())),
        None,
    )
    if not title:
        raise ValueError("review title is missing or invalid")
    match = re.fullmatch(
        r"# Review: (M\d{3}(?:-S\d{2})?) round (\d+|holistic)", title.strip()
    )
    identity, round_text = match.groups()
    table = [
        line for line in lines[findings_at + 1:closure_at]
        if line.strip().startswith("|")
    ]
    header = _cells(table[0]) if table else []
    separator = _cells(table[1]) if len(table) > 1 else []
    if header != ["id", "severity", "disposition", "summary"]:
        raise ValueError("findings table header or separator is missing")
    if not separator or not all(set(item) <= {"-", ":"} for item in separator):
        raise ValueError("findings table header or separator is missing")
    findings = []
    seen = set()
    for line in table[2:]:
        cells = _cells(line)
        if len(cells) == 4 and all(set(item) <= {"-", ":"} for item in cells):
            continue
        valid = (
            len(cells) == 4
            and cells[0] not in seen
            and cells[1] in ("P0", "P1", "P2", "P3")
            and cells[2] in ("open", "closed_by_review", "carried", "waived_by_human")
            and bool(cells[0])
            and bool(cells[3])
        )
        if not valid:
            raise ValueError(f"invalid findings row: {line.strip()}")
        seen.add(cells[0])
        findings.append(dict(zip(("id", "severity", "disposition", "summary"), cells)))
    closure = [line.strip() for line in lines[closure_at + 1:verdict_at] if line.strip()]
    statuses = [
        line.removeprefix("Objective status: ") for line in closure
        if line.startswith("Objective status: ")
    ]
    evidence = [
        line.removeprefix("Objective evidence: ") for line in closure
        if line.startswith("Objective evidence: ")
    ]
    valid = (
        len(statuses) == 1
        and statuses[0] in ("achieved", "not_achieved", "indeterminate")
        and len(evidence) == 1
        and bool(evidence[0])
    )
    if not valid:
        raise ValueError("invalid closure decision")
    verdict_lines = [line.strip() for line in lines[verdict_at + 1:] if line.strip()]
    verdict_match = (
        re.fullmatch(
            r"Verdict: (pass|needs_work|blocked|override) - next: (.+)",
            verdict_lines[0],
        )
        if verdict_lines else None
    )
    if not verdict_match or any(line.startswith("Verdict:") for line in verdict_lines[1:]):
        raise ValueError("invalid verdict line")
    verdict, move = verdict_match.groups()
    open_ids = [
        item["id"] for item in findings
        if item["severity"] in ("P0", "P1", "P2") and item["disposition"] == "open"
    ]
    if verdict in ("pass", "override") and open_ids:
        raise ValueError(f"{verdict} cannot have open P0-P2 findings")
    return {
        "identity": identity,
        "round": None if round_text == "holistic" else int(round_text),
        "findings": findings,
        "objective_status": statuses[0],
        "objective_evidence": evidence[0],
        "verdict": verdict,
        "next_move": move,
        "open": open_ids,
    }


def _cells(line):
    return [item.strip() for item in line.strip().strip("|").split("|")]


def changed_files(root):
    records = c.status_bytes(root).split(b"\0")
    output = []
    index = 0
    while index < len(records) and records[index]:
        record = records[index].decode("utf-8", "surrogateescape")
        code = record[:2]
        rel = record[3:].replace("\\", "/")
        index += 1
        if "R" in code:
            kind = "renamed"
        elif "D" in code:
            kind = "deleted"
        elif code == "??" or "A" in code:
            kind = "added"
        else:
            kind = "modified"
        if kind == "renamed" and index < len(records):
            index += 1
        path = c.repo_path(root, c.safe_rel(rel))
        if path.is_symlink():
            raise ValueError(f"changed path is a symlink: {rel}")
        if kind == "deleted":
            digest = hashlib.sha256(c.git(root, "show", f"HEAD:{rel}").stdout).hexdigest()
        elif path.is_file():
            digest = c.sha(path)
        else:
            raise ValueError(f"changed path is not a regular file: {rel}")
        output.append({"path": rel, "sha": digest, "kind": kind})
    return output


def prompt_baseline(root, allow_dirty=False):
    changed = changed_files(root)
    prompt_roots = ("prompts/for_coding_agent/", "prompts/for_review_agent/")
    dirty = [
        item["path"] for item in changed
        if item["path"] != "05_governance/ledger.jsonl"
        and not item["path"].startswith(prompt_roots)
    ]
    if dirty and not allow_dirty:
        paths = ", ".join(dirty)
        raise ValueError(
            f"dirty paths must be committed or stashed: {paths}; use --allow-dirty"
        )
    return changed if allow_dirty else None


def fence(changed, allowed, forbidden):
    def matches(path, rule):
        return path.startswith(rule) if rule.endswith("/") else path == rule

    return [
        item["path"] for item in changed
        if any(matches(item["path"], rule) for rule in forbidden)
        or not any(matches(item["path"], rule) for rule in allowed)
    ]


def rel_file(root, value):
    rel = c.cli_rel(value)
    path = c.repo_path(root, rel)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"not a regular repository file: {rel}")
    return rel, path


def diff_block(text, paths):
    notice = (
        "\n[Diff truncated at 32 KB. Inspect the listed changed paths locally with "
        "`git diff HEAD -- <path>`.]"
    )
    raw = text.encode("utf-8")
    if len(raw) > DIFF_LIMIT:
        room = DIFF_LIMIT - len(notice.encode("utf-8"))
        text = raw[:room].decode("utf-8", "ignore").rstrip() + notice
    if not text.strip():
        text = "(no textual diff; inspect " + ", ".join(paths) + ")"
    return "```diff\n" + text.rstrip() + "\n```"


def review_diff(root, changed):
    paths = [item["path"] for item in changed]
    if not paths:
        return diff_block("(no product changes)", paths)
    result = c.git(root, "diff", "--no-ext-diff", "HEAD", "--", *paths, check=False)
    if result.returncode:
        raise ValueError("cannot render review diff; inspect the changed paths locally")
    parts = [result.stdout.decode("utf-8", "replace")]
    for item in changed:
        if item["kind"] != "added":
            continue
        tracked = c.git(root, "ls-files", "--error-unmatch", "--", item["path"], check=False)
        if tracked.returncode == 0:
            continue
        path = c.repo_path(root, item["path"])
        try:
            body = path.read_text(encoding="utf-8")
        except UnicodeError:
            body = f"[Added file `{item['path']}` is not UTF-8 text; inspect it locally.]"
        parts.append(f"\nAdded file: {item['path']}\n{body}")
    return diff_block("".join(parts), paths)


def accepted_base(root, events, milestone):
    ids = {item["id"] for item in milestone["slices"]}
    for index, event in enumerate(events):
        if event["ev"] != "accepted" or event["slice"] not in ids:
            continue
        verified = next(
            (
                old for old in reversed(events[:index])
                if old["ev"] == "verified"
                and old["slice"] == event["slice"]
                and old["round"] == event["round"]
                and old["ok"]
            ),
            None,
        )
        if not verified:
            break
        receipt = json.loads((root / verified["receipt"]).read_text(encoding="utf-8"))
        base = receipt.get("base_commit")
        valid = isinstance(base, str) and c.git(
            root, "cat-file", "-e", base + "^{commit}", check=False
        ).returncode == 0
        if valid:
            return base
        break
    raise ValueError("cannot resolve the first accepted base commit for holistic review")


def findings_context(root, state):
    prefix = ""
    if state.get("unblock_reason"):
        prefix = f"Unblock reason: {state['unblock_reason']}\n\n"
    if state["open"] and state["report"]:
        report = parse_review((root / state["report"]).read_text(encoding="utf-8"))
        rows = [
            f"| {item['id']} | {item['severity']} | {item['disposition']} | "
            f"{item['summary']} |"
            for item in report["findings"] if item["id"] in state["open"]
        ]
        return prefix + "\n".join(rows)
    if state["receipt"]:
        receipt = json.loads((root / state["receipt"]).read_text(encoding="utf-8"))
        if not receipt["ok"]:
            command = receipt["commands"][-1]
            return (
                prefix + "Previous verification failed.\n\nstdout tail:\n```text\n"
                f"{command['stdout_tail']}\n```\n\nstderr tail:\n```text\n"
                f"{command['stderr_tail']}\n```"
            )
    return prefix.rstrip()

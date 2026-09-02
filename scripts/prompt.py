"""Render agent prompts from project authority."""

import argparse
import json
import re
import sys
from pathlib import Path

import _common as c
import _evidence as evidence
import ledger
import roadmap


KNOWN = {
    "slice_id",
    "title",
    "round",
    "objective",
    "acceptance",
    "non_goals",
    "read_first",
    "allowed_prefixes",
    "forbidden",
    "focused",
    "full",
    "open_findings",
    "memory",
    "diff_manifest",
    "diff_evidence",
    "coder_notes",
    "receipt",
    "prior_findings",
    "report_path",
    "finding_id_rule",
}


def _bullets(values, empty="- None declared."):
    return "\n".join(f"- {value}" for value in values) if values else empty


def _argv(values):
    if not values:
        return "- None declared."
    commands = [values] if isinstance(values[0], str) else values
    return "\n\n".join("```text\n" + " ".join(command) + "\n```" for command in commands)


def _render(path, values, optional=()):
    text = path.read_text(encoding="utf-8")
    found = set(re.findall(r"{{([a-z_]+)}}", text))
    unknown = found - KNOWN
    if unknown:
        raise ValueError(f"unknown placeholders: {sorted(unknown)}")
    for heading, key in optional:
        if not values.get(key):
            pattern = rf"\n## {re.escape(heading)}\n.*?(?=\n## |\Z)"
            text = re.sub(pattern, "", text, flags=re.S)
    for key in found:
        text = text.replace("{{" + key + "}}", str(values.get(key, "")))
    if "{{" in text or "}}" in text:
        raise ValueError("unresolved placeholder")
    return text.rstrip() + "\n"


def _next(root):
    used = set()
    folders = (root / "prompts/for_coding_agent", root / "prompts/for_review_agent")
    for folder in folders:
        for path in folder.glob("*.md"):
            match = re.match(r"(\d{3})_", path.name)
            if match:
                used.add(int(match.group(1)))
    for value in range(1, 1000):
        if value not in used:
            return value
    raise ValueError("prompt number space exhausted")


def _memory(rm, item):
    memory = rm.get("memory")
    if not memory:
        return ""
    root = memory["root"].rstrip("/")
    lines = [f"Root: `{root}`", "", "Allowed read commands:"]
    lines += [f"- `llloom --root {root} {verb}`" for verb in memory["read_verbs"]]
    pages = item.get("memory_pages", memory.get("read_first_pages", []))
    if pages:
        lines += ["", "Read for this slice:"] + [f"- `{page}`" for page in pages]
    lines += [
        "",
        "Cite claim or page ids used. Report stale or contradicted claims; "
        "do not hand-edit memory.",
    ]
    return "\n".join(lines)


def coding(root, sid, allow_dirty=False):
    rm = roadmap.load(root)
    events = ledger.read(root / "05_governance/ledger.jsonl")
    state = ledger.fold(events, rm)
    current = state["slices"].get(sid)
    if not current or current["step"] not in ("unstarted", "fix"):
        raise ValueError(f"{sid} is not ready for coding prompt")
    ledger.require_artifacts(root, events)
    baseline = evidence.prompt_baseline(root, rm, events, sid, allow_dirty)
    _, item = roadmap.slice_by_id(rm, sid)
    focused = item.get("focused") or rm["verification"].get("focused_default", [])
    values = {
        "slice_id": sid,
        "title": item["title"],
        "round": current["round"],
        "objective": item["objective"].strip(),
        "acceptance": _bullets(item["acceptance"]),
        "non_goals": _bullets(item.get("non_goals", [])),
        "read_first": _bullets([f"`{path}`" for path in item.get("read_first", [])]),
        "allowed_prefixes": ", ".join(f"`{path}`" for path in roadmap.effective_prefixes(rm, item)),
        "forbidden": ", ".join(f"`{path}`" for path in rm["forbidden"]),
        "focused": _argv(focused),
        "full": _argv(item.get("verification", rm["verification"]["full"])),
        "open_findings": evidence.findings_context(root, current),
        "memory": _memory(rm, item),
    }
    template = root / "prompts/templates/coding_prompt.md"
    text = _render(
        template, values, (("Findings to resolve", "open_findings"), ("Memory", "memory"))
    )
    number = _next(root)
    path = root / "prompts/for_coding_agent" / f"{number:03d}_{sid}_r{current['round']}.md"
    c.atomic_text(path, text)
    rel = path.relative_to(root).as_posix()
    event = {
        "ev": "prompt",
        "by": "architect",
        "slice": sid,
        "round": current["round"],
        "path": rel,
        "sha": c.sha(path),
    }
    if baseline:
        event["baseline"] = baseline
    ledger.append(root / "05_governance/ledger.jsonl", event, rm)
    if len(text.encode()) > 8192:
        print("warning: coding prompt exceeds 8 KB", file=sys.stderr)
    return rel


def review(root, sid):
    rm = roadmap.load(root)
    events = ledger.read(root / "05_governance/ledger.jsonl")
    state = ledger.fold(events, rm)
    current = state["slices"].get(sid)
    if not current or current["step"] != "reviewing":
        raise ValueError(f"{sid} is not awaiting review")
    ledger.require_artifacts(root, events)
    _, item = roadmap.slice_by_id(rm, sid)
    folder = f"05_governance/reviews/{sid.split('-')[0].lower()}"
    report = f"{folder}/{sid}_r{current['round']}_review.md"
    receipt_text = (root / current["receipt"]).read_text(encoding="utf-8")
    notes = (
        evidence.bounded_text(
            (root / current["notes"]).read_text(encoding="utf-8"), current["notes"]
        )
        if current["notes"]
        else ""
    )
    current_paths = {item["path"] for item in current["changed"]}
    changed = _bullets(
        [
            f"`{item['path']}` ({item['kind']}, sha256 `{item['sha']}`, "
            f"{'current round' if item['path'] in current_paths else 'earlier round'})"
            for item in evidence.slice_changes(events, sid)
        ]
    )
    values = {
        "slice_id": sid,
        "title": item["title"],
        "round": current["round"],
        "objective": item["objective"].strip(),
        "acceptance": _bullets(item["acceptance"]),
        "diff_manifest": changed,
        "diff_evidence": evidence.review_diff(root, current["changed"]),
        "coder_notes": notes,
        "receipt": (
            f"Path: `{current['receipt']}`\n\nSHA-256: `{c.sha(root / current['receipt'])}`"
            f"\n\n```json\n{receipt_text.rstrip()}\n```"
        ),
        "prior_findings": evidence.findings_context(root, current) if current["open"] else "",
        "report_path": report,
        "finding_id_rule": f"Start every finding ID with `{sid}-`.",
    }
    text = _render(
        root / "prompts/templates/review_prompt.md",
        values,
        (("Coder notes", "coder_notes"), ("Prior findings", "prior_findings")),
    )
    path = root / "prompts/for_review_agent" / f"{_next(root):03d}_{sid}_r{current['round']}.md"
    c.atomic_text(path, text)
    rel = path.relative_to(root).as_posix()
    ledger.append(
        root / "05_governance/ledger.jsonl",
        {
            "ev": "artifact",
            "by": "architect",
            "scope": sid,
            "round": current["round"],
            "role": "review_prompt",
            "path": rel,
            "sha": c.sha(path),
        },
        rm,
    )
    if len(text.encode()) > 64 * 1024:
        print("warning: review prompt exceeds 64 KB", file=sys.stderr)
    return rel


def holistic(root, mid):
    rm = roadmap.load(root)
    events = ledger.read(root / "05_governance/ledger.jsonl")
    state = ledger.fold(events, rm)
    milestone = next((item for item in rm["milestones"] if item["id"] == mid), None)
    ready = (
        milestone
        and milestone["holistic_review"]
        and all(state["slices"][item["id"]]["step"] == "accepted" for item in milestone["slices"])
    )
    if not ready:
        raise ValueError(f"{mid} is not ready for holistic review")
    ledger.require_artifacts(root, events)
    changed = []
    paths_by_slice = {}
    receipts = []
    for item in milestone["slices"]:
        current = state["slices"][item["id"]]
        cumulative = evidence.slice_changes(events, item["id"])
        paths_by_slice[item["id"]] = [row["path"] for row in cumulative]
        changed += [
            f"`{row['path']}` ({item['id']}, {row['kind']}, latest round {row['round']})"
            for row in cumulative
        ]
        if current["receipt"]:
            receipt_text = (root / current["receipt"]).read_text(encoding="utf-8").rstrip()
            receipts.append(
                f"### {item['id']}\n\nVerification: `{current['receipt']}` "
                f"(sha256 `{c.sha(root / current['receipt'])}`)\n\n"
                f"Review: `{current['report']}`\n\n```json\n{receipt_text}\n```"
            )
    base = evidence.accepted_base(root, events, milestone)
    report = f"05_governance/reviews/{mid.lower()}/{mid}_holistic_review.md"
    values = {
        "slice_id": mid,
        "title": milestone["title"],
        "round": "holistic",
        "objective": f"Judge holistic closure of {mid} across its accepted slices.",
        "acceptance": _bullets(
            [
                f"{item['id']}: {value}"
                for item in milestone["slices"]
                for value in item["acceptance"]
            ]
        ),
        "diff_manifest": _bullets(changed),
        "diff_evidence": evidence.holistic_diff(root, base, paths_by_slice),
        "coder_notes": "",
        "receipt": "\n\n".join(receipts),
        "prior_findings": "",
        "report_path": report,
        "finding_id_rule": (
            "Every P0-P2 finding ID must start with the affected slice ID, "
            "for example `M001-S02-H1-F1`."
        ),
    }
    text = _render(
        root / "prompts/templates/review_prompt.md",
        values,
        (("Coder notes", "coder_notes"), ("Prior findings", "prior_findings")),
    )
    path = root / "prompts/for_review_agent" / f"{_next(root):03d}_{mid}_holistic.md"
    c.atomic_text(path, text)
    rel = path.relative_to(root).as_posix()
    ledger.append(
        root / "05_governance/ledger.jsonl",
        {
            "ev": "artifact",
            "by": "architect",
            "scope": mid,
            "round": "holistic",
            "role": "holistic_prompt",
            "path": rel,
            "sha": c.sha(path),
        },
        rm,
    )
    return rel


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("slice", nargs="?")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--holistic")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--root", type=Path, default=c.ROOT)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.holistic:
            rel = holistic(root, args.holistic)
        elif not args.slice:
            raise ValueError("provide a slice or --holistic Mnnn")
        elif args.review:
            rel = review(root, args.slice)
        else:
            rel = coding(root, args.slice, args.allow_dirty)
        print(rel)
        return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

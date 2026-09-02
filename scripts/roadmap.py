"""Validate, query, and render the project roadmap authority."""

import argparse
import copy
import re
import sys
from pathlib import Path

import yaml

import _common as c

TOP = {
    "schema",
    "project",
    "brief",
    "verification",
    "allowed_prefixes",
    "forbidden",
    "review",
    "memory",
    "milestones",
    "ruled_out",
    "not_yet_specified",
}
MILESTONE = {"id", "title", "status", "risk", "holistic_review", "slices"}
SLICE = {
    "id",
    "title",
    "objective",
    "acceptance",
    "non_goals",
    "read_first",
    "allowed_prefixes",
    "focused",
    "verification",
    "risk",
    "kind",
    "memory_pages",
    "notes",
}
MEMORY = {"kind", "root", "manual", "read_verbs", "read_first_pages"}
MID, SID = (re.compile("M\\d{3}$"), re.compile("M\\d{3}-S\\d{2}$"))


def _map(value, allowed, where, errors):
    if not isinstance(value, dict):
        errors.append(f"{where} must be a mapping")
        return False
    errors += [f"{where}: unknown key {key!r}" for key in value if key not in allowed]
    return True


def _strings(value, where, errors, required=False):
    invalid = not isinstance(value, list) or required and not value
    invalid = (
        invalid
        or isinstance(value, list)
        and any(not isinstance(x, str) or not x.strip() for x in value)
    )
    if invalid:
        article = "a non-empty " if required else "a "
        errors.append(f"{where} must be {article}list of non-empty strings")
        return []
    return value


def _paths(value, where, errors, prefixes=False):
    out = _strings(value, where, errors)
    for item in out:
        try:
            c.safe_rel(item, directory=prefixes and item.endswith("/"))
        except ValueError as exc:
            errors.append(f"{where}: {exc}")
    return out


def _commands(value, where, errors, required=False):
    if not isinstance(value, list) or (required and (not value)):
        message = "a non-empty list of argv lists" if required else "a list of argv lists"
        errors.append(f"{where} must be {message}")
        return
    for n, command in enumerate(value):
        _strings(command, f"{where}[{n}]", errors, required=True)


def validate(data: dict) -> tuple[list[str], list[str]]:
    errors, warnings, ids = ([], [], set())
    _map(data, TOP, "roadmap", errors)
    if data.get("schema") != "frutlups.roadmap/1":
        errors.append("schema must be frutlups.roadmap/1")
    if not isinstance(data.get("project"), str) or not data.get("project", "").strip():
        errors.append("project must be a non-empty string")
    try:
        c.safe_rel(data.get("brief", ""), directory=True)
    except ValueError as exc:
        errors.append(f"brief: {exc}")
    verification = data.get("verification")
    if _map(verification, {"full", "focused_default"}, "verification", errors):
        _strings(verification.get("full"), "verification.full argv", errors, required=True)
        _commands(verification.get("focused_default", []), "verification.focused_default", errors)
    defaults = _paths(data.get("allowed_prefixes"), "allowed_prefixes", errors, True)
    forbidden = _paths(data.get("forbidden"), "forbidden", errors, True)
    review = data.get("review")
    if _map(review, {"ordinary", "high", "release"}, "review", errors):
        for risk in ("ordinary", "high", "release"):
            seats = review.get(risk)
            _strings([seats] if isinstance(seats, str) else seats, f"review.{risk}", errors, True)
    memory, memory_root = (data.get("memory"), None)
    if memory is not None and _map(memory, MEMORY, "memory", errors):
        if memory.get("kind") != "llloom":
            errors.append("memory.kind must be llloom")
        for key in ("root", "manual"):
            try:
                c.safe_rel(memory.get(key, ""), directory=key == "root")
            except ValueError as exc:
                errors.append(f"memory.{key}: {exc}")
        memory_root = (
            memory.get("root", "").rstrip("/") + "/"
            if isinstance(memory.get("root"), str)
            else None
        )
        _strings(memory.get("read_verbs"), "memory.read_verbs", errors, True)
        _paths(memory.get("read_first_pages"), "memory.read_first_pages", errors)
    milestones, active = (data.get("milestones"), 0)
    if not isinstance(milestones, list) or not milestones:
        errors.append("milestones must be a non-empty list")
        milestones = []
    for mi, milestone in enumerate(milestones):
        where = f"milestones[{mi}]"
        mid = milestone.get("id") if isinstance(milestone, dict) else None
        if not _map(milestone, MILESTONE, where, errors):
            continue
        if not isinstance(mid, str) or not MID.fullmatch(mid):
            errors.append(f"{where}.id must match Mnnn")
        elif mid in ids:
            errors.append(f"duplicate id {mid}")
        else:
            ids.add(mid)
        if not isinstance(milestone.get("title"), str) or not milestone.get("title", "").strip():
            errors.append(f"{where}.title must be non-empty")
        if milestone.get("status") not in ("planned", "active"):
            errors.append(f"{where}.status must be planned or active")
        if milestone.get("risk") not in ("ordinary", "high", "release"):
            errors.append(f"{where}.risk is invalid")
        if not isinstance(milestone.get("holistic_review"), bool):
            errors.append(f"{where}.holistic_review must be boolean")
        items = milestone.get("slices")
        active += milestone.get("status") == "active"
        if not isinstance(items, list) or not items:
            errors.append(f"{where}.slices must be non-empty")
            continue
        for si, item in enumerate(items):
            sw = f"{where}.slices[{si}]"
            sid = item.get("id") if isinstance(item, dict) else None
            if not _map(item, SLICE, sw, errors):
                continue
            invalid_sid = not isinstance(sid, str) or not SID.fullmatch(sid)
            invalid_sid = invalid_sid or isinstance(mid, str) and not sid.startswith(mid + "-")
            if invalid_sid:
                errors.append(f"{sw}.id must match {mid}-Snn")
            elif sid in ids:
                errors.append(f"duplicate id {sid}")
            else:
                ids.add(sid)
            errors += [
                f"{sw}.{key} must be non-empty"
                for key in ("title", "objective")
                if not isinstance(item.get(key), str) or not item.get(key, "").strip()
            ]
            _strings(item.get("acceptance"), f"{sw}.acceptance", errors, True)
            _strings(item.get("non_goals", []), f"{sw}.non_goals", errors)
            _paths(item.get("read_first", []), f"{sw}.read_first", errors)
            effective, kind = (item.get("allowed_prefixes", defaults), item.get("kind", "code"))
            _paths(effective, f"{sw}.allowed_prefixes", errors, True)
            if kind not in ("code", "memory_update", "docs"):
                errors.append(f"{sw}.kind is invalid")
            for prefix in effective if isinstance(effective, list) else []:
                broadens = defaults and not any(prefix.startswith(base) for base in defaults)
                if kind != "memory_update" and broadens:
                    errors.append(f"{sw}.allowed_prefixes broadens project defaults: {prefix}")
                if any((prefix.startswith(x) or x.startswith(prefix) for x in forbidden)):
                    errors.append(f"{sw}.allowed_prefixes overlaps forbidden path: {prefix}")
            if kind == "memory_update" and (not memory_root or memory_root not in effective):
                errors.append(f"{sw}: memory_update must allow the memory root")
            overlaps_memory = memory_root and any(
                prefix.startswith(memory_root) or memory_root.startswith(prefix)
                for prefix in effective
            )
            if kind == "code" and overlaps_memory:
                errors.append(f"{sw}: code slice may not allow the memory root")
            _commands(item.get("focused", []), f"{sw}.focused", errors)
            if "verification" in item:
                _strings(item["verification"], f"{sw}.verification argv", errors, True)
            if item.get("risk", milestone.get("risk")) not in ("ordinary", "high", "release"):
                errors.append(f"{sw}.risk is invalid")
            if "notes" in item and not isinstance(item["notes"], str):
                errors.append(f"{sw}.notes must be a string")
            if item.get("memory_pages") and memory is None:
                errors.append(f"{sw}.memory_pages requires a memory block")
            _paths(item.get("memory_pages", []), f"{sw}.memory_pages", errors)
            if len(yaml.safe_dump(item, sort_keys=False).encode()) > 2048:
                warnings.append(f"{sid}: slice entry exceeds 2 KB")
    if milestones and (not active):
        errors.append("at least one milestone must be active")
    for key, prefix in (("ruled_out", "R"), ("not_yet_specified", "N")):
        rows = data.get(key, [])
        if not isinstance(rows, list):
            errors.append(f"{key} must be a list")
            continue
        for row in rows:
            valid = isinstance(row, dict) and set(row) == {"id", "text"}
            valid = valid and bool(re.fullmatch(prefix + "\\d+", str(row.get("id", ""))))
            valid = valid and bool(str(row.get("text", "")).strip())
            if not valid:
                errors.append(f"{key} entries require {prefix}<number> id and text")
    return (errors, warnings)


def load(root: Path = c.ROOT) -> dict:
    data = c.load_yaml(root / "roadmap.yaml")
    errors, _ = validate(data)
    if errors:
        raise ValueError("\n".join(errors))
    out = copy.deepcopy(data)
    out["review"] = {
        key: [seats] if isinstance(seats, str) else seats for key, seats in out["review"].items()
    }
    return out


def slices(data):
    return ((milestone, item) for milestone in data["milestones"] for item in milestone["slices"])


def slice_by_id(data, sid):
    for milestone, item in slices(data):
        if item["id"] == sid:
            return (milestone, item)
    raise ValueError(f"unknown slice: {sid}")


def effective_prefixes(data, item):
    return tuple(item.get("allowed_prefixes", data["allowed_prefixes"]))


def render_markdown(data):
    lines = [
        "# Roadmap",
        "",
        "> Generated from `roadmap.yaml`; do not edit.",
        "",
        f"Project: `{data['project']}`",
        "",
    ]
    for milestone in data["milestones"]:
        lines += [
            f"## {milestone['id']} — {milestone['title']}",
            "",
            f"Status: {milestone['status']}",
            f"Risk: {milestone['risk']}",
            f"Holistic review: {str(milestone['holistic_review']).lower()}",
            "",
        ]
        for item in milestone["slices"]:
            lines += [
                f"### {item['id']} — {item['title']}",
                "",
                item["objective"].strip(),
                "",
                "Acceptance:",
            ] + [f"- {x}" for x in item["acceptance"]]
            if item.get("non_goals"):
                lines += ["", "Non-goals:"] + [f"- {x}" for x in item["non_goals"]]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "render", "next"))
    parser.add_argument("--root", type=Path, default=c.ROOT)
    args = parser.parse_args(argv)
    try:
        raw = c.load_yaml(args.root / "roadmap.yaml")
        errors, warnings = validate(raw)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        if errors:
            print("\n".join((f"error: {error}" for error in errors)), file=sys.stderr)
            return 2
        data = load(args.root)
        if args.command == "check":
            print("roadmap: ok")
            return 0
        if args.command == "render":
            c.atomic_text(args.root / "docs/roadmap.md", render_markdown(data))
            print("docs/roadmap.md")
            return 0
        import ledger

        state = ledger.fold(ledger.read(args.root / "05_governance/ledger.jsonl"), data)
        print(ledger.next_slice(data, state) or "none")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

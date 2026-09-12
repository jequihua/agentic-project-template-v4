"""Render complete agent envelopes with bounded, immutable review evidence."""

import argparse
import json
import re
import sys
from pathlib import Path

import _common as c
import _evidence as evidence
import _integrity as integrity
import ledger
import roadmap


CODING_LIMIT, REVIEW_LIMIT = 16 * 1024, 48 * 1024
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
    "finding_updates",
    "notes",
    "outcome_contract",
}
ENVELOPE_SECTIONS = (
    ("Objective", "objective"),
    ("Acceptance", "acceptance"),
    ("Non-goals", "non_goals"),
    ("Read first", "read_first"),
    ("Allowed writes", "allowed_prefixes"),
    ("Forbidden writes", "forbidden"),
    ("Focused verification", "focused"),
    ("Full verification", "full"),
    ("Advisory notes", "notes"),
    ("Findings and resolutions", "open_findings"),
    ("Memory", "memory"),
)


def _bullets(values, empty="- None declared."):
    return "\n".join(f"- {value}" for value in values) if values else empty


def _argv(values):
    if not values:
        return "- None declared."
    commands = [values] if isinstance(values[0], str) else values
    return "\n\n".join("```text\n" + " ".join(command) + "\n```" for command in commands)


def _render(path, values, optional=(), complete=False):
    text = evidence.read_excerpt(path.parent, path.name, REVIEW_LIMIT + 1).replace("\r\n", "\n")
    if path.stat().st_size > REVIEW_LIMIT:
        raise ValueError("template framing exceeds 49152 bytes; reduce the custom template")
    found = set(re.findall(r"{{([a-z_]+)}}", text))
    unknown = found - KNOWN
    if unknown:
        raise ValueError(f"unknown placeholders: {sorted(unknown)}")
    bare = re.sub(r"{{[a-z_]+}}", "", text)
    if "{{" in bare or "}}" in bare:
        raise ValueError("unresolved placeholder")
    for heading, key in optional:
        if not values.get(key):
            pattern = rf"\n## {re.escape(heading)}\n.*?(?=\n## |\Z)"
            text = re.sub(pattern, "", text, flags=re.S)
    text = re.sub(r"{{([a-z_]+)}}", lambda match: str(values.get(match[1], "")), text)
    # Preserve project-owned templates while making omitted authority visible.
    additions = ENVELOPE_SECTIONS if complete else (("Advisory notes", "notes"),)
    for heading, key in additions:
        if key not in found and values.get(key):
            if complete:
                print(
                    f"diagnostic: custom template omitted {key}; appended its full section",
                    file=sys.stderr,
                )
            text += f"\n\n## {heading}\n\n{values[key]}"
    if values.get("outcome_contract") and "outcome_contract" not in found:
        text += "\n\n## Autonomous outcome\n\n" + values["outcome_contract"]
    return text.replace("\r\n", "\n").rstrip() + "\n"


def _next(root):
    used = set()
    for folder in (root / "prompts/for_coding_agent", root / "prompts/for_review_agent"):
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


def _load(root):
    rm = roadmap.load(root)
    events = ledger.read(root / "05_governance/ledger.jsonl")
    return rm, events, ledger.fold(events, rm)


def _v2(rm):
    return rm["schema"] == "frutlups.roadmap/2"


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _envelope(root, rm, item, current):
    context = evidence.findings_context(root, current)
    if current.get("blocker"):
        blocker = current["blocker"]
        if isinstance(blocker, dict) and "path" in blocker:
            context += "\n\nOriginal blocker:\n" + evidence.read_excerpt(
                root, blocker["path"], CODING_LIMIT
            )
        else:
            context += "\n\nOriginal blocker:\n" + _json(blocker)
    if current.get("resolution"):
        resolution = current["resolution"]
        context += "\n\nRecorded resolution: " + (
            resolution if isinstance(resolution, str) else _json(resolution)
        )
    return {
        "schema": "frutlups.envelope/2",
        "slice": item["id"],
        "round": current["round"],
        "title": item["title"],
        "objective": item["objective"].strip(),
        "acceptance": item["acceptance"],
        "non_goals": item.get("non_goals", []),
        "read_first": item.get("read_first", []),
        "allowed_prefixes": roadmap.effective_prefixes(rm, item),
        "forbidden": rm["forbidden"],
        "focused": item.get("focused") or rm["verification"].get("focused_default", []),
        "full": item.get("verification", rm["verification"]["full"]),
        "runtime": rm.get("runtime", {}),
        "timeout_seconds": rm["verification"].get("timeout_seconds", 600),
        "observation": rm["verification"].get("observation", "process"),
        "notes": item.get("notes", "").strip(),
        "findings": context.strip(),
        "memory": _memory(rm, item),
    }


def _values(envelope):
    values = {key: envelope[key] for key in ("title", "round", "objective", "memory")}
    values["slice_id"] = envelope["slice"]
    for key in ("acceptance", "non_goals"):
        values[key] = _bullets(envelope[key])
    values["read_first"] = _bullets([f"`{path}`" for path in envelope["read_first"]])
    for key in ("allowed_prefixes", "forbidden"):
        values[key] = ", ".join(f"`{path}`" for path in envelope[key])
    for key in ("focused", "full"):
        values[key] = _argv(envelope[key])
    if "runtime" in envelope:
        values["full"] += (
            "\n\nExecution policy: runtime "
            + json.dumps(envelope["runtime"], ensure_ascii=False, sort_keys=True)
            + f"; timeout {envelope['timeout_seconds']} seconds; "
            + f"observation {envelope['observation']}."
        )
    values["notes"] = (
        "Advisory context; mandatory gates belong in acceptance.\n\n" + envelope["notes"]
        if envelope["notes"]
        else ""
    )
    values["open_findings"] = envelope["findings"]
    return values


def _frozen(root, rm, events, item, current):
    issued = next(
        (
            event
            for event in reversed(events)
            if event["ev"] == "prompt"
            and event.get("slice") == item["id"]
            and event["round"] == current["round"]
        ),
        {},
    )
    ref = issued.get("envelope")
    if ref:
        path = c.repo_path(root, ref["path"])
        if c.sha(path) != ref["sha"]:
            raise ValueError("immutable acceptance envelope drift")
        return json.loads(path.read_text(encoding="utf-8"))
    return _envelope(root, rm, item, current)


def _diagnostics(root, envelope):
    messages = []
    for rel in envelope["read_first"]:
        path = c.repo_path(root, c.safe_rel(rel))
        if not path.is_file() or path.is_symlink():
            messages.append(f"missing required read: {rel} (future outputs belong in acceptance)")
    if re.search(r"\b(must|required|gate|shall)\b", envelope["notes"], re.I):
        messages.append("advisory notes contain gate language; move mandatory gates to acceptance")
    # Diagnose only explicit path references, without guessing prose into scope.
    for rel in re.findall(r"`([^`\n]+/[^`\n]+)`", "\n".join(envelope["acceptance"])):
        if re.search(r"\s", rel) or rel.startswith(("http:", "https:")):
            continue
        try:
            c.safe_rel(rel)
        except ValueError:
            continue
        outside = evidence.fence([{"path": rel}], envelope["allowed_prefixes"], [])
        if outside and rel not in envelope["read_first"]:
            messages.append(
                f"acceptance path outside writes: {rel}; declare architect ownership "
                "or admit its integration/docs/test writes"
            )
    return messages


def _sized(text, values, limit):
    size = len(text.encode("utf-8"))
    if size > limit:
        sections = ", ".join(
            f"{key}={len(str(value).encode('utf-8'))}" for key, value in values.items() if value
        )
        raise ValueError(
            f"prompt is {size} bytes; cap is {limit}; reduce admitted scope. "
            f"Section bytes: {sections}"
        )
    return text


def _finish(backend, sid, round_no):
    if backend == "manual":
        return ""
    example = {
        "schema": "frutlups.outcome/2",
        "slice": sid,
        "round": round_no,
        "invocation": "<runner-provided invocation id>",
        "outcome": "implemented",
        "requirement": "<affected acceptance requirement>",
        "reason": "<observed result>",
        "actor": "",
        "action": "",
        "remaining": [],
        "evidence": [],
        "authority": [],
    }
    return (
        "For this autonomous backend, replace the manual four-list Finish response with "
        "one JSON object using this exact schema (at most 16384 UTF-8 bytes):\n\n```json\n"
        + _json(example)
        + "```\nOutcome is implemented, blocked_authority, or "
        "blocked_environment. A blocker requires nonempty actor/action and bounded remaining "
        "work. Evidence entries are {path,sha}; authority entries are relative decision/budget "
        "paths. Preserve edits and report missing authority; never invent success or a budget. "
        "Use the invocation identity supplied by the runner."
    )


def _save(root, rel, text):
    path = c.repo_path(root, rel)
    if path.exists() or path.is_symlink():
        if (
            path.is_symlink()
            or not path.is_file()
            or c.sha(path) != c.evidence_sha_bytes(text.encode("utf-8"))
        ):
            raise ValueError(f"immutable evidence path already occupied: {rel}")
    else:
        c.atomic_text(path, text)
    return {"path": rel, "sha": c.evidence_sha_bytes(text.encode("utf-8"))}


def _ref(root, rel, digest=None):
    return f"`{rel}` (sha256 `{digest or c.sha(root / rel)}`)"


def _support(scope, label, text, artifacts):
    digest = c.evidence_sha_bytes(text.encode("utf-8"))
    rel = f"05_governance/reviews/{scope.split('-')[0].lower()}/{scope}_{digest[:16]}_{label}"
    artifacts.append((rel, text))
    return f"`{rel}` (sha256 `{digest}`; read as a file, starting at line 1)"


def _diff_excerpt(diff):
    if len(diff.encode("utf-8")) <= 8192:
        return diff
    prefix = diff.encode("utf-8")[:8000].decode("utf-8", "ignore")
    return prefix + "\n```\n\n[Inline excerpt bounded; read the full diff page above.]"


def _issue_support(root, rm, events, scope, round_no, artifacts):
    known = {(event.get("path"), event.get("sha")) for event in events}
    for rel, text in artifacts:
        ref = _save(root, rel, text)
        if (rel, ref["sha"]) not in known:
            ledger.append(
                root / "05_governance/ledger.jsonl",
                {
                    "ev": "artifact",
                    "by": "architect",
                    "scope": scope,
                    "round": round_no,
                    "role": "evidence",
                    **ref,
                },
                rm,
            )


def coding(root, sid, allow_dirty=False, *, preview=False, backend="manual"):
    rm, events, state = _load(root)
    current = state["slices"].get(sid)
    if not current or current["step"] not in ("unstarted", "fix"):
        raise ValueError(f"{sid} is not ready for coding prompt")
    if backend == "autonomous" and not _v2(rm):
        raise ValueError("structured autonomous prompts require the /2 roadmap contract")
    _, item = roadmap.slice_by_id(rm, sid)
    envelope = _envelope(root, rm, item, current)
    if current.get("blocker") and current.get("envelope"):
        # A resolution supplies new authority, without silently replacing the task.
        ref = current["envelope"]
        prior = json.loads((root / ref["path"]).read_text(encoding="utf-8"))
        envelope = {**prior, "round": current["round"], "findings": envelope["findings"]}
        if current.get("manifest"):
            ref = current["manifest"]
            envelope["findings"] += "\n\nRetained changes: " + _ref(root, ref["path"], ref["sha"])
        if current.get("notes"):
            envelope["findings"] += (
                "\n\nPrevious notes: "
                + _ref(root, current["notes"], current.get("notes_sha"))
                + "\n"
                + evidence.read_excerpt(root, current["notes"], 2048)
            )
    for event in events:
        if event["ev"] == "resolved" and event["scope"] == sid:
            envelope["findings"] += "\n\nResolution authority: " + ", ".join(
                _ref(root, ref["path"], ref["sha"]) for ref in event["authority"]
            )
    values = _values(envelope)
    values["outcome_contract"] = _finish(backend, sid, current["round"])
    text = _sized(
        _render(
            root / "prompts/templates/coding_prompt.md",
            values,
            (
                ("Findings to resolve", "open_findings"),
                ("Memory", "memory"),
                ("Advisory notes", "notes"),
                ("Autonomous outcome", "outcome_contract"),
            ),
            _v2(rm),
        ),
        values,
        CODING_LIMIT,
    )
    diagnostics = _diagnostics(root, envelope)
    for message in diagnostics:
        print(f"diagnostic: {message}", file=sys.stderr)
    if any(message.startswith("missing required read") for message in diagnostics):
        raise ValueError("prompt has missing required reads; correct read_first before issuance")
    ledger.require_artifacts(root, events)
    baseline = evidence.prompt_baseline(root, rm, events, sid, allow_dirty)
    if preview:
        return text
    event = {"ev": "prompt", "by": "architect", "slice": sid, "round": current["round"]}
    if _v2(rm):
        rel = f"05_governance/reviews/{sid.split('-')[0].lower()}/{sid}_r{current['round']}"
        event["envelope"] = _save(root, rel + "_envelope.json", _json(envelope))
    rel = f"prompts/for_coding_agent/{_next(root):03d}_{sid}_r{current['round']}.md"
    event.update(_save(root, rel, text))
    if baseline:
        event["baseline"] = baseline
    ledger.append(root / "05_governance/ledger.jsonl", event, rm)
    return rel


def _receipt(root, current):
    rel = current["receipt"]
    prefix = "Verification passed. Complete receipt: " + _ref(root, rel)
    # Legacy receipts may contain hundreds of repeated path hashes.
    if (root / rel).stat().st_size <= 4096:
        prefix += "\n\n```json\n" + evidence.read_excerpt(root, rel, 4096).rstrip() + "\n```"
    return prefix


def _review_values(envelope, report):
    values = _values(envelope)
    values.update(
        diff_manifest="",
        diff_evidence="",
        coder_notes="",
        receipt="",
        prior_findings=envelope["findings"],
        report_path=report,
        finding_id_rule=f"Start every finding ID with `{envelope['slice']}-`.",
    )
    # The review template presents this as Prior findings, without duplicating it.
    values["open_findings"] = ""
    return values


def _render_review(root, values, version2):
    values["finding_updates"] = (
        "To change an older finding, add `## Finding updates` before Closure Decision with "
        "columns `source | sha | id | disposition | related`. Name the original report path, "
        "its SHA-256, exact finding ID and explicit disposition; related is linked IDs or `-`. "
        "An unrelated pass closes nothing. Only a human may waive findings."
        if version2
        else ""
    )

    def render():
        return _render(
            root / "prompts/templates/review_prompt.md",
            values,
            (
                ("Coder notes", "coder_notes"),
                ("Prior findings", "prior_findings"),
                ("Advisory notes", "notes"),
            ),
            version2,
        )

    text = render()
    # Externalize supporting excerpts before asking to reduce authority/scope.
    for key in ("diff_evidence", "coder_notes", "receipt", "diff_manifest"):
        if len(text.encode("utf-8")) <= REVIEW_LIMIT:
            break
        refs = re.findall(r"`[^`\n]+` \(sha256 `[a-f0-9]{64}`[^)\n]*\)", values[key])
        if refs:
            values[key] = "Complete evidence (read with file tools):\n" + _bullets(refs)
            text = render()
    return _sized(text, values, REVIEW_LIMIT)


def review(root, sid, *, preview=False, backend="manual"):
    rm, events, state = _load(root)
    current = state["slices"].get(sid)
    if not current or current["step"] != "reviewing":
        raise ValueError(f"{sid} is not awaiting review")
    ledger.require_artifacts(root, events)
    _, item = roadmap.slice_by_id(rm, sid)
    envelope = _frozen(root, rm, events, item, current)
    report = (
        f"05_governance/reviews/{sid.split('-')[0].lower()}/{sid}_r{current['round']}_review.md"
    )
    values = _review_values(envelope, report)
    mandatory = _render_review(root, values, _v2(rm))
    artifacts = []
    cumulative = evidence.slice_changes(events, sid)
    ledger.require_product(root, current)
    integrity.require_active(root, current, events)
    current_paths = {item["path"] for item in current["changed"]}
    manifest = current.get("manifest")
    rows = [
        f"`{item['path']}` ({item['kind']}, sha256 `{item['sha']}`, "
        f"{'current round' if item['path'] in current_paths else 'earlier round'})"
        for item in (cumulative[:8] if _v2(rm) else cumulative)
    ]
    if _v2(rm):
        manifest_ref = (
            _ref(root, manifest["path"], manifest["sha"])
            if manifest
            else _support(sid, "paths.json", _json(cumulative), artifacts)
        )
        values["diff_manifest"] = (
            f"{len(cumulative)} cumulative paths. Complete manifest: {manifest_ref}"
        )
        values["diff_manifest"] += "\n\n" + _bullets(rows)
        if len(cumulative) > 8:
            values["diff_manifest"] += (
                f"\n- {len(cumulative) - 8} additional paths in the manifest."
            )
    else:
        values["diff_manifest"] = evidence.bounded_text(
            _bullets(rows), "05_governance/ledger.jsonl", 4096
        )
    values["receipt"] = _receipt(root, current)
    if current["notes"]:
        values["coder_notes"] = _ref(root, current["notes"], current.get("notes_sha"))
        values["coder_notes"] += "\n\n" + evidence.read_excerpt(root, current["notes"], 2048)
    if current.get("outcome"):
        ref = current["outcome"]
        values["coder_notes"] += "\n\nCoder outcome: " + _ref(root, ref["path"], ref["sha"])
        values["coder_notes"] += "\n" + evidence.read_excerpt(root, ref["path"], CODING_LIMIT)
    # Admission of the mandatory text precedes Git and any bulk file reads.
    room = REVIEW_LIMIT - len(mandatory.encode("utf-8")) - 12000
    if room < 1024:
        _render_review(root, values, _v2(rm))
        room = 1024
    diff = evidence.review_diff(root, current["changed"], min(24000, room))
    if _v2(rm):
        ref = _support(sid, "diff.md", diff + "\n", artifacts)
        values["diff_evidence"] = "Bounded diff page: " + ref + "\n\n" + _diff_excerpt(diff)
    else:
        values["diff_evidence"] = diff
    text = _render_review(root, values, _v2(rm))
    if preview:
        return text
    _issue_support(root, rm, events, sid, current["round"], artifacts)
    rel = f"prompts/for_review_agent/{_next(root):03d}_{sid}_r{current['round']}.md"
    ledger.append(
        root / "05_governance/ledger.jsonl",
        {
            "ev": "artifact",
            "by": "architect",
            "scope": sid,
            "round": current["round"],
            "role": "review_prompt",
            **_save(root, rel, text),
        },
        rm,
    )
    return rel


def _holistic_report_path(root, mid, events):
    base = f"05_governance/reviews/{mid.lower()}/{mid}_holistic"
    pattern = rf"`({re.escape(base)}(?:_\d+)?_review\.md)`"
    occupied = set()
    for event in events:
        if event["ev"] != "artifact" or event["scope"] != mid:
            continue
        if event["role"] == "holistic_report":
            occupied.add(event["path"])
        elif event["role"] == "holistic_prompt":
            occupied.update(
                re.findall(pattern, evidence.read_excerpt(root, event["path"], REVIEW_LIMIT))
            )
    number = 1
    while True:
        suffix = "" if number == 1 else f"_{number}"
        rel = f"{base}{suffix}_review.md"
        if rel not in occupied and not (root / rel).exists() and not (root / rel).is_symlink():
            return rel
        number += 1


def holistic(root, mid, *, preview=False, backend="manual"):
    rm, events, state = _load(root)
    progress = state.get("holistic", {}).get(mid, {})
    if progress.get("step") in ("blocked", "close_pending"):
        raise ValueError(f"{mid} has a persisted {progress['step']} holistic decision")
    milestone = next((item for item in rm["milestones"] if item["id"] == mid), None)
    if not (
        milestone
        and milestone["holistic_review"]
        and all(state["slices"][item["id"]]["step"] == "accepted" for item in milestone["slices"])
    ):
        raise ValueError(f"{mid} is not ready for holistic review")
    ledger.require_artifacts(root, events)
    envelopes = [
        _frozen(root, rm, events, item, state["slices"][item["id"]]) for item in milestone["slices"]
    ]
    envelope = {
        **envelopes[0],
        "slice": mid,
        "round": "holistic",
        "title": milestone["title"],
        "objective": f"Judge holistic closure of {mid} across its accepted slices.",
    }
    values = _review_values(envelope, _holistic_report_path(root, mid, events))
    for _, key in ENVELOPE_SECTIONS:
        if key in ("objective", "open_findings"):
            continue
        values[key] = "\n\n".join(
            f"### {item['slice']}\n\n{_values(item).get(key, '')}"
            for item in envelopes
            if _values(item).get(key)
        )
    values["prior_findings"] = "\n\n".join(
        item["findings"] for item in envelopes if item["findings"]
    )
    for event in events:
        if event["ev"] == "holistic_reviewed" and event["milestone"] == mid:
            values["prior_findings"] += (
                "\n\nPrevious holistic decision: "
                + event["verdict"]
                + "; report "
                + _ref(root, event["report"], event["sha"])
                + "\nUnresolved finding IDs: "
                + (", ".join(event["open"]) or "none")
            )
        if event["ev"] == "resolved" and event["scope"] == mid:
            values["prior_findings"] += "\n\nRecorded resolution: " + event["reason"]
            values["prior_findings"] += "\nAuthority: " + ", ".join(
                _ref(root, ref["path"], ref["sha"]) for ref in event["authority"]
            )
        if (
            event["ev"] == "artifact"
            and event.get("scope") == mid
            and event.get("role") in ("holistic_report", "holistic_decision")
        ):
            values["prior_findings"] += (
                "\n\nPrevious holistic decision: "
                + _ref(root, event["path"], event["sha"])
                + "\n"
                + evidence.read_excerpt(root, event["path"], 4096)
            )
    values["finding_id_rule"] = (
        "Every P0-P2 finding ID must start with the affected slice ID, "
        "for example `M001-S02-H1-F1`."
    )
    mandatory = _render_review(root, values, _v2(rm))
    artifacts, rows, paths_by_slice, receipts = [], [], {}, []
    for item in milestone["slices"]:
        sid = item["id"]
        current = state["slices"][sid]
        integrity.require_active(root, current, events)
        cumulative = evidence.slice_changes(events, sid)
        paths_by_slice[sid] = [row["path"] for row in cumulative]
        rows += [{"slice": sid, **row} for row in cumulative]
        receipts.append(
            f"### {sid}\n\n"
            + _receipt(root, current)
            + "\n\nReview: "
            + _ref(root, current["report"])
        )
    values["receipt"] = "\n\n".join(receipts)
    if _v2(rm):
        values["diff_manifest"] = f"{len(rows)} cumulative paths. Complete manifest: " + _support(
            mid, "paths.json", _json(rows), artifacts
        )
    else:
        values["diff_manifest"] = evidence.bounded_text(
            _bullets(
                [
                    f"`{row['path']}` ({row['slice']}, {row['kind']}, latest round {row['round']})"
                    for row in rows
                ]
            ),
            "05_governance/ledger.jsonl",
            4096,
        )
    _render_review(root, values, _v2(rm))
    room = max(
        1024,
        REVIEW_LIMIT
        - len(mandatory.encode("utf-8"))
        - len(values["receipt"].encode("utf-8"))
        - 4096,
    )
    diff = evidence.holistic_diff(
        root, evidence.accepted_base(root, events, milestone), paths_by_slice, min(24000, room)
    )
    values["diff_evidence"] = diff
    if _v2(rm):
        values["diff_evidence"] = (
            "Bounded diff page: "
            + _support(mid, "diff.md", diff + "\n", artifacts)
            + "\n\n"
            + _diff_excerpt(diff)
        )
    text = _render_review(root, values, _v2(rm))
    if preview:
        return text
    _issue_support(root, rm, events, mid, "holistic", artifacts)
    rel = f"prompts/for_review_agent/{_next(root):03d}_{mid}_holistic.md"
    ledger.append(
        root / "05_governance/ledger.jsonl",
        {
            "ev": "artifact",
            "by": "architect",
            "scope": mid,
            "round": "holistic",
            "role": "holistic_prompt",
            **_save(root, rel, text),
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
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backend", choices=("manual", "autonomous"), default="manual")
    parser.add_argument("--root", type=Path, default=c.ROOT)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        preview = args.preview or args.check

        def render():
            options = {"preview": preview, "backend": args.backend}
            if args.holistic:
                return holistic(root, args.holistic, **options)
            if not args.slice:
                raise ValueError("provide a slice or --holistic Mnnn")
            if args.review:
                return review(root, args.slice, **options)
            return coding(root, args.slice, args.allow_dirty, **options)

        if preview:
            result = render()
        else:
            with c.mutation(root):
                result = render()
        if args.check:
            print(f"Prompt check passed: {len(result.encode('utf-8'))} UTF-8 bytes.")
            for section in re.split(r"(?m)(?=^## )", result):
                print(f"{section.splitlines()[0]}: {len(section.encode('utf-8'))} bytes")
        else:
            print(result, end="" if preview else "\n")
        return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

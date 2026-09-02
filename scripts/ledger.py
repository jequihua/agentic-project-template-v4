"""Validate, fold, and append manual-loop ledger events."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import _common as c
import _evidence as evidence
import roadmap


SCHEMA = "frutlups.ledger/1"
EVENTS = {
    "prompt",
    "artifact",
    "coded",
    "verified",
    "reviewed",
    "accepted",
    "reopened",
    "unblocked",
    "milestone_done",
    "note",
    "stop",
}
COMMON = {"schema", "t", "ev", "by"}
FIELDS = {
    "prompt": {"slice", "round", "path", "sha", "baseline"},
    "artifact": {"scope", "round", "role", "path", "sha"},
    "coded": {
        "slice",
        "round",
        "changed",
        "notes_path",
        "seat",
        "secs",
        "tokens_in",
        "tokens_out",
    },
    "verified": {"slice", "round", "receipt", "sha", "ok"},
    "reviewed": {
        "slice",
        "round",
        "report",
        "sha",
        "verdict",
        "open",
        "seat",
        "secs",
        "tokens_in",
        "tokens_out",
        "cost_usd",
    },
    "accepted": {"slice", "round", "commit"},
    "reopened": {"slice", "round", "reason"},
    "unblocked": {"slice", "round", "reason"},
    "milestone_done": {"milestone", "holistic_report"},
    "note": {"text", "slice"},
    "stop": {"reason", "detail"},
}
OPTIONAL = {
    "prompt": {"baseline"},
    "coded": {"notes_path", "seat", "secs", "tokens_in", "tokens_out"},
    "reviewed": {"seat", "secs", "tokens_in", "tokens_out", "cost_usd"},
    "accepted": {"commit"},
    "milestone_done": {"holistic_report"},
    "note": {"slice"},
}
SHA = re.compile(r"[0-9a-f]{64}$")
COMMIT = re.compile(r"[0-9a-f]{7,64}$")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
ACTORS = ("human", "architect", "frutlups")
KINDS = ("added", "modified", "deleted", "renamed")


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _validate_changes(value, line, field):
    _need(isinstance(value, list), f"{line}: {field} must be a list")
    for number, item in enumerate(value):
        valid = (
            isinstance(item, dict)
            and set(item) == {"path", "sha", "kind"}
            and item.get("kind") in KINDS
            and bool(SHA.fullmatch(str(item.get("sha", ""))))
        )
        _need(valid, f"{line}: invalid {field}[{number}]")
        c.safe_rel(item["path"])


def _validate(event, line="event"):
    _need(isinstance(event, dict), f"{line}: event must be an object")
    ev = event.get("ev")
    _need(event.get("schema") == SCHEMA and ev in EVENTS, f"{line}: invalid schema or event")
    _need(event.get("by") in ACTORS, f"{line}: invalid by")
    _need(
        isinstance(event.get("t"), str) and TIME.fullmatch(event["t"]),
        f"{line}: invalid UTC timestamp",
    )
    unknown = set(event) - COMMON - FIELDS[ev]
    missing = FIELDS[ev] - OPTIONAL.get(ev, set()) - set(event)
    _need(
        not unknown and not missing, f"{line}: unknown={sorted(unknown)} missing={sorted(missing)}"
    )
    if "round" in event:
        valid_round = type(event["round"]) is int and event["round"] >= 1
        if ev == "artifact" and event.get("role") in ("holistic_prompt", "holistic_report"):
            valid_round = event["round"] == "holistic"
        _need(valid_round, f"{line}: invalid round")
    if "slice" in event:
        _need(bool(re.fullmatch(r"M\d{3}-S\d{2}", str(event["slice"]))), f"{line}: invalid slice")
    if "milestone" in event:
        _need(bool(re.fullmatch(r"M\d{3}", str(event["milestone"]))), f"{line}: invalid milestone")
    if ev == "artifact":
        scope = str(event.get("scope", ""))
        role = event.get("role")
        slice_artifact = bool(re.fullmatch(r"M\d{3}-S\d{2}", scope))
        milestone_artifact = bool(re.fullmatch(r"M\d{3}", scope))
        valid = (
            slice_artifact
            and role == "review_prompt"
            and type(event["round"]) is int
            or milestone_artifact
            and role in ("holistic_prompt", "holistic_report")
            and event["round"] == "holistic"
        )
        valid_actor = event["by"] in ("architect", "frutlups") or (
            role == "holistic_report" and event["by"] == "human"
        )
        _need(valid and valid_actor, f"{line}: invalid artifact scope, round, role, or actor")
    for key in ("path", "receipt", "report", "notes_path", "holistic_report"):
        if key in event:
            c.safe_rel(event[key])
    if "sha" in event:
        _need(isinstance(event["sha"], str) and SHA.fullmatch(event["sha"]), f"{line}: invalid sha")
    if "commit" in event:
        _need(
            isinstance(event["commit"], str) and COMMIT.fullmatch(event["commit"]),
            f"{line}: invalid commit",
        )
    if ev == "coded":
        _validate_changes(event["changed"], line, "changed")
    if ev == "prompt" and "baseline" in event:
        _validate_changes(event["baseline"], line, "baseline")
    if ev == "verified":
        _need(isinstance(event["ok"], bool), f"{line}: ok must be boolean")
    if ev == "reviewed":
        valid = (
            event["verdict"] in ("pass", "needs_work", "blocked", "override")
            and (event["verdict"] != "override" or event["by"] == "human")
            and isinstance(event["open"], list)
            and all(isinstance(item, str) and item for item in event["open"])
        )
        _need(valid, f"{line}: invalid review fields")
    text_fields = ("reason", "detail", "text", "seat")
    numeric_fields = ("secs", "cost_usd")
    count_fields = ("tokens_in", "tokens_out")
    valid = all(
        key not in event or isinstance(event[key], str) and event[key].strip()
        for key in text_fields
    )
    valid = valid and all(
        key not in event or type(event[key]) in (int, float) and event[key] >= 0
        for key in numeric_fields
    )
    valid = valid and all(
        key not in event or type(event[key]) is int and event[key] >= 0 for key in count_fields
    )
    valid = valid and (ev != "stop" or event["by"] == "frutlups")
    valid = valid and (ev != "unblocked" or event["by"] in ("human", "architect"))
    _need(valid, f"{line}: invalid text, usage, or actor field")
    return event


def read(path: c.Path):
    if not path.exists():
        return []
    events = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw:
            continue
        try:
            events.append(_validate(json.loads(raw), f"line {number}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {number}: malformed JSON: {exc.msg}") from exc
    return events


def _state(item):
    return {
        "step": "unstarted",
        "round": 1,
        "open": [],
        "prompt": None,
        "baseline": [],
        "receipt": None,
        "report": None,
        "changed": [],
        "notes": None,
        "reopened": False,
        "unblock_reason": None,
        "corrective_rounds_used": 0,
    }


def fold(events, rm):
    states = {item["id"]: _state(item) for _, item in roadmap.slices(rm)}
    done = set()
    milestones = {item["id"]: item for item in rm["milestones"]}
    for event in events:
        ev = event["ev"]
        if ev in ("note", "stop"):
            continue
        if ev == "artifact":
            scope = event["scope"]
            if event["role"] == "review_prompt":
                _need(scope in states, f"unknown slice in ledger: {scope}")
                state = states[scope]
                ready = state["step"] == "reviewing" and event["round"] == state["round"]
                _need(ready, f"{scope}: review prompt artifact out of order")
            else:
                _need(scope in milestones, f"unknown milestone in ledger: {scope}")
                milestone = milestones[scope]
                ready = all(
                    states[item["id"]]["step"] == "accepted" for item in milestone["slices"]
                )
                _need(
                    milestone["holistic_review"] and scope not in done and ready,
                    f"{scope}: holistic prompt artifact out of order",
                )
            continue
        if ev == "milestone_done":
            mid = event["milestone"]
            _need(mid in milestones, f"unknown milestone in ledger: {mid}")
            milestone = milestones[mid]
            ready = all(states[item["id"]]["step"] == "accepted" for item in milestone["slices"])
            _need(
                milestone["holistic_review"] and mid not in done and ready,
                f"{mid}: invalid or premature milestone_done",
            )
            done.add(mid)
            continue
        sid = event.get("slice")
        _need(sid in states, f"unknown slice in ledger: {sid}")
        state = states[sid]
        round_no = event["round"]
        if ev == "prompt":
            ready = state["step"] in ("unstarted", "fix") and round_no == state["round"]
            _need(ready, f"{sid}: prompt out of order")
            state.update(step="coding", prompt=event["path"], baseline=event.get("baseline", []))
            state["corrective_rounds_used"] += round_no > 1
        elif ev == "coded":
            _need(
                state["step"] == "coding" and round_no == state["round"],
                f"{sid}: coded out of order",
            )
            state.update(step="verifying", changed=event["changed"], notes=event.get("notes_path"))
        elif ev == "verified":
            _need(
                state["step"] == "verifying" and round_no == state["round"],
                f"{sid}: verified out of order",
            )
            next_step = "reviewing" if event["ok"] else "fix"
            next_round = round_no if event["ok"] else round_no + 1
            state.update(step=next_step, receipt=event["receipt"], round=next_round)
        elif ev == "reviewed":
            _need(
                state["step"] == "reviewing" and round_no == state["round"],
                f"{sid}: reviewed out of order",
            )
            step = {
                "pass": "accept_pending",
                "override": "accept_pending",
                "needs_work": "fix",
                "blocked": "blocked",
            }[event["verdict"]]
            state.update(
                step=step,
                report=event["report"],
                open=event["open"],
                round=round_no + (step == "fix"),
                unblock_reason=None,
            )
        elif ev == "accepted":
            _need(
                state["step"] == "accept_pending" and round_no == state["round"],
                f"{sid}: accepted out of order",
            )
            state.update(step="accepted", open=[], reopened=False, unblock_reason=None)
        elif ev == "reopened":
            valid = state["step"] == "accepted" and round_no == state["round"] + 1
            _need(valid, f"{sid}: reopened out of order")
            state.update(step="fix", round=round_no, open=[], reopened=True)
            done.discard(sid.split("-")[0])
        elif ev == "unblocked":
            valid = state["step"] == "blocked" and round_no == state["round"] + 1
            _need(valid, f"{sid}: unblocked out of order")
            state.update(step="fix", round=round_no, unblock_reason=event["reason"])
    return {"slices": states, "milestones_done": done, "events": len(events)}


def append(path: c.Path, event, rm):
    candidate = {"schema": SCHEMA, "t": c.now(), **event}
    _validate(candidate)
    events = read(path)
    fold(events + [candidate], rm)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    return candidate


def next_slice(rm, state):
    for _, item in roadmap.slices(rm):
        current = state["slices"][item["id"]]
        if current["reopened"] and current["step"] != "accepted":
            return item["id"]
    for milestone in rm["milestones"]:
        if milestone["status"] == "active":
            return next(
                (
                    item["id"]
                    for item in milestone["slices"]
                    if state["slices"][item["id"]]["step"] != "accepted"
                ),
                None,
            )
    return None


def status_text(rm, state):
    lines = [
        f"{item['id']} r{state['slices'][item['id']]['round']} "
        f"{state['slices'][item['id']]['step']}"
        for _, item in roadmap.slices(rm)
    ]
    return "\n".join(lines + [f"next: {next_slice(rm, state) or 'none'}"])


parse_review = evidence.parse_review
changed_files = evidence.changed_files
prompt_baseline = evidence.prompt_baseline
fence = evidence.fence
_rel_file = evidence.rel_file


def _artifacts_for(root, events, sid):
    paths = {"05_governance/ledger.jsonl", "05_governance/backlog.md"}
    for event in events:
        belongs = event.get("slice") == sid or event.get("scope") == sid
        if event.get("scope") == sid.split("-")[0] and event["ev"] == "artifact":
            belongs = True
        if not belongs:
            continue
        paths.update(
            event[key] for key in ("path", "notes_path", "receipt", "report") if event.get(key)
        )
        if event["ev"] == "coded":
            paths.update(item["path"] for item in event["changed"])
    return sorted(paths)


def artifact_errors(root, events):
    errors = []
    for event in events:
        for key in ("path", "receipt", "report"):
            if event.get(key):
                path = c.repo_path(root, event[key])
                if path.is_symlink() or not path.is_file() or c.sha(path) != event["sha"]:
                    errors.append(f"drift: {event[key]}")
        if event.get("notes_path"):
            path = c.repo_path(root, event["notes_path"])
            if path.is_symlink() or not path.is_file():
                errors.append(f"missing: {event['notes_path']}")
    return errors


def require_artifacts(root, events):
    errors = artifact_errors(root, events)
    if errors:
        raise ValueError("immutable evidence drift: " + ", ".join(errors))


def check(root, rm, events):
    fold(events, rm)
    errors = artifact_errors(root, events)
    latest = {}
    for event in events:
        if event["ev"] == "coded":
            for item in event["changed"]:
                latest[item["path"]] = item
    for rel, item in latest.items():
        path = c.repo_path(root, rel)
        matches_latest = (
            item["kind"] == "deleted"
            and not path.exists()
            and not path.is_symlink()
            or item["kind"] != "deleted"
            and path.is_file()
            and not path.is_symlink()
            and c.sha(path) == item["sha"]
        )
        if matches_latest or evidence.matches_head(root, rel):
            continue
        if item["kind"] == "deleted":
            errors.append(f"drift: {rel} was deleted")
        else:
            errors.append(f"drift: {rel}")
    return errors


def _parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=c.Path, default=c.ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prompt")
    item.add_argument("slice")
    item.add_argument("path")
    item.add_argument("--allow-dirty", action="store_true")
    item.add_argument("--by", choices=ACTORS, default="architect")
    item = sub.add_parser("coded")
    item.add_argument("slice")
    item.add_argument("--notes")
    item.add_argument("--by", choices=ACTORS, default="architect")
    item = sub.add_parser("record")
    item.add_argument("report")
    item.add_argument("--milestone")
    item.add_argument("--by", choices=ACTORS, default="architect")
    item = sub.add_parser("accept")
    item.add_argument("slice")
    item.add_argument("--commit", action="store_true")
    item.add_argument("--commit-id")
    item.add_argument("--by", choices=ACTORS, default="architect")
    item = sub.add_parser("reopen")
    item.add_argument("slice")
    item.add_argument("--reason", required=True)
    item.add_argument("--by", choices=ACTORS, default="human")
    item = sub.add_parser("unblock")
    item.add_argument("slice")
    item.add_argument("--reason", required=True)
    item.add_argument("--by", choices=("human", "architect"), default="human")
    sub.add_parser("status")
    item = sub.add_parser("index")
    item.add_argument("--output")
    sub.add_parser("check")
    return parser


def _holistic_events(review, milestone, state, by, report):
    slice_ids = [item["id"] for item in milestone["slices"]]
    for finding in review["findings"]:
        if finding["severity"] not in ("P0", "P1", "P2"):
            continue
        if not any(finding["id"].startswith(sid + "-") for sid in slice_ids):
            raise ValueError("every holistic P0-P2 finding id must start with its slice id")
    if review["verdict"] in ("pass", "override"):
        return [
            {
                "ev": "milestone_done",
                "by": by,
                "milestone": milestone["id"],
                "holistic_report": report,
            }
        ]
    groups = {}
    for finding in review["open"]:
        sid = next((value for value in slice_ids if finding.startswith(value + "-")), None)
        if not sid or state["slices"][sid]["step"] != "accepted":
            raise ValueError("every holistic open finding must start with an accepted slice id")
        groups.setdefault(sid, []).append(finding)
    if not groups:
        raise ValueError("a non-pass holistic review must have open P0-P2 findings")
    return [
        {
            "ev": "reopened",
            "by": by,
            "slice": sid,
            "round": state["slices"][sid]["round"] + 1,
            "reason": "holistic findings " + ", ".join(findings),
        }
        for sid, findings in groups.items()
    ]


def _record(root, value, args, rm, events, state):
    rel, path = _rel_file(root, value)
    review = parse_review(path.read_text(encoding="utf-8"))
    ledger_path = root / "05_governance/ledger.jsonl"
    if args.milestone:
        milestone = next((item for item in rm["milestones"] if item["id"] == args.milestone), None)
        ready = (
            milestone
            and milestone["holistic_review"]
            and all(
                state["slices"][item["id"]]["step"] == "accepted" for item in milestone["slices"]
            )
        )
        valid = (
            review["identity"] == args.milestone
            and review["round"] is None
            and ready
            and (review["verdict"] != "override" or args.by == "human")
        )
        if not valid:
            raise ValueError("holistic report identity, authority, or readiness mismatch")
        candidates = [
            {
                "ev": "artifact",
                "by": args.by,
                "scope": args.milestone,
                "round": "holistic",
                "role": "holistic_report",
                "path": rel,
                "sha": c.sha(path),
            },
            *_holistic_events(review, milestone, state, args.by, rel),
        ]
        trial = list(events)
        for candidate in candidates:
            complete = {"schema": SCHEMA, "t": c.now(), **candidate}
            _validate(complete)
            fold(trial + [complete], rm)
            trial.append(complete)
        for candidate in candidates:
            append(ledger_path, candidate, rm)
        print(f"{args.milestone} holistic {review['verdict']}")
        return
    sid = review["identity"]
    round_no = review["round"]
    current = state["slices"].get(sid)
    if not current or current["step"] != "reviewing" or round_no != current["round"]:
        raise ValueError("review identity/round is not awaiting review")
    waived = any(item["disposition"] == "waived_by_human" for item in review["findings"])
    if (review["verdict"] == "override" or waived) and args.by != "human":
        raise ValueError("override or waiver requires --by human")
    carried = [
        f"- {item['id']}: {item['summary']}"
        for item in review["findings"]
        if item["severity"] == "P3" and item["disposition"] == "carried"
    ]
    backlog = root / "05_governance/backlog.md"
    backlog_text = None
    if carried:
        old = backlog.read_text(encoding="utf-8")
        missing = [line for line in carried if line.split(":", 1)[0][2:] not in old]
        if missing:
            backlog_text = old.rstrip() + "\n\n" + "\n".join(missing) + "\n"
    event = {
        "ev": "reviewed",
        "by": args.by,
        "slice": sid,
        "round": round_no,
        "report": rel,
        "sha": c.sha(path),
        "verdict": review["verdict"],
        "open": review["open"],
    }
    append(ledger_path, event, rm)
    if backlog_text is not None:
        c.atomic_text(backlog, backlog_text)
    print(f"{sid} r{round_no} review {review['verdict']} open={len(review['open'])}")


def _git_identity(root):
    for key in ("user.email", "user.name"):
        result = c.git(root, "config", "--get", key, check=False, text=True)
        if result.returncode or not result.stdout.strip():
            raise ValueError(f"git {key} is not configured; configure it before --commit")


def _coded(root, args, rm, events, state, ledger_path):
    _, item = roadmap.slice_by_id(rm, args.slice)
    current = state["slices"][args.slice]
    if current["step"] != "coding":
        raise ValueError(f"{args.slice} is {current['step']}, not coding")
    notes = _rel_file(root, args.notes)[0] if args.notes else None
    owned = {
        "05_governance/ledger.jsonl",
        "05_governance/backlog.md",
        current["prompt"],
    }
    if notes:
        owned.add(notes)
    baseline = {(entry["path"], entry["sha"], entry["kind"]) for entry in current["baseline"]}
    changed = [
        entry
        for entry in changed_files(root)
        if entry["path"] not in owned
        and (entry["path"], entry["sha"], entry["kind"]) not in baseline
    ]
    violations = fence(changed, roadmap.effective_prefixes(rm, item), rm["forbidden"])
    if violations:
        raise ValueError("write boundary violation: " + ", ".join(violations))
    event = {
        "ev": "coded",
        "by": args.by,
        "slice": args.slice,
        "round": current["round"],
        "changed": changed,
    }
    if notes:
        event["notes_path"] = notes
    append(ledger_path, event, rm)
    print(f"{args.slice} r{current['round']} coded changed={len(changed)}")


def main(argv=None):
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    ledger_path = root / "05_governance/ledger.jsonl"
    try:
        rm = roadmap.load(root)
        events = read(ledger_path)
        state = fold(events, rm)
        if args.command == "prompt":
            roadmap.slice_by_id(rm, args.slice)
            current = state["slices"][args.slice]
            if current["step"] not in ("unstarted", "fix"):
                raise ValueError(f"{args.slice} is {current['step']}, not ready for a prompt")
            require_artifacts(root, events)
            rel, path = _rel_file(root, args.path)
            baseline = prompt_baseline(
                root, rm, events, args.slice, args.allow_dirty, prospective=(rel,)
            )
            event = {
                "ev": "prompt",
                "by": args.by,
                "slice": args.slice,
                "round": current["round"],
                "path": rel,
                "sha": c.sha(path),
            }
            if baseline:
                event["baseline"] = baseline
            append(ledger_path, event, rm)
            print(f"{args.slice} r{current['round']} prompt -> {rel}")
        elif args.command == "coded":
            _coded(root, args, rm, events, state, ledger_path)
        elif args.command == "record":
            _record(root, args.report, args, rm, events, state)
        elif args.command == "accept":
            current = state["slices"][args.slice]
            if current["step"] != "accept_pending":
                raise ValueError(f"{args.slice} is {current['step']}, not accept_pending")
            if args.commit:
                _git_identity(root)
            event = {
                "ev": "accepted",
                "by": args.by,
                "slice": args.slice,
                "round": current["round"],
            }
            if args.commit_id:
                event["commit"] = args.commit_id
            append(ledger_path, event, rm)
            if args.commit:
                paths = _artifacts_for(root, read(ledger_path), args.slice)
                c.git(root, "add", "-A", "--", *paths)
                c.git(root, "commit", "-m", f"Accept {args.slice} round {current['round']}")
                commit = c.git(root, "rev-parse", "HEAD", text=True).stdout.strip()
                print(f"{args.slice} accepted commit {commit}")
            else:
                print(f"{args.slice} accepted")
        elif args.command in ("reopen", "unblock"):
            current = state["slices"][args.slice]
            expected = "accepted" if args.command == "reopen" else "blocked"
            if current["step"] != expected:
                raise ValueError(f"{args.slice} is not {expected}")
            event = {
                "ev": "reopened" if args.command == "reopen" else "unblocked",
                "by": args.by,
                "slice": args.slice,
                "round": current["round"] + 1,
                "reason": args.reason,
            }
            append(ledger_path, event, rm)
            print(f"{args.slice} {event['ev']} r{event['round']}")
        elif args.command == "status":
            print(status_text(rm, state))
        elif args.command == "index":
            rows = ["| Slice | Round | Verdict | Report |", "| --- | ---: | --- | --- |"]
            rows += [
                f"| {event['slice']} | {event['round']} | {event['verdict']} | "
                f"`{event['report']}` |"
                for event in events
                if event["ev"] == "reviewed"
            ]
            text = "# Review index\n\n" + "\n".join(rows) + "\n"
            if args.output:
                c.atomic_text(c.repo_path(root, c.cli_rel(args.output)), text)
            else:
                print(text, end="")
        else:
            errors = check(root, rm, events)
            if errors:
                print("\n".join(f"error: {item}" for item in errors), file=sys.stderr)
                return 2
            print("ledger: ok")
        return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

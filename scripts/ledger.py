"""Validate, fold, and append manual-loop ledger events."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
import re
import sys

import _common as c
import _evidence as evidence
import roadmap
import _protocol as protocol
import _git as gitops
import _findings as findings
import _integrity as integrity


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
        "cost_usd",
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
    "coded": {"notes_path", "seat", "secs", "tokens_in", "tokens_out", "cost_usd"},
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
    if event.get("schema") == protocol.SCHEMA:
        return protocol.validate(event, _validate)
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
    upgraded = False
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw:
            continue
        try:
            event = _validate(json.loads(raw), f"line {number}")
            _need(
                not upgraded or event["schema"] == protocol.SCHEMA, "legacy event after /2 history"
            )
            upgraded = upgraded or event["schema"] == protocol.SCHEMA
            events.append(event)
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
        "envelope": None,
        "manifest": None,
        "outcome": None,
        "blocker": None,
        "resolution": None,
        "notes_sha": None,
    }


def fold(events, rm):
    states = {item["id"]: _state(item) for _, item in roadmap.slices(rm)}
    done = set()
    milestones = {item["id"]: item for item in rm["milestones"]}
    extras = {"holistic": {}, "attempts": {}, "checkpoints": {}, "intents": {}, "cancelled": set()}
    upgraded = False
    for event in events:
        is_v2 = event.get("schema") == protocol.SCHEMA
        _need(not is_v2 or rm["schema"] == protocol.ROADMAP, "/2 history requires /2 roadmap")
        _need(not upgraded or is_v2, "legacy event after /2 history")
        upgraded = upgraded or is_v2
        if is_v2 and protocol.apply(event, states, milestones, done, extras):
            continue
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
            if is_v2:
                _need(
                    extras["holistic"].get(mid, {}).get("step") == "close_pending",
                    "milestone close requires recorded passing holistic review",
                )
            ready = all(states[item["id"]]["step"] == "accepted" for item in milestone["slices"])
            _need(
                milestone["holistic_review"] and mid not in done and ready,
                f"{mid}: invalid or premature milestone_done",
            )
            done.add(mid)
            if is_v2:
                extras["holistic"].setdefault(mid, {})["step"] = "done"
            continue
        sid = event.get("slice")
        _need(sid in states, f"unknown slice in ledger: {sid}")
        state = states[sid]
        round_no = event["round"]
        if ev == "prompt":
            ready = state["step"] in ("unstarted", "fix") and round_no == state["round"]
            _need(ready, f"{sid}: prompt out of order")
            state.update(step="coding", prompt=event["path"], baseline=event.get("baseline", []))
            state["envelope"] = event.get("envelope")
            state["corrective_rounds_used"] += round_no > 1
        elif ev == "coded":
            _need(
                state["step"] == "coding" and round_no == state["round"],
                f"{sid}: coded out of order",
            )
            state.update(step="verifying", changed=event["changed"], notes=event.get("notes_path"))
            state.update(
                manifest=event.get("manifest"),
                outcome=event.get("outcome"),
                notes_sha=event.get("notes_sha"),
            )
            if event.get("result", "implemented") != "implemented":
                state.update(step="blocked", blocker=event["outcome"])
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
            if step == "blocked":
                state["blocker"] = {"path": event["report"], "sha": event["sha"]}
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
            if is_v2 and sid.split("-")[0] in extras["holistic"]:
                extras["holistic"][sid.split("-")[0]].update(
                    step="reviewing", resolution="Slice reopened: " + event["reason"]
                )
        elif ev == "unblocked":
            valid = state["step"] == "blocked" and round_no == state["round"] + 1
            _need(valid, f"{sid}: unblocked out of order")
            state.update(step="fix", round=round_no, unblock_reason=event["reason"])
    return {"slices": states, "milestones_done": done, "events": len(events), **extras}


def append(path: c.Path, event, rm):
    with c.command_scope(), c.writer_lock(path.resolve().parents[1]):
        return _append(path, event, rm)


def _append(path: c.Path, event, rm):
    schema = protocol.SCHEMA if rm["schema"] == protocol.ROADMAP else SCHEMA
    candidate = {"schema": schema, "t": c.now(), **event}
    _need(candidate["schema"] == schema, "writer schema differs from declared roadmap")
    _validate(candidate)
    events = read(path)
    if path.exists():
        data = path.read_bytes()
        _need(
            not data or data.endswith(b"\n"),
            "ledger has an incomplete final line; preserve and repair it",
        )
    if candidate["schema"] == protocol.SCHEMA:
        protocol.ensure_writable(
            path.resolve().parents[1],
            rm,
            allow_attempt=candidate["ev"] == "attempt_finished",
            cancellation=candidate["ev"] == "commit_cancelled",
        )
        if candidate["ev"] == "commit_cancelled":
            import _commit

            _commit.cancel_check(path.resolve().parents[1], events, rm, candidate["operation"])
        else:
            root = path.resolve().parents[1]
            errors = artifact_errors(root, [candidate]) + integrity.errors(
                root, events + [candidate], rm
            )
            _need(not errors, "invalid immutable evidence: " + ", ".join(errors))
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
            for item in milestone["slices"]:
                if state["slices"][item["id"]]["step"] != "accepted":
                    return item["id"]
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
        if event.get("milestone") == sid.split("-")[0]:
            belongs = True
        if not belongs:
            continue
        paths.update(
            event[key] for key in ("path", "notes_path", "receipt", "report") if event.get(key)
        )
        paths.update(ref["path"] for ref in protocol.event_references(event))
        if event["ev"] == "coded":
            paths.update(item["path"] for item in event["changed"])
    return sorted(paths)


def artifact_errors(root, events):
    errors = []
    for event in events:
        for ref in protocol.event_references(event):
            path = c.repo_path(root, ref["path"])
            if path.is_symlink() or not path.is_file() or c.sha(path) != ref["sha"]:
                errors.append(f"drift: {ref['path']}")
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
    errors += integrity.errors(root, events, roadmap.load(root))
    if errors:
        raise ValueError("immutable evidence drift: " + ", ".join(errors))


def check(root, rm, events):
    fold(events, rm)
    errors = artifact_errors(root, events)
    errors += integrity.errors(root, events, rm)
    try:
        findings.project(root, events)
        if any(x.get("commit_intent") for x in events):
            import _commit

            _commit.status(root, events, rm)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
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
    item.add_argument("--result", choices=sorted(protocol.RESULTS), default="implemented")
    item.add_argument("--outcome")
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
    item = sub.add_parser("blocked")
    item.add_argument("slice")
    item.add_argument(
        "--result", choices=sorted(protocol.RESULTS - {"implemented"}), default="blocked_authority"
    )
    item.add_argument("--outcome")
    item.add_argument("--notes")
    for name in ("requirement", "reason", "actor", "action"):
        item.add_argument("--" + name)
    item.add_argument("--remaining", action="append", default=[])
    item.add_argument("--evidence", action="append", default=[])
    item.add_argument("--authority", action="append", default=[])
    item.add_argument("--by", choices=ACTORS, default="architect")
    item = sub.add_parser("resolve")
    item.add_argument("scope")
    item.add_argument("--reason", required=True)
    item.add_argument("--authority", action="append", required=True)
    item.add_argument("--by", choices=("human", "architect"), default="human")
    item = sub.add_parser("close")
    item.add_argument("milestone")
    item.add_argument("--commit", action="store_true")
    item.add_argument("--by", choices=ACTORS, default="architect")
    item = sub.add_parser("recover")
    item.add_argument("--execute", action="store_true")
    item.add_argument("--git-resolved", metavar="OPERATION")
    item.add_argument("--reason")
    item.add_argument("--by", choices=("human", "architect"), default="human")
    item = sub.add_parser("cancel")
    item.add_argument("operation")
    item.add_argument("--reason", required=True)
    item.add_argument("--retain-acceptance", action="store_true")
    item.add_argument("--git-resolved", action="store_true")
    item.add_argument("--by", choices=("human", "architect"), default="human")
    item = sub.add_parser("attempt")
    item.add_argument("event", help="JSON attempt_started/attempt_finished/review_checkpoint")
    sub.add_parser("reconcile")
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


def _backlog_text(path, findings):
    carried = [
        f"- {item['id']}: {item['summary']}"
        for item in findings
        if item["severity"] == "P3" and item["disposition"] == "carried"
    ]
    if carried:
        old = path.read_text(encoding="utf-8")
        missing = [line for line in carried if line.split(":", 1)[0][2:] not in old]
        if missing:
            return old.rstrip() + "\n\n" + "\n".join(missing) + "\n"
    return None


def _record(root, value, args, rm, events, state):
    if rm["schema"] == protocol.ROADMAP:
        require_artifacts(root, events)
    rel, path = _rel_file(root, value)
    review = parse_review(path.read_text(encoding="utf-8"))
    waived = any(
        item["disposition"] == "waived_by_human"
        for item in review["findings"] + findings.updates(path.read_text(encoding="utf-8"))
    )
    if (review["verdict"] == "override" or waived) and args.by != "human":
        raise ValueError("override or waiver requires --by human")
    ledger_path = root / "05_governance/ledger.jsonl"
    backlog = root / "05_governance/backlog.md"
    backlog_text = _backlog_text(backlog, review["findings"])
    if args.milestone:
        if rm["schema"] == protocol.ROADMAP:
            prior = state["holistic"].get(args.milestone, {})
            if prior.get("event", {}).get("report") == rel:
                _need(prior["event"]["sha"] == c.sha(path), "holistic report drift")
                if prior["step"] == "close_pending":
                    _close(root, args.milestone, args.by, False, rm, events, state)
                else:
                    print(f"{args.milestone} report already recorded: {prior['step']}")
                return
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
        if rm["schema"] == protocol.ROADMAP:
            findings.validate_record(root, events, rel, c.sha(path), args.by)
            append(
                ledger_path,
                {
                    "ev": "holistic_reviewed",
                    "by": args.by,
                    "milestone": args.milestone,
                    "report": rel,
                    "sha": c.sha(path),
                    "verdict": review["verdict"],
                    "open": review["open"],
                },
                rm,
            )
            findings.reconcile(root, read(ledger_path))
            print(f"{args.milestone} holistic {review['verdict']}")
            return
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
        if backlog_text is not None:
            c.atomic_text(backlog, backlog_text)
        print(f"{args.milestone} holistic {review['verdict']}")
        return
    sid = review["identity"]
    round_no = review["round"]
    current = state["slices"].get(sid)
    if not current or current["step"] != "reviewing" or round_no != current["round"]:
        raise ValueError("review identity/round is not awaiting review")
    require_product(root, current)
    if rm["schema"] == protocol.ROADMAP:
        integrity.require_active(root, current, events, extra=(rel,))
        findings.validate_record(root, events, rel, c.sha(path), args.by, current)
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
    if rm["schema"] == protocol.ROADMAP:
        findings.reconcile(root, read(ledger_path))
    elif backlog_text is not None:
        c.atomic_text(backlog, backlog_text)
    print(f"{sid} r{round_no} review {review['verdict']} open={len(review['open'])}")


def _git_identity(root):
    for key in ("user.email", "user.name"):
        result = c.git(root, "config", "--get", key, check=False, text=True)
        if result.returncode or not result.stdout.strip():
            raise ValueError(f"git {key} is not configured; configure it before --commit")


def _coded(root, args, rm, events, state, ledger_path):
    require_artifacts(root, events)
    _, item = roadmap.slice_by_id(rm, args.slice)
    current = state["slices"][args.slice]
    if current["step"] != "coding":
        raise ValueError(f"{args.slice} is {current['step']}, not coding")
    notes = _rel_file(root, args.notes)[0] if args.notes else None
    owned = evidence._known_baseline_paths(events, args.slice)
    if notes:
        owned.add(notes)
    outcome_ref = None
    if getattr(args, "outcome", None):
        outcome_ref = _ref(root, args.outcome)
        owned.add(outcome_ref["path"])
    baseline = {(entry["path"], entry["sha"], entry["kind"]) for entry in current["baseline"]}
    changed = [
        entry
        for entry in changed_files(root)
        if entry["path"] not in owned
        and (entry["path"], entry["sha"], entry["kind"]) not in baseline
    ]
    allowed, forbidden = roadmap.effective_prefixes(rm, item), rm["forbidden"]
    version2 = rm["schema"] == protocol.ROADMAP
    if version2:
        envelope = protocol.read_reference(root, current["envelope"])
        allowed, forbidden = envelope["allowed_prefixes"], envelope["forbidden"]
        prior = {}
        for old in events:
            if old["ev"] == "coded" and old["slice"] == args.slice:
                prior.update({x["path"]: {**x, "round": old["round"]} for x in old["changed"]})
        seen = {x["path"] for x in changed}
        for rel, old in prior.items():
            if rel in seen:
                continue
            path = c.repo_path(root, rel)
            if old["kind"] != "deleted" and not path.exists():
                changed.append({"path": rel, "kind": "deleted", "sha": old["sha"]})
            elif path.is_file() and (old["kind"] == "deleted" or c.sha(path) != old["sha"]):
                # Reopened work can observe a retained path changed by a later
                # accepted slice. Record the current identity, preserving history.
                changed.append({"path": rel, "kind": "modified", "sha": c.sha(path)})
    violations = fence(changed, allowed, forbidden)
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
    if version2:
        result = getattr(args, "result", "implemented")
        if args.command == "blocked" and not outcome_ref:
            _need(
                all(
                    getattr(args, key, None) for key in ("requirement", "reason", "actor", "action")
                ),
                "blocked needs --outcome or --requirement, --reason, --actor and --action",
            )
            value = {
                "schema": "frutlups.outcome/2",
                "slice": args.slice,
                "round": current["round"],
                "invocation": f"manual-{args.slice}-r{current['round']}",
                "outcome": result,
                **{key: getattr(args, key) for key in ("requirement", "reason", "actor", "action")},
                "remaining": args.remaining,
                "evidence": [_ref(root, x) for x in args.evidence],
                "authority": [c.cli_rel(x) for x in args.authority],
            }
            outcome_ref = _save_json(root, args.slice, current["round"], "outcome", value)
        if outcome_ref:
            value = protocol.outcome(root, outcome_ref, args.slice, current["round"])
            _need(value["outcome"] == result, "outcome differs from explicit result")
            event["outcome"] = outcome_ref
        _need(result == "implemented" or outcome_ref, "blocked result requires --outcome")
        prior.update({x["path"]: {**x, "round": current["round"]} for x in changed})
        manifest = {
            "schema": "frutlups.manifest/2",
            "slice": args.slice,
            "round": current["round"],
            "changed": [prior[x] for x in sorted(prior)],
        }
        event.update(
            result=result,
            manifest=_save_json(root, args.slice, current["round"], "manifest", manifest),
        )
        if notes:
            event["notes_sha"] = c.sha(root / notes)
    else:
        _need(
            not outcome_ref and getattr(args, "result", "implemented") == "implemented",
            "typed outcomes require /2 roadmap",
        )
    gitops.guard_index(root, gitops.approved_paths(root, [*owned, *[x["path"] for x in changed]]))
    append(ledger_path, event, rm)
    print(f"{args.slice} r{current['round']} coded changed={len(changed)}")


def _ref(root, value):
    rel, path = _rel_file(root, value)
    return {"path": rel, "sha": c.sha(path)}


def _save_json(root, sid, round_no, label, value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    digest = c.evidence_sha_bytes(text.encode("utf-8"))
    directory = f"05_governance/reviews/{sid.split('-')[0].lower()}"
    rel = f"{directory}/{sid}_r{round_no}_{label}_{digest[:16]}.json"
    path = c.repo_path(root, rel)
    if path.exists():
        _need(c.sha(path) == digest, "immutable artifact collision")
    else:
        c.artifact_text(path, text)
    return {"path": rel, "sha": digest}


def require_product(root, current):
    """An active receipt/report cannot approve edits made after the coded handoff."""
    rows = current["changed"]
    if current.get("manifest"):
        rows = protocol.manifest(root, current["manifest"])["changed"]
    for item in rows:
        path = c.repo_path(root, item["path"])
        matches = (
            (not path.exists() and not path.is_symlink())
            if item["kind"] == "deleted"
            else (path.is_file() and not path.is_symlink() and c.sha(path) == item["sha"])
        )
        _need(matches, "active product drift: " + item["path"])


def _close(root, mid, by, commit, rm, events, state):
    require_artifacts(root, events)
    current = state["holistic"].get(mid, {})
    _need(current.get("step") == "close_pending", "milestone is not close_pending")
    milestone = next(x for x in rm["milestones"] if x["id"] == mid)
    paths = {"05_governance/ledger.jsonl", "05_governance/backlog.md", current["event"]["report"]}
    for item in milestone["slices"]:
        integrity.require_active(
            root, state["slices"][item["id"]], events, extra=(current["event"]["report"],)
        )
        paths.update(_artifacts_for(root, events, item["id"]))
    event = {
        "ev": "milestone_done",
        "by": by,
        "milestone": mid,
        "holistic_report": current["event"]["report"],
    }
    _approve(root, event, paths, mid, f"Close {mid}", commit, rm)


def _approve(root, event, paths, scope, message, commit, rm):
    paths = gitops.approved_paths(root, paths)
    if commit:
        gitops.guard_index(root, paths)
        _git_identity(root)
        if rm["schema"] == protocol.ROADMAP:
            import _commit

            event["commit_intent"] = _commit.request_intent(
                root,
                paths,
                scope,
                message,
                rm,
                "05_governance/reviews/" + scope.split("-")[0].lower(),
            )
    append(root / "05_governance/ledger.jsonl", event, rm)
    if commit:
        if rm["schema"] == protocol.ROADMAP:
            print(
                json.dumps(
                    _commit.recover(root, read(root / "05_governance/ledger.jsonl"), rm, True)
                )
            )
        else:
            gitops.stage_exact(root, paths)
            gitops.run(root, "commit", "-m", message)
    print(f"{scope} {event['ev']}")


def _execute(args):
    root = args.root.resolve()
    ledger_path = root / "05_governance/ledger.jsonl"
    try:
        with c.artifact_batch(root):
            rm = roadmap.load(root)
            events = read(ledger_path)
            state = fold(events, rm)
            if args.command == "prompt":
                _need(
                    rm["schema"] != protocol.ROADMAP,
                    "saved-prompt registration is legacy /1 only; use prompt.py for /2",
                )
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
            elif args.command in ("coded", "blocked"):
                _coded(root, args, rm, events, state, ledger_path)
            elif args.command == "record":
                _record(root, args.report, args, rm, events, state)
            elif args.command == "accept":
                current = state["slices"][args.slice]
                if current["step"] != "accept_pending":
                    raise ValueError(f"{args.slice} is {current['step']}, not accept_pending")
                require_artifacts(root, events)
                require_product(root, current)
                integrity.require_active(root, current, events)
                _need(not args.commit or not args.commit_id, "choose --commit or --commit-id")
                _need(
                    rm["schema"] != protocol.ROADMAP or not args.commit_id,
                    "/2 uses verified commit intents; --commit-id is legacy-only",
                )
                event = {
                    "ev": "accepted",
                    "by": args.by,
                    "slice": args.slice,
                    "round": current["round"],
                }
                if args.commit_id:
                    event["commit"] = args.commit_id
                paths = _artifacts_for(root, events, args.slice)
                _approve(
                    root,
                    event,
                    paths,
                    args.slice,
                    f"Accept {args.slice} round {current['round']}",
                    args.commit,
                    rm,
                )
            elif args.command in ("reopen", "unblock"):
                _need(
                    args.command != "unblock" or rm["schema"] != protocol.ROADMAP,
                    "/2 blockers need resolve --reason --authority",
                )
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
                if rm["schema"] == protocol.ROADMAP:
                    import _commit

                    for row in _commit.status(root, events, rm):
                        print(f"commit {row['id']}: {row['state']}")
                    for mid, item in state["holistic"].items():
                        print(f"{mid} holistic: {item['step']}")
                    for key, item in state["attempts"].items():
                        if not item["finish"]:
                            print(f"unresolved invocation: {key}")
                    for milestone in rm["milestones"]:
                        complete = all(
                            state["slices"][x["id"]]["step"] == "accepted"
                            for x in milestone["slices"]
                        )
                        complete = complete and (
                            not milestone["holistic_review"]
                            or milestone["id"] in state["milestones_done"]
                        )
                        if milestone["status"] == "done" and not complete:
                            print(
                                f"warning: {milestone['id']} declared done without ledger closure"
                            )
            elif args.command == "resolve":
                require_artifacts(root, events)
                append(
                    ledger_path,
                    {
                        "ev": "resolved",
                        "by": args.by,
                        "scope": args.scope,
                        "reason": args.reason,
                        "authority": [_ref(root, x) for x in args.authority],
                    },
                    rm,
                )
                print(f"{args.scope} resolved")
            elif args.command == "close":
                _close(root, args.milestone, args.by, args.commit, rm, events, state)
            elif args.command == "recover":
                import _commit

                if args.git_resolved:
                    _need(
                        bool(args.reason and args.reason.strip()),
                        "Git attribution requires --reason",
                    )
                    _commit.resolve_inflight(root, args.git_resolved, args.reason, args.by)
                print(json.dumps(_commit.recover(root, events, rm, args.execute), indent=2))
            elif args.command == "cancel":
                import _commit

                if args.git_resolved:
                    _commit.resolve_inflight(root, args.operation, args.reason, args.by)
                _commit.cancel_check(root, events, rm, args.operation)
                append(
                    ledger_path,
                    {
                        "ev": "commit_cancelled",
                        "by": args.by,
                        "operation": args.operation,
                        "reason": args.reason,
                        "retain_acceptance": args.retain_acceptance,
                    },
                    rm,
                )
                print(f"commit {args.operation} cancelled; files and index preserved")
            elif args.command == "attempt":
                with _rel_file(root, args.event)[1].open("rb") as stream:
                    data = stream.read(protocol.EVENT_LIMIT + 1)
                _need(len(data) <= protocol.EVENT_LIMIT, "attempt event exceeds 2 MiB")
                value = json.loads(data)
                _need(
                    isinstance(value, dict)
                    and value.get("ev")
                    in ("attempt_started", "attempt_finished", "review_checkpoint"),
                    "attempt accepts only reservation, completion or review checkpoint",
                )
                require_artifacts(root, events)
                append(ledger_path, value, rm)
                print(value["ev"])
            elif args.command == "reconcile":
                require_artifacts(root, events)
                for message in findings.reconcile(root, events):
                    print("warning: " + message)
                print("backlog reconciled")
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


def main(argv=None):
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    readonly = args.command in ("status", "check") or args.command == "index" and not args.output
    readonly = readonly or args.command == "recover" and not args.execute and not args.git_resolved
    try:
        guard = nullcontext() if readonly else c.writer_lock(root)
        with c.command_scope(), guard:
            if not readonly and args.command not in ("recover", "cancel"):
                protocol.ensure_writable(root, allow_attempt=args.command == "attempt")
            return _execute(args)
    except (KeyError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

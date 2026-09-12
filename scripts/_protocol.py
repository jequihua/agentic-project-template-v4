"""Version-2 lifecycle contracts; legacy event meaning remains in ledger.py."""

from __future__ import annotations

import json
import re
from pathlib import Path

import _common as c

SCHEMA = "frutlups.ledger/2"
ROADMAP = "frutlups.roadmap/2"
RESULTS = {"implemented", "blocked_authority", "blocked_environment"}
EXTRA = {
    "prompt": {"envelope"},
    "coded": {"manifest", "result", "notes_sha", "outcome"},
    "accepted": {"commit_intent"},
    "milestone_done": {"commit_intent"},
}
FIELDS = {
    "resolved": {"scope", "reason", "authority"},
    "commit_cancelled": {"operation", "reason", "retain_acceptance"},
    "holistic_reviewed": {"milestone", "report", "sha", "verdict", "open"},
    "review_checkpoint": {"invocation", "scope", "round", "contract", "report", "sha", "seat"},
    "attempt_started": {
        "invocation",
        "scope",
        "round",
        "role",
        "contract",
        "allowance_seconds",
        "retry",
        "parent",
    },
    "attempt_finished": {"invocation", "status", "usage", "reason", "evidence"},
}
OPTIONAL = {"attempt_started": {"parent"}, "attempt_finished": {"reason", "evidence"}}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def identifier(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value))


def scope(value):
    return isinstance(value, str) and bool(re.fullmatch(r"M\d{3}(?:-S\d{2})?", value))


def reference(value):
    need(isinstance(value, dict) and set(value) == {"path", "sha"}, "invalid evidence reference")
    c.safe_rel(value["path"])
    need(digest(value["sha"]), "invalid evidence reference hash")
    return value


def references(values):
    need(isinstance(values, list), "evidence references must be a list")
    for value in values:
        reference(value)


def validate(event, legacy_validate):
    need(len(json.dumps(event).encode()) <= 2 * 1024 * 1024, "ledger event exceeds 2 MiB")
    ev = event.get("ev")
    need(isinstance(ev, str), "event name must be text")
    need(event.get("by") in ("human", "architect", "frutlups"), "invalid actor")
    need(isinstance(event.get("t"), str), "invalid timestamp")
    from datetime import datetime

    need(event["t"].endswith("Z"), "timestamp must be UTC")
    datetime.fromisoformat(event["t"].replace("Z", "+00:00"))
    if ev in FIELDS:
        keys = set(event) - {"schema", "t", "ev", "by"}
        required = FIELDS[ev] - OPTIONAL.get(ev, set())
        need(required <= keys <= FIELDS[ev], f"invalid {ev} fields")
    else:
        base = {key: value for key, value in event.items() if key not in EXTRA.get(ev, set())}
        base["schema"] = "frutlups.ledger/1"
        if ev == "artifact" and event.get("role") == "evidence":
            need(
                set(base) == {"schema", "t", "ev", "by", "scope", "round", "role", "path", "sha"},
                "invalid evidence artifact fields",
            )
            reference({"path": event["path"], "sha": event["sha"]})
            need(scope(event["scope"]), "invalid evidence scope")
            need(
                ("-S" in event["scope"] and type(event["round"]) is int and event["round"] > 0)
                or ("-S" not in event["scope"] and event["round"] == "holistic"),
                "evidence scope/round mismatch",
            )
        else:
            legacy_validate(base)
    for key in ("scope", "milestone"):
        if key in event:
            need(scope(event[key]), f"invalid {key}")
    for key in ("reason", "seat"):
        if key in event:
            need(isinstance(event[key], str) and bool(event[key].strip()), f"invalid {key}")
    for key in ("invocation", "operation", "parent"):
        if key in event:
            need(identifier(event[key]), f"invalid {key}")
    for key in ("contract", "sha", "notes_sha"):
        if key in event:
            need(digest(event[key]), f"invalid {key}")
    for key in ("envelope", "manifest", "outcome"):
        if key in event:
            reference(event[key])
    if ev == "prompt":
        need("envelope" in event, "/2 prompt requires a frozen envelope")
    if ev == "coded":
        need(
            "manifest" in event and event.get("result") in RESULTS, "/2 coded needs manifest/result"
        )
        need(("notes_path" in event) == ("notes_sha" in event), "notes require a hash")
        need(event["result"] == "implemented" or "outcome" in event, "blocker requires outcome")
    if "commit_intent" in event:
        intent = event["commit_intent"]
        need(
            isinstance(intent, dict) and set(intent) == {"id", "parent", "manifest", "message"},
            "invalid commit intent",
        )
        need(bool(re.fullmatch(r"[0-9a-f]{32}", str(intent["id"]))), "invalid commit operation id")
        need(
            bool(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", str(intent["parent"]))),
            "invalid parent",
        )
        need(
            isinstance(intent["message"], str) and bool(intent["message"].strip()),
            "invalid message",
        )
        reference(intent["manifest"])
    if ev == "resolved":
        need(event["by"] in ("human", "architect"), "resolution requires human or architect")
        references(event["authority"])
        need(bool(event["authority"]), "resolution needs a bound authority/environment reference")
    if ev == "commit_cancelled":
        need(event["by"] in ("human", "architect"), "cancellation requires human or architect")
        need(type(event["retain_acceptance"]) is bool, "retain_acceptance must be boolean")
        need(
            not event["retain_acceptance"] or event["by"] == "human",
            "only human retains acceptance",
        )
    if ev == "reopened":
        need(event["by"] in ("human", "architect"), "explicit reopen requires human or architect")
    if ev in ("holistic_reviewed", "review_checkpoint"):
        c.safe_rel(event["report"])
    if ev == "holistic_reviewed":
        need(event["verdict"] in ("pass", "needs_work", "blocked", "override"), "invalid verdict")
        need(event["verdict"] != "override" or event["by"] == "human", "override requires human")
        need(
            isinstance(event["open"], list) and all(identifier(x) for x in event["open"]),
            "invalid open findings",
        )
        need(
            event["verdict"] not in ("pass", "override") or not event["open"],
            "pass has open findings",
        )
    if ev in ("attempt_started", "review_checkpoint"):
        need(
            event["round"] == "holistic" or type(event["round"]) is int and event["round"] > 0,
            "invalid round",
        )
    if ev == "attempt_started":
        need(event["role"] in ("coder", "reviewer", "holistic", "probe"), "invalid attempt role")
        need(event["retry"] in ("initial", "transport", "format"), "invalid retry")
        need(
            type(event["allowance_seconds"]) is int and event["allowance_seconds"] > 0,
            "invalid allowance",
        )
        need((event["retry"] == "initial") == ("parent" not in event), "retry requires parent")
        if event["role"] != "probe":
            holistic = event["role"] == "holistic"
            need(
                holistic == (event["round"] == "holistic")
                and holistic == ("-S" not in event["scope"]),
                "attempt role/scope mismatch",
            )
    if ev == "attempt_finished":
        need(event["status"] in ("completed", "failed", "resolved"), "invalid attempt status")
        usage = event["usage"]
        need(
            isinstance(usage, dict)
            and set(usage) <= {"secs", "tokens_in", "tokens_out", "cost_usd", "completeness"},
            "invalid usage fields",
        )
        need(
            usage.get("completeness") in ("complete", "partial", "unknown"), "invalid completeness"
        )
        for key, value in usage.items():
            if key == "completeness":
                continue
            need(type(value) in (int, float) and 0 <= value < float("inf"), "invalid usage value")
            if key.startswith("tokens_"):
                need(type(value) is int, "tokens must be integer")
        if "evidence" in event:
            references(event["evidence"])
        if event["status"] == "resolved":
            need(
                event["by"] in ("human", "architect")
                and event.get("reason")
                and event.get("evidence"),
                "unknown attempt needs explicit human/architect attribution",
            )
    return event


def read_reference(root, ref, limit=2 * 1024 * 1024):
    reference(ref)
    path = c.repo_path(root, ref["path"])
    need(path.is_file() and not path.is_symlink(), f"missing regular evidence: {ref['path']}")
    need(c.sha(path) == ref["sha"], f"immutable evidence drift: {ref['path']}")
    need(path.stat().st_size <= limit, f"evidence exceeds read bound: {ref['path']}")
    return json.loads(path.read_text(encoding="utf-8"))


def outcome(root, ref, sid, round_no):
    value = read_reference(root, ref, 16 * 1024)
    fields = {
        "schema",
        "slice",
        "round",
        "invocation",
        "outcome",
        "requirement",
        "reason",
        "actor",
        "action",
        "remaining",
        "evidence",
        "authority",
    }
    need(isinstance(value, dict) and set(value) == fields, "invalid outcome fields")
    need(
        value["schema"] == "frutlups.outcome/2"
        and value["slice"] == sid
        and value["round"] == round_no,
        "outcome identity mismatch",
    )
    need(identifier(value["invocation"]) and value["outcome"] in RESULTS, "invalid outcome")
    for key in ("requirement", "reason", "actor", "action"):
        need(isinstance(value[key], str), f"invalid outcome {key}")
        if key in ("requirement", "reason") or value["outcome"] != "implemented":
            need(bool(value[key].strip()), f"outcome needs {key}")
    need(
        isinstance(value["remaining"], list)
        and all(isinstance(x, str) and x for x in value["remaining"]),
        "invalid remaining work",
    )
    references(value["evidence"])
    need(isinstance(value["authority"], list), "invalid authority list")
    for path in value["authority"]:
        c.safe_rel(path)
    for item in value["evidence"]:
        p = c.repo_path(root, item["path"])
        need(p.is_file() and c.sha(p) == item["sha"], "outcome retained evidence drift")
    return value


def manifest(root, ref):
    value = read_reference(root, ref)
    need(
        isinstance(value, dict) and set(value) == {"schema", "slice", "round", "changed"},
        "invalid manifest fields",
    )
    need(
        value["schema"] == "frutlups.manifest/2"
        and scope(value["slice"])
        and type(value["round"]) is int
        and value["round"] > 0,
        "invalid manifest identity",
    )
    need(isinstance(value["changed"], list), "invalid manifest changes")
    seen = set()
    for row in value["changed"]:
        need(
            isinstance(row, dict) and set(row) == {"path", "sha", "kind", "round"},
            "invalid manifest row",
        )
        c.safe_rel(row["path"])
        need(
            row["path"] not in seen
            and digest(row["sha"])
            and row["kind"] in ("added", "modified", "deleted", "renamed")
            and type(row["round"]) is int
            and 1 <= row["round"] <= value["round"],
            "invalid manifest row identity",
        )
        seen.add(row["path"])
    return value


def event_references(event):
    refs = [event[key] for key in ("envelope", "manifest", "outcome") if key in event]
    if event.get("notes_sha"):
        refs.append({"path": event["notes_path"], "sha": event["notes_sha"]})
    if event.get("commit_intent"):
        refs.append(event["commit_intent"]["manifest"])
    refs += event.get("authority", []) + event.get("evidence", [])
    return refs


def apply(event, states, milestones, done, extras):
    """Apply only new transitions; return whether the legacy fold should skip it."""
    ev = event["ev"]
    attempts = extras["attempts"]
    holistic = extras["holistic"]
    if ev == "attempt_started":
        need(event["invocation"] not in attempts, "duplicate invocation")
        need(not any(x.get("finish") is None for x in attempts.values()), "unresolved invocation")
        need(event["scope"] in states or event["scope"] in milestones, "unknown attempt scope")
        if event.get("parent"):
            prior = attempts.get(event["parent"])
            need(prior is not None and prior.get("finish") is not None, "unknown retry parent")
            need(
                all(event[key] == prior["start"][key] for key in ("scope", "round", "contract")),
                "retry binding mismatch",
            )
            need(
                event["retry"] != "transport" or event["role"] == prior["start"]["role"],
                "transport retry role mismatch",
            )
            if event["retry"] == "format":
                previous_role = prior["start"]["role"]
                expected_role = (
                    previous_role if previous_role in ("reviewer", "holistic") else "probe"
                )
                need(event["role"] == expected_role, "format repair role must remain read-only")
            need(
                not any(
                    x["start"].get("parent") == event["parent"]
                    and x["start"]["retry"] == event["retry"]
                    for x in attempts.values()
                ),
                "retry allowance already consumed",
            )
            need(
                event["retry"] != "format" or event["role"] != "coder",
                "format repair must be read-only",
            )
        attempts[event["invocation"]] = {"start": event, "finish": None}
        return True
    if ev == "attempt_finished":
        prior = attempts.get(event["invocation"])
        need(prior is not None and prior["finish"] is None, "attempt completion out of order")
        prior["finish"] = event
        return True
    if ev == "review_checkpoint":
        prior = attempts.get(event["invocation"])
        need(
            prior and prior["finish"] and prior["finish"]["status"] == "completed",
            "checkpoint needs a completed invocation",
        )
        need(prior["start"]["contract"] == event["contract"], "checkpoint contract mismatch")
        need(
            prior["start"]["role"] in ("reviewer", "holistic")
            and all(prior["start"][key] == event[key] for key in ("scope", "round")),
            "checkpoint scope, round or role mismatch",
        )
        need(event["invocation"] not in extras["checkpoints"], "duplicate checkpoint")
        extras["checkpoints"][event["invocation"]] = event
        return True
    if ev == "holistic_reviewed":
        mid = event["milestone"]
        need(mid in milestones, "unknown holistic milestone")
        need(
            mid not in done
            and all(states[x["id"]]["step"] == "accepted" for x in milestones[mid]["slices"]),
            "holistic review out of order",
        )
        need(
            holistic.get(mid, {}).get("step") not in ("blocked", "close_pending"),
            "holistic decision pending",
        )
        verdict = event["verdict"]
        step = {
            "pass": "close_pending",
            "override": "close_pending",
            "blocked": "blocked",
            "needs_work": "fix",
        }[verdict]
        holistic[mid] = {"step": step, "event": event}
        groups = {}
        for finding in event["open"]:
            sid = next(
                (x["id"] for x in milestones[mid]["slices"] if finding.startswith(x["id"] + "-")),
                None,
            )
            need(sid, "holistic finding must name its affected slice")
            groups.setdefault(sid, []).append(finding)
        if verdict == "needs_work":
            need(groups, "needs_work holistic review needs affected findings")
            for sid, ids in groups.items():
                current = states[sid]
                current.update(
                    step="fix",
                    round=current["round"] + 1,
                    reopened=True,
                    open=ids,
                    report=event["report"],
                    unblock_reason="Holistic findings: " + ", ".join(ids),
                )
        return True
    if ev == "resolved":
        sid = event["scope"]
        if sid in states:
            current = states[sid]
            need(current["step"] == "blocked", "resolution requires blocked work")
            current.update(
                step="fix",
                round=current["round"] + 1,
                resolution=event["reason"],
                unblock_reason=event["reason"],
            )
        else:
            need(sid in holistic and holistic[sid]["step"] == "blocked", "milestone is not blocked")
            holistic[sid]["step"] = "reviewing"
            holistic[sid]["resolution"] = event["reason"]
        return True
    if ev == "commit_cancelled":
        intent = extras["intents"].get(event["operation"])
        need(
            intent is not None and event["operation"] not in extras["cancelled"],
            "unknown/cancelled intent",
        )
        extras["cancelled"].add(event["operation"])
        if not event["retain_acceptance"]:
            sid = intent.get("slice", intent.get("milestone"))
            if sid in states:
                current = states[sid]
                current.update(
                    step="fix",
                    round=current["round"] + 1,
                    reopened=True,
                    unblock_reason="Commit cancelled: " + event["reason"],
                )
                done.discard(sid.split("-")[0])
                if sid.split("-")[0] in holistic:
                    holistic[sid.split("-")[0]].update(
                        step="reviewing", resolution="Commit cancelled: " + event["reason"]
                    )
            else:
                done.discard(sid)
                holistic[sid] = {"step": "reviewing", "resolution": event["reason"]}
        return True
    if ev == "artifact" and event.get("role") == "evidence":
        need(event["scope"] in states or event["scope"] in milestones, "unknown artifact scope")
        return True
    if event.get("commit_intent"):
        identity = event["commit_intent"]["id"]
        need(identity not in extras["intents"], "duplicate commit operation")
        extras["intents"][identity] = event
    return False


def ensure_writable(root, rm=None, *, allow_attempt=False, cancellation=False):
    import ledger
    import roadmap

    rm = rm or roadmap.load(root)
    events = ledger.read(Path(root) / "05_governance/ledger.jsonl")
    state = ledger.fold(events, rm)
    if not cancellation and any(event.get("commit_intent") for event in events):
        import _commit

        pending = [x for x in _commit.status(root, events, rm) if x["state"] == "pending"]
        need(not pending, "commit pending; use ledger.py recover or cancel")
    if not allow_attempt:
        need(
            not any(x.get("finish") is None for x in state.get("attempts", {}).values()),
            "unresolved invocation; record completion or explicit attribution before new work",
        )

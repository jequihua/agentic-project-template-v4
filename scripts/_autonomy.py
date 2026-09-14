"""Optional durable run grants; external dispatch and deadline enforcement stay runner-owned."""

from __future__ import annotations

import math
import os

SCHEMA = "frutlups.autonomy/1"
EVENTS = {"run_admitted", "run_extended"}
UNITS = ("jobs", "transport_retries", "format_retries", "seconds")
FIELDS = {
    "run_admitted": {
        "run",
        "milestone",
        "slices",
        "stop",
        "allowance",
        "max_corrective_rounds",
        "grantors",
        "previous",
        "reason",
        "authority",
    },
    "run_extended": {"run", "milestone", "revision", "allowance", "reason", "authority"},
}


def validate(event):
    import _protocol as p

    ev = event["ev"]
    p.need(set(event) - {"schema", "t", "ev", "by"} == FIELDS[ev], f"invalid {ev} fields")
    p.need(event["by"] in ("human", "architect"), "run grant requires human or architect")
    p.need(p.identifier(event["run"]), "invalid run identity")
    p.need(p.scope(event["milestone"]) and "-S" not in event["milestone"], "invalid run milestone")
    p.need(isinstance(event["reason"], str) and bool(event["reason"].strip()), "run needs reason")
    p.references(event["authority"])
    p.need(bool(event["authority"]), "run needs bound authority")
    p.need(
        len({(ref["path"], ref["sha"]) for ref in event["authority"]}) == len(event["authority"]),
        "duplicate run authority reference",
    )
    allowance = event["allowance"]
    p.need(isinstance(allowance, dict) and set(allowance) == set(UNITS), "invalid run allowance")
    p.need(all(type(x) is int and x >= 0 for x in allowance.values()), "invalid allowance units")
    if ev == "run_extended":
        p.need(type(event["revision"]) is int and event["revision"] > 0, "invalid run revision")
        p.need(any(allowance.values()), "extension needs positive allowance")
        return event
    p.need(allowance["jobs"] > 0 and allowance["seconds"] > 0, "admission needs jobs and seconds")
    selected = event["slices"]
    p.need(
        isinstance(selected, list)
        and bool(selected)
        and all(p.scope(x) and "-S" in x for x in selected)
        and len(set(selected)) == len(selected),
        "invalid run slices",
    )
    p.need(p.scope(event["stop"]), "invalid run stop")
    p.need(
        type(event["max_corrective_rounds"]) is int and event["max_corrective_rounds"] >= 0,
        "invalid corrective ceiling",
    )
    grantors = event["grantors"]
    p.need(
        isinstance(grantors, list)
        and all(x in ("human", "architect") for x in grantors)
        and "human" in grantors
        and len(set(grantors)) == len(grantors),
        "grantors must contain human and optionally architect",
    )
    previous = event["previous"]
    p.need(
        previous is None
        or isinstance(previous, dict)
        and set(previous) == {"run", "revision"}
        and p.identifier(previous["run"])
        and type(previous["revision"]) is int
        and previous["revision"] >= 0,
        "invalid previous run head",
    )
    return event


def _remaining(run):
    run["remaining"] = {key: run["allowance"][key] - run["consumed"][key] for key in UNITS}


def _grant(event, rm, states, done, extras):
    import _protocol as p

    runs, head = extras["runs"], extras["run_head"]
    authority = frozenset((ref["path"], ref["sha"]) for ref in event["authority"])
    grants = extras.setdefault("run_authorities", set())
    p.need(authority not in grants, "run authority already granted")
    p.need(
        not any(x.get("finish") is None for x in extras["attempts"].values()),
        "unresolved invocation prevents run grant",
    )
    if event["ev"] == "run_admitted":
        p.need(event["run"] not in runs, "duplicate run identity")
        p.need(event["previous"] == head, "previous run head mismatch")
        milestone = next((x for x in rm["milestones"] if x["id"] == event["milestone"]), None)
        p.need(milestone is not None, "unknown run milestone")
        p.need(milestone["status"] != "planned", "run admission requires active milestone")
        selected = event["slices"]
        p.need(
            [x["id"] for x in milestone["slices"] if x["id"] in selected] == selected,
            "run slices must belong to milestone in roadmap order",
        )
        stop = event["stop"]
        p.need(stop in (selected[-1], milestone["id"]), "run stop must be final slice or milestone")
        if stop == milestone["id"]:
            p.need(milestone["holistic_review"] and stop not in done, "invalid or reached run stop")
        else:
            p.need(states[stop]["step"] != "accepted", "run stop already reached")
        if head and runs[head["run"]]["closed"] is None:
            runs[head["run"]]["closed"] = "superseded"
        run = {
            "admission": event,
            "revision": 0,
            "allowance": dict(event["allowance"]),
            "consumed": dict.fromkeys(UNITS, 0),
            "closed": None,
            "initial_contexts": set(),
            "roots": {},
            "chain_retries": {},
        }
        runs[event["run"]] = run
    else:
        p.need(head is not None and head["run"] == event["run"], "extension needs current run")
        run = runs[head["run"]]
        p.need(run["closed"] is None, "cannot extend closed run")
        p.need(event["milestone"] == run["admission"]["milestone"], "extension milestone mismatch")
        p.need(event["revision"] == run["revision"] + 1, "extension revision mismatch")
        p.need(event["by"] in run["admission"]["grantors"], "extension actor is not delegated")
        run["revision"] = event["revision"]
        for key in UNITS:
            run["allowance"][key] += event["allowance"][key]
    grants.add(authority)
    extras["run_head"] = {"run": event["run"], "revision": run["revision"]}
    _remaining(run)


def _start(event, rm, states, extras):
    import _protocol as p

    head = extras["run_head"]
    p.need(
        head is not None,
        "profile attempts require preceding admission; historical cutover unsupported",
    )
    run = extras["runs"][head["run"]]
    admission = run["admission"]
    p.need(run["closed"] is None, "run is closed")
    p.need(
        event["scope"] in admission["slices"] or event["scope"] == admission["milestone"],
        "attempt outside admitted selection",
    )
    p.need(
        event["role"] != "holistic" or admission["stop"] == admission["milestone"],
        "holistic attempt exceeds slice stop",
    )
    current = states.get(event["scope"])
    p.need(current is None or current["step"] != "blocked", "slice blocker needs resolution")
    p.need(
        extras["holistic"].get(admission["milestone"], {}).get("step") != "blocked",
        "holistic blocker needs resolution",
    )
    if event["role"] == "verification":
        p.need(
            current is not None
            and current["step"] == "verifying"
            and current["round"] == event["round"]
            and event["retry"] == "initial"
            and "parent" not in event,
            "verification requires current verifying round and no retry",
        )
    if event["role"] == "reviewer":
        p.need(
            current is not None
            and current["step"] == "reviewing"
            and current["round"] == event["round"],
            "reviewer requires current reviewing round",
        )
    if event["role"] == "holistic":
        milestone = next(x for x in rm["milestones"] if x["id"] == admission["milestone"])
        p.need(
            event["scope"] == milestone["id"]
            and event["round"] == "holistic"
            and milestone["holistic_review"]
            and all(states[x["id"]]["step"] == "accepted" for x in milestone["slices"])
            and extras["holistic"].get(milestone["id"], {}).get("step")
            not in ("blocked", "close_pending", "done"),
            "holistic requires accepted milestone and no pending decision",
        )
    if event["role"] == "coder":
        p.need(
            current is not None
            and current["step"] == "coding"
            and current["round"] == event["round"],
            "coder requires current issued coding round",
        )
        p.need(
            current is not None
            and current["corrective_rounds_used"] <= admission["max_corrective_rounds"],
            "pinned corrective ceiling exhausted",
        )
    invocation = event["invocation"]
    parent = event.get("parent")
    if parent:
        p.need(
            extras["run_membership"].get(parent) == head["run"],
            "retry parent belongs to another run",
        )
        root = run["roots"][parent]
        p.need(
            extras["attempts"][root]["start"]["role"] != "verification",
            "verification cannot be retried",
        )
        p.need(event["retry"] not in run["chain_retries"][root], "chain retry allowance consumed")
    else:
        root = invocation
        context = tuple(event[key] for key in ("scope", "round", "role", "contract"))
        p.need(
            event["role"] == "verification" or context not in run["initial_contexts"],
            "initial model context already attempted",
        )
    charges = {
        "jobs": int(event["role"] != "verification"),
        "transport_retries": int(event["retry"] == "transport"),
        "format_retries": int(event["retry"] == "format"),
        "seconds": event["allowance_seconds"],
    }
    for key in UNITS:
        p.need(charges[key] <= run["remaining"][key], f"run {key} allowance exhausted")
    if parent:
        run["chain_retries"][root].add(event["retry"])
    else:
        run["initial_contexts"].add(context)
        run["chain_retries"][root] = set()
    run["roots"][invocation] = root
    extras["run_membership"][invocation] = head["run"]
    for key in UNITS:
        run["consumed"][key] += charges[key]
    _remaining(run)


def apply(event, rm, states, done, extras):
    """Fold profile effects before ordinary attempt/lifecycle state changes."""
    import _protocol as p

    ev = event["ev"]
    enabled = rm.get("autonomy") == {"schema": SCHEMA}
    p.need(
        enabled
        or ev not in EVENTS
        and not (ev == "attempt_started" and event.get("role") == "verification"),
        "autonomy history requires declared frutlups.autonomy/1 profile",
    )
    if not enabled:
        return False
    extras.setdefault("runs", {})
    extras.setdefault("run_head", None)
    extras.setdefault("run_membership", {})
    if ev in EVENTS:
        p.need(event.get("schema") == p.SCHEMA, "run grants require /2 ledger")
        _grant(event, rm, states, done, extras)
        return True
    if ev == "attempt_started":
        _start(event, rm, states, extras)
    elif ev == "attempt_finished":
        owner = extras["run_membership"].get(event["invocation"])
        p.need(owner is not None, "completion has no admitted run")
        run = extras["runs"][owner]
        reservation = extras["attempts"][event["invocation"]]["start"]["allowance_seconds"]
        secs = event["usage"].get("secs")
        measured = math.ceil(secs) if secs is not None else reservation
        charge = measured if event["status"] == "completed" else max(reservation, measured)
        run["consumed"]["seconds"] += charge - reservation
        if measured > reservation:
            run["closed"] = "overrun"
        _remaining(run)
    elif extras["run_head"]:
        run = extras["runs"][extras["run_head"]["run"]]
        stop = run["admission"]["stop"]
        if run["closed"] is None and (
            ev == "accepted"
            and event["slice"] == stop
            or ev == "milestone_done"
            and event["milestone"] == stop
        ):
            run["closed"] = "boundary"
    return False


def validate_history(rm, states, done, extras):
    """A done roadmap label may replay completed history, never grant new work."""
    import _protocol as p

    runs = extras.get("runs", {})
    admitted = {x["admission"]["milestone"] for x in runs.values()}
    unsettled = {
        runs[owner]["admission"]["milestone"]
        for invocation, owner in extras.get("run_membership", {}).items()
        if extras["attempts"][invocation]["finish"] is None
    }
    for milestone in rm["milestones"]:
        mid = milestone["id"]
        if mid in admitted and milestone["status"] != "active":
            p.need(
                milestone["status"] == "done"
                and mid not in unsettled
                and all(states[x["id"]]["step"] == "accepted" for x in milestone["slices"])
                and (not milestone["holistic_review"] or mid in done),
                "inactive run history requires completed milestone and settled attempts",
            )


def configure_parser(subparsers):
    commands = subparsers.add_parser("run").add_subparsers(dest="run_command", required=True)
    for name in ("admit", "extend"):
        item = commands.add_parser(name)
        item.add_argument("milestone" if name == "admit" else "run")
        if name == "admit":
            item.add_argument("--run-id", required=True)
            item.add_argument("--slice", dest="slices", action="append", required=True)
            item.add_argument("--stop", required=True)
            item.add_argument("--max-corrective-rounds", type=int, default=0)
            item.add_argument(
                "--grantor", dest="grantors", choices=("human", "architect"), action="append"
            )
        else:
            item.add_argument("--revision", type=int, required=True)
        for key in UNITS:
            required = name == "admit" and key in ("jobs", "seconds")
            item.add_argument("--" + key.replace("_", "-"), type=int, required=required, default=0)
        item.add_argument("--reason", required=True)
        item.add_argument("--authority", action="append", required=True)
        item.add_argument("--by", choices=("human", "architect"), default="human")


def execute(root, args, rm, events, state):
    import _protocol as p
    import ledger

    p.need("FRUTLUPS_SEAT" not in os.environ, "autonomous seats cannot grant run allowance")
    p.need(
        rm.get("autonomy") == {"schema": SCHEMA}, "run commands require declared autonomy profile"
    )
    ledger.require_artifacts(root, events)
    event = {
        "ev": "run_admitted" if args.run_command == "admit" else "run_extended",
        "by": args.by,
        "reason": args.reason,
        "authority": [ledger._ref(root, path) for path in args.authority],
        "allowance": {key: getattr(args, key) for key in UNITS},
    }
    if args.run_command == "admit":
        event.update(
            run=args.run_id,
            milestone=args.milestone,
            slices=args.slices,
            stop=args.stop,
            max_corrective_rounds=args.max_corrective_rounds,
            grantors=args.grantors or ["human"],
            previous=state.get("run_head"),
        )
    else:
        head = state.get("run_head")
        p.need(head is not None and head["run"] == args.run, "extension needs current run")
        event.update(
            run=args.run,
            revision=args.revision,
            milestone=state["runs"][args.run]["admission"]["milestone"],
        )
    ledger.append(root / "05_governance/ledger.jsonl", event, rm)
    print(f"{event['ev']} {event['run']}")


def status(state):
    lines = []
    for name, run in state.get("runs", {}).items():
        balances = " ".join(f"{key}={run['remaining'][key]}" for key in UNITS)
        lines.append(
            f"run {name} revision={run['revision']} stop={run['admission']['stop']} "
            f"state={run['closed'] or 'open'} remaining {balances}"
        )
    return lines

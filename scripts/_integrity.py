"""Strict evidence relationships and current-product admission for protocol 2."""

from __future__ import annotations

import math
import re

import _common as c
import _evidence
import _findings
import _protocol as p
import _workspace

OBSERVATIONS = {"process", "in_process", "fresh_process", "clean_checkout", "inspection"}
ENVELOPE_FIELDS = {
    "schema",
    "slice",
    "round",
    "title",
    "objective",
    "acceptance",
    "non_goals",
    "read_first",
    "allowed_prefixes",
    "forbidden",
    "focused",
    "full",
    "runtime",
    "timeout_seconds",
    "observation",
    "notes",
    "findings",
    "memory",
}


def _strings(value, label, required=False):
    p.need(
        isinstance(value, list)
        and (not required or bool(value))
        and all(
            isinstance(item, str) and bool(item.strip()) and "\0" not in item for item in value
        ),
        "invalid " + label,
    )


def envelope(root, ref, sid, round_no):
    value = p.read_reference(root, ref, 128 * 1024)
    p.need(isinstance(value, dict) and set(value) == ENVELOPE_FIELDS, "invalid envelope fields")
    p.need(
        value["schema"] == "frutlups.envelope/2"
        and value["slice"] == sid
        and value["round"] == round_no,
        "envelope identity mismatch",
    )
    for key in ("title", "objective", "notes", "findings", "memory"):
        p.need(isinstance(value[key], str), "invalid envelope " + key)
    p.need(value["title"].strip() and value["objective"].strip(), "empty envelope objective/title")
    for key in ("acceptance", "non_goals", "read_first", "allowed_prefixes", "forbidden", "full"):
        _strings(value[key], "envelope " + key, key in ("acceptance", "full"))
    for key in ("read_first", "allowed_prefixes", "forbidden"):
        for rel in value[key]:
            c.safe_rel(rel, directory=key != "read_first" and rel.endswith("/"))
    p.need(isinstance(value["focused"], list), "invalid envelope focused commands")
    for argv in value["focused"]:
        _strings(argv, "focused argv", True)
    runtime = value["runtime"]
    p.need(isinstance(runtime, dict) and set(runtime) <= {"python"}, "invalid envelope runtime")
    if runtime:
        p.need(
            isinstance(runtime["python"], str)
            and re.fullmatch(r"3\.\d+(?:\.\d+)?", runtime["python"]),
            "invalid envelope Python version",
        )
    p.need(
        type(value["timeout_seconds"]) is int and value["timeout_seconds"] > 0,
        "invalid envelope timeout",
    )
    p.need(value["observation"] in OBSERVATIONS, "invalid envelope observation")
    return value


def _reference(root, ref):
    p.reference(ref)
    path = c.repo_path(root, ref["path"])
    message = "immutable evidence drift: " + ref["path"]
    p.need(path.is_file() and not path.is_symlink(), message)
    identity = c.file_key(path)
    p.need(c.sha(path) == ref["sha"] and c.file_key(path) == identity, message)


def _receipt(root, event, coded, issued):
    import verify

    value = p.read_reference(root, {"path": event["receipt"], "sha": event["sha"]}, 128 * 1024)
    fields = {
        "schema",
        "slice",
        "round",
        "t",
        "base_commit",
        "tree_dirty_before",
        "commands",
        "tree_clean_after",
        "ok",
        "manifest",
        "witness",
        "runtime",
        "observation",
    }
    p.need(isinstance(value, dict) and set(value) == fields, "invalid receipt fields")
    p.need(
        value["schema"] == "frutlups.receipt/2"
        and value["slice"] == event["slice"]
        and value["round"] == event["round"],
        "receipt identity mismatch",
    )
    p.need(value["manifest"] == coded["manifest"], "receipt manifest does not match coded evidence")
    p.need(
        value["t"] == event["t"]
        or isinstance(value["t"], str)
        and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value["t"]),
        "invalid receipt timestamp",
    )
    p.need(
        isinstance(value["base_commit"], str)
        and re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", value["base_commit"]),
        "invalid receipt HEAD",
    )
    for key in ("tree_dirty_before", "tree_clean_after", "ok"):
        p.need(type(value[key]) is bool, "invalid receipt " + key)
    witness = value["witness"]
    p.need(
        isinstance(witness, dict)
        and set(witness) == {"before", "after", "stable", "head", "index", "product"},
        "invalid receipt witness",
    )
    for key in ("before", "after", "index", "product"):
        p.need(p.digest(witness[key]), "invalid receipt witness " + key)
    p.need(witness["head"] == value["base_commit"], "receipt witness HEAD mismatch")
    p.need(
        type(witness["stable"]) is bool
        and witness["stable"] == (witness["before"] == witness["after"]),
        "receipt stability contradiction",
    )
    commands = value["commands"]
    p.need(isinstance(commands, list) and len(commands) == 1, "receipt needs one full command")
    command = commands[0]
    p.need(
        isinstance(command, dict)
        and set(command)
        == {"label", "argv", "exit", "secs", "stdout_tail", "stderr_tail", "timed_out"},
        "invalid receipt command fields",
    )
    p.need(
        command["label"] == "full" and command["argv"] == verify._public_argv(issued["full"], root),
        "receipt command differs from frozen verification",
    )
    p.need(command["exit"] is None or type(command["exit"]) is int, "invalid receipt exit")
    p.need(type(command["timed_out"]) is bool, "invalid receipt timeout flag")
    p.need(
        type(command["secs"]) in (int, float)
        and math.isfinite(command["secs"])
        and command["secs"] >= 0,
        "invalid receipt duration",
    )
    for key in ("stdout_tail", "stderr_tail"):
        p.need(
            isinstance(command[key], str) and len(command[key].encode("utf-8")) <= 4096,
            "invalid receipt diagnostic tail",
        )
    expected = command["exit"] == 0 and not command["timed_out"] and witness["stable"]
    p.need(value["ok"] == expected == event["ok"], "receipt ok contradicts command or witness")
    p.need(
        value["observation"] == issued["observation"], "receipt observation differs from envelope"
    )
    runtime = value["runtime"]
    p.need(
        isinstance(runtime, dict) and set(runtime) == {"python", "implementation", "source", "sha"},
        "invalid receipt runtime fields",
    )
    p.need(
        isinstance(runtime["python"], str)
        and re.fullmatch(r"3\.\d+\.\d+[A-Za-z0-9.+-]*", runtime["python"])
        and isinstance(runtime["implementation"], str)
        and re.fullmatch(r"[A-Za-z0-9_. -]{1,80}", runtime["implementation"]),
        "invalid portable runtime",
    )
    p.need(
        runtime["source"] in ("invoking_python", "project.local"),
        "invalid runtime selection source",
    )
    expected_runtime = issued["runtime"].get("python")
    p.need(
        not expected_runtime
        or runtime["python"] == expected_runtime
        or runtime["python"].startswith(expected_runtime + "."),
        "receipt runtime version mismatch",
    )
    identity = {key: item for key, item in runtime.items() if key != "sha"}
    p.need(
        runtime["sha"]
        == _workspace.snapshot_digest({"runtime": identity, "declaration": issued["runtime"]}),
        "receipt runtime identity hash mismatch",
    )
    return value


def _review(root, event, rm, projection):
    ref = {"path": event["report"], "sha": event["sha"]}
    _, report = _findings.read_report(root, ref)
    scope = event.get("slice", event.get("milestone", event.get("scope")))
    round_no = event.get("round", "holistic")
    if round_no == "holistic":
        round_no = None
    p.need(
        report["identity"] == scope and report["round"] == round_no,
        "recorded review identity mismatch",
    )
    if round_no is None:
        milestone = next((item for item in rm["milestones"] if item["id"] == scope), None)
        p.need(milestone is not None, "unknown holistic review milestone")
        prefixes = tuple(item["id"] + "-" for item in milestone["slices"])
        p.need(
            all(
                row["severity"] == "P3" or row["id"].startswith(prefixes)
                for row in report["findings"]
            ),
            "holistic finding must identify its affected slice",
        )
    if event["ev"] != "review_checkpoint":
        p.need(
            report["verdict"] == event["verdict"] and report["open"] == event["open"],
            "recorded review verdict/open findings mismatch",
        )
    projection.add((ref["path"], ref["sha"]), event)
    if event["ev"] != "review_checkpoint":
        projection.require_closure(report)


def errors(root, events, rm):
    """Check immutable artifact semantics without comparing historical files to today."""
    failures, issued, coded, cumulative = [], {}, {}, {}
    projection = _findings.Projection(root)
    for event in events:
        sid = event.get("slice")
        key = (sid, event.get("round"))
        if event.get("ev") == "coded":
            cumulative.setdefault(sid, {}).update(
                {row["path"]: {**row, "round": event["round"]} for row in event["changed"]}
            )
        try:
            if event.get("schema") != p.SCHEMA:
                for ref, previous in _findings.report_events([event]):
                    projection.add(ref, previous)
                continue
            for ref in p.event_references(event):
                _reference(root, ref)
            if event["ev"] == "prompt":
                issued[key] = envelope(root, event["envelope"], sid, event["round"])
            elif event["ev"] == "coded":
                manifest = p.manifest(root, event["manifest"])
                p.need(
                    manifest["slice"] == sid and manifest["round"] == event["round"],
                    "coded manifest identity mismatch",
                )
                p.need(
                    manifest["changed"]
                    == [cumulative[sid][rel] for rel in sorted(cumulative[sid])],
                    "coded manifest is not the cumulative recorded change set",
                )
                p.need(key in issued, "coded evidence lacks its issued envelope")
                p.need(
                    not _evidence.fence(
                        event["changed"], issued[key]["allowed_prefixes"], issued[key]["forbidden"]
                    ),
                    "coded changes exceed frozen envelope",
                )
                if event.get("outcome"):
                    outcome = p.outcome(root, event["outcome"], sid, event["round"])
                    p.need(outcome["outcome"] == event["result"], "coded outcome mismatch")
                    for ref in outcome["evidence"]:
                        _reference(root, ref)
                coded[key] = event
            elif event["ev"] == "verified":
                p.need(key in issued and key in coded, "receipt lacks issued/coded evidence")
                _receipt(root, event, coded[key], issued[key])
            elif event["ev"] in ("reviewed", "holistic_reviewed", "review_checkpoint"):
                _review(root, event, rm, projection)
            elif event["ev"] == "artifact" and event.get("role") == "holistic_report":
                projection.add((event["path"], event["sha"]), event)
        except (KeyError, TypeError, OSError, ValueError) as exc:
            failures.append(f"{event['ev']} {sid or event.get('scope', '')}: {exc}")
    return failures


def evidence_paths(root, events):
    paths = {
        "05_governance/ledger.jsonl",
        "05_governance/backlog.md",
        "roadmap.yaml",
        "docs/roadmap.md",
    }
    for event in events:
        paths.update(
            event[key] for key in ("path", "receipt", "report", "notes_path") if event.get(key)
        )
        paths.update(ref["path"] for ref in p.event_references(event))
        if event.get("outcome"):
            outcome = p.outcome(root, event["outcome"], event["slice"], event["round"])
            paths.update(ref["path"] for ref in outcome["evidence"])
    return paths


def product_digest(root, snapshot, events, extra=()):
    ignored = evidence_paths(root, events) | set(extra)
    product_paths = {
        row["path"] for event in events if event["ev"] == "coded" for row in event["changed"]
    }
    ignored -= product_paths
    return _workspace.snapshot_digest(
        {rel: value for rel, value in snapshot["files"].items() if rel not in ignored}
    )


def require_active(root, current, events, extra=()):
    """Refuse unrecorded product edits and drift after active verification.

    Extra paths name only the report/evidence the caller is about to record.
    Historical accepted scopes do not pin today's HEAD/index to their old receipt.
    """
    if not current.get("manifest"):
        return
    manifest = p.manifest(root, current["manifest"])
    rows = {row["path"]: row for row in manifest["changed"]}
    if current["step"] == "accepted":
        # A later accepted scope may legitimately own the newest file identity;
        # ledger-only acceptance can leave every slice's product files dirty.
        rows = {
            row["path"]: row
            for event in events
            if event["ev"] == "coded"
            for row in event["changed"]
        }
    excluded = evidence_paths(root, events) | set(extra)
    baseline = {
        row["path"]: row for row in current.get("baseline", []) if row["path"] not in excluded
    }
    for rel, row in {**baseline, **rows}.items():
        path = c.repo_path(root, rel)
        matches = (
            row["kind"] == "deleted"
            and not path.exists()
            and not path.is_symlink()
            or row["kind"] != "deleted"
            and path.is_file()
            and not path.is_symlink()
            and c.sha(path) == row["sha"]
        )
        if not matches and current["step"] == "accepted":
            matches = _evidence.matches_head(root, rel)
        p.need(matches, "active product differs from recorded evidence: " + rel)
    dirty = _evidence.changed_files(root)
    unexpected = sorted({row["path"] for row in dirty} - set(rows) - set(baseline) - excluded)
    p.need(not unexpected, "unrecorded product changes: " + ", ".join(unexpected[:8]))
    if current["step"] not in ("reviewing", "accept_pending") or not current.get("receipt"):
        return
    recorded = next(
        (event for event in reversed(events) if event.get("receipt") == current["receipt"]), None
    )
    p.need(recorded is not None, "active receipt is not recorded")
    value = p.read_reference(
        root, {"path": recorded["receipt"], "sha": recorded["sha"]}, 128 * 1024
    )
    witness = value["witness"]
    present = _workspace.snapshot(root)
    p.need(witness["head"] == present["head"], "HEAD changed after verification")
    p.need(witness["index"] == present["index"], "index changed after verification")
    p.need(
        witness["product"] == product_digest(root, present, events, extra),
        "raw product content or mode changed after verification",
    )

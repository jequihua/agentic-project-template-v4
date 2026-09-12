"""Explicit report-bound finding updates and a disposable backlog projection."""

from __future__ import annotations

import re

import _common as c
import _evidence as evidence
import _protocol as protocol

BEGIN = "<!-- findings:begin -->"
END = "<!-- findings:end -->"
DISPOSITIONS = {"open", "closed_by_review", "carried", "waived_by_human"}


def updates(text):
    lines = evidence._visible_lines(text)
    heads = [i for i, line in enumerate(lines) if line.strip() == "## Finding updates"]
    if not heads:
        return []
    protocol.need(len(heads) == 1, "duplicate Finding updates heading")
    closure = next((i for i, line in enumerate(lines) if line.strip() == "## Closure Decision"), -1)
    protocol.need(heads[0] < closure, "Finding updates must precede Closure Decision")
    start = heads[0] + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    rows = [line for line in lines[start:end] if line.strip().startswith("|")]
    split = lambda line: [x.strip() for x in line.strip().strip("|").split("|")]
    protocol.need(
        len(rows) >= 2 and split(rows[0]) == ["source", "sha", "id", "disposition", "related"],
        "invalid Finding updates table",
    )
    out = []
    seen = set()
    for row in rows[2:]:
        cells = split(row)
        protocol.need(len(cells) == 5, "invalid finding update row")
        source, sha, identity, disposition, related = cells
        c.safe_rel(source)
        protocol.need(
            protocol.digest(sha) and identity and disposition in DISPOSITIONS,
            "invalid finding update identity/disposition",
        )
        key = (source, sha, identity)
        protocol.need(key not in seen, "contradictory or duplicate finding update")
        seen.add(key)
        out.append(
            {
                "source": source,
                "sha": sha,
                "id": identity,
                "disposition": disposition,
                "related": []
                if related == "-"
                else [x.strip() for x in related.split(",") if x.strip()],
            }
        )
    return out


def report_events(events):
    seen = set()
    for event in events:
        if event["ev"] in ("reviewed", "holistic_reviewed", "review_checkpoint"):
            ref = (event["report"], event["sha"])
        elif event["ev"] == "artifact" and event.get("role") == "holistic_report":
            ref = (event["path"], event["sha"])
        else:
            continue
        if ref not in seen:
            seen.add(ref)
            yield ref, event


def project(root, events, extra=None):
    records = list(report_events(events))
    if extra:
        records.append(extra)
    findings = {}
    ids = {}
    diagnostics = []
    for (path, sha), event in records:
        ref = {"path": path, "sha": sha}
        p = c.repo_path(root, path)
        protocol.need(
            p.is_file() and not p.is_symlink() and c.sha(p) == sha, f"finding source drift: {path}"
        )
        protocol.need(p.stat().st_size <= 1024 * 1024, "review exceeds 1 MiB")
        text = p.read_text(encoding="utf-8")
        report = evidence.parse_review(text)
        changes = updates(text)
        waived = any(x["disposition"] == "waived_by_human" for x in report["findings"] + changes)
        protocol.need(not waived or event["by"] == "human", "waiver requires --by human")
        # A checkpoint preserves seat evidence. Only the recorded merged decision projects it.
        if event["ev"] == "review_checkpoint":
            continue
        for item in report["findings"]:
            if event.get("schema") == protocol.SCHEMA:
                protocol.need(
                    item["severity"] == "P3" or item["disposition"] != "carried",
                    "only P3 findings may be carried",
                )
            key = (path, sha, item["id"])
            prior = ids.get(item["id"])
            if prior and prior != key:
                protocol.need(
                    event.get("schema") != protocol.SCHEMA,
                    f"finding ID collision: {item['id']}; use source-bound update",
                )
                diagnostics.append(f"Legacy duplicate id {item['id']} at {path}")
            ids[item["id"]] = key
            findings[key] = {
                **item,
                "source": ref,
                "related": [],
                "last_report": path,
                "owner": report["identity"],
            }
        for change in changes:
            key = (change["source"], change["sha"], change["id"])
            protocol.need(key in findings, f"unresolved finding reference: {change['id']}")
            protocol.need(
                findings[key]["severity"] == "P3" or change["disposition"] != "carried",
                "only P3 findings may be carried",
            )
            for linked in change["related"]:
                protocol.need(linked in ids, f"unknown related finding: {linked}")
            findings[key].update(
                disposition=change["disposition"], related=change["related"], last_report=path
            )
        count = re.search(r"^Finding count: (\d+)\s*$", text, re.M)
        if count and int(count[1]) != len(report["findings"]):
            diagnostics.append(f"Finding count differs from parsed IDs in {path}")
    return findings, diagnostics


def validate_record(root, events, path, sha, by, current=None):
    event = {"ev": "reviewed", "schema": protocol.SCHEMA, "by": by}
    findings, diagnostics = project(root, events, ((path, sha), event))
    report = evidence.parse_review((root / path).read_text(encoding="utf-8"))
    unresolved = [
        x["id"]
        for x in findings.values()
        if x["severity"] in ("P0", "P1", "P2")
        and x["disposition"] == "open"
        and (
            x["owner"] == report["identity"]
            or x["owner"].startswith(report["identity"] + "-")
            or x["id"].startswith(report["identity"] + "-")
            or x["id"] in (current or {}).get("open", [])
        )
    ]
    if report["verdict"] in ("pass", "override"):
        protocol.need(
            not unresolved,
            "prior findings need explicit source-bound closure: " + ", ".join(unresolved),
        )
    return diagnostics


def reconcile(root, events):
    findings, diagnostics = project(root, events)
    path = root / "05_governance/backlog.md"
    old = path.read_text(encoding="utf-8")
    protocol.need(
        old.count(BEGIN) == old.count(END) and old.count(BEGIN) <= 1,
        "backlog generated markers are malformed",
    )
    rows = [
        BEGIN,
        "| ID | Severity | Disposition | Source | Summary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key in sorted(findings):
        item = findings[key]
        summary = item["summary"].replace("|", r"\|")
        rows.append(
            f"| {item['id']} | {item['severity']} | {item['disposition']} | "
            f"{item['source']['path']} ({item['source']['sha']}) | {summary} |"
        )
    rows += [END]
    generated = "\n".join(rows)
    if BEGIN in old:
        start, end = old.index(BEGIN), old.index(END) + len(END)
        protocol.need(start < end, "backlog generated markers out of order")
        text = old[:start] + generated + old[end:]
    else:
        text = old.rstrip() + "\n\n" + generated + "\n"
    if text != old:
        c.atomic_text(path, text)
    return diagnostics

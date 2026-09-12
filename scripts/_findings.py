"""Explicit report-bound finding updates and a disposable backlog projection."""

from __future__ import annotations

import re
from copy import deepcopy

import _common as c
import _evidence as evidence
import _protocol as protocol

BEGIN = "<!-- findings:begin -->"
END = "<!-- findings:end -->"
DISPOSITIONS = {"open", "closed_by_review", "carried", "waived_by_human"}


def _cells(line):
    row = re.sub(r"^\||(?<!\\)\|$", "", line.strip())
    return [item.strip().replace(r"\|", "|") for item in re.split(r"(?<!\\)\|", row)]


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
    protocol.need(
        len(rows) >= 2
        and _cells(rows[0]) == ["source", "sha", "id", "disposition", "related"]
        and len(_cells(rows[1])) == 5
        and all(re.fullmatch(r":?-{3,}:?", cell) for cell in _cells(rows[1])),
        "invalid Finding updates table",
    )
    out = []
    seen = set()
    for row in rows[2:]:
        cells = _cells(row)
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
        linked = [] if related == "-" else [item.strip() for item in related.split(",")]
        valid_links = all(linked) and len(set(linked)) == len(linked) if linked else related == "-"
        protocol.need(valid_links, "invalid related finding IDs")
        out.append(
            {
                "source": source,
                "sha": sha,
                "id": identity,
                "disposition": disposition,
                "related": linked,
            }
        )
    return out


def report_events(events):
    """Include checkpoints and decisions independently, even for the same artifact."""
    for event in events:
        if event["ev"] in ("reviewed", "holistic_reviewed", "review_checkpoint"):
            ref = (event["report"], event["sha"])
        elif event["ev"] == "artifact" and event.get("role") == "holistic_report":
            ref = (event["path"], event["sha"])
        else:
            continue
        yield ref, event


def read_report(root, ref):
    """Re-prove current bytes before reusing a hash-bound parse within one command."""
    protocol.reference(ref)
    path = c.repo_path(root, ref["path"])
    message = "immutable evidence drift (finding source drift): " + ref["path"]
    protocol.need(path.is_file() and not path.is_symlink(), message)
    identity = c.file_key(path)
    protocol.need(path.stat().st_size <= 1024 * 1024, "review exceeds 1 MiB")
    with path.open("rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    protocol.need(len(data) <= 1024 * 1024, "review exceeds 1 MiB")
    protocol.need(c.evidence_sha_bytes(data) == ref["sha"], message)
    protocol.need(c.file_key(path) == identity, "finding source changed while reading")
    key = (str(path.resolve()), ref["sha"])
    cache = c.cache("findings.reports")
    if cache is not None and key in cache:
        text, report = cache[key]
        return text, deepcopy(report)
    text = data.decode("utf-8")
    value = text, evidence.parse_review(text)
    c.remember("findings.reports", key, value, len(data))
    return value[0], deepcopy(value[1])


def source_label(key):
    path, sha, identity = key
    return f"{identity} (source {path}, sha {sha})"


class Projection:
    """One chronological pass; original finding identity is never rewritten."""

    def __init__(self, root):
        self.root = root
        self.findings = {}
        self.ids = {}
        self.origins = {}
        self.seen = set()
        self.diagnostics = []
        self.open = set()
        self.open_by_scope = {}

    def _index(self, key):
        item = self.findings[key]
        scopes = {item["owner"], item["owner"].split("-")[0]}
        prefix = re.match(r"^(M\d{3})-(?:(S\d{2})-)?", item["id"])
        if prefix:
            scopes.add(prefix[1])
            if prefix[2]:
                scopes.add(prefix[1] + "-" + prefix[2])
        unresolved = item["severity"] in ("P0", "P1", "P2") and item["disposition"] == "open"
        self.open.discard(key)
        if unresolved:
            self.open.add(key)
        for scope in scopes:
            keys = self.open_by_scope.setdefault(scope, set())
            keys.discard(key)
            if unresolved:
                keys.add(key)

    def add(self, ref, event):
        path, sha = ref
        text, report = read_report(self.root, {"path": path, "sha": sha})
        v2 = event.get("schema") == protocol.SCHEMA
        changes = updates(text) if v2 else []
        waived = report["verdict"] == "override" or any(
            item["disposition"] == "waived_by_human" for item in report["findings"] + changes
        )
        if waived and event["by"] != "human":
            protocol.need(not v2, "waiver requires --by human")
            self.diagnostics.append(f"Legacy waiver actor preserved at {path} ({sha})")
        if event["ev"] == "review_checkpoint" or ref in self.seen:
            return report
        self.seen.add(ref)
        owner = report["identity"]
        for item in report["findings"]:
            key = (path, sha, item["id"])
            prior = self.origins.get((owner, item["id"]))
            if v2:
                protocol.need(
                    item["severity"] == "P3" or item["disposition"] != "carried",
                    "only P3 findings may be carried",
                )
                protocol.need(
                    item["id"] not in self.ids,
                    f"finding ID collision: {item['id']}; use source-bound update",
                )
            elif prior:
                self.findings[prior].update(disposition=item["disposition"], last_report=path)
                self._index(prior)
                self.diagnostics.append(
                    f"Legacy re-list at {path} ({sha}) updates {source_label(prior)}"
                )
                continue
            elif item["id"] in self.ids:
                self.diagnostics.append(f"Legacy cross-scope duplicate id {item['id']} at {path}")
            self.origins[(owner, item["id"])] = key
            self.ids.setdefault(item["id"], set()).add(key)
            self.findings[key] = {
                **item,
                "source": {"path": path, "sha": sha},
                "related": [],
                "last_report": path,
                "owner": owner,
            }
            self._index(key)
        for change in changes:
            key = (change["source"], change["sha"], change["id"])
            protocol.need(
                key in self.findings, "unresolved finding reference: " + source_label(key)
            )
            protocol.need(
                self.findings[key]["severity"] == "P3" or change["disposition"] != "carried",
                "only P3 findings may be carried",
            )
            for linked in change["related"]:
                protocol.need(linked in self.ids, f"unknown related finding: {linked}")
                protocol.need(len(self.ids[linked]) == 1, f"ambiguous related finding: {linked}")
            self.findings[key].update(
                disposition=change["disposition"], related=change["related"], last_report=path
            )
            self._index(key)
        count = re.search(r"^Finding count: (\d+)\s*$", text, re.MULTILINE)
        if count and int(count[1]) != len(report["findings"]):
            self.diagnostics.append(f"Finding count differs from parsed IDs in {path}")
        return report

    def require_closure(self, report, current=None):
        if report["verdict"] not in ("pass", "override"):
            return
        scope = report["identity"]
        pending = set(self.open_by_scope.get(scope, ()))
        for identity in (current or {}).get("open", []):
            pending.update(self.ids.get(identity, set()) & self.open)
        unresolved = [source_label(key) for key in sorted(pending)]
        protocol.need(
            not unresolved,
            "prior findings need explicit source-bound closure: " + ", ".join(unresolved),
        )


def project(root, events, extra=None):
    projection = Projection(root)
    for ref, event in report_events(events):
        projection.add(ref, event)
    if extra:
        projection.add(*extra)
    return projection.findings, projection.diagnostics


def validate_record(root, events, path, sha, by, current=None):
    event = {"ev": "reviewed", "schema": protocol.SCHEMA, "by": by}
    projection = Projection(root)
    for ref, previous in report_events(events):
        projection.add(ref, previous)
    report = projection.add((path, sha), event)
    projection.require_closure(report, current)
    return projection.diagnostics


def reconcile(root, events):
    findings, diagnostics = project(root, events)
    path = root / "05_governance/backlog.md"
    old = path.read_text(encoding="utf-8")
    marker_lines = [line.strip() for line in old.splitlines() if "<!-- findings:" in line]
    protocol.need(
        marker_lines in ([], [BEGIN, END])
        and old.count(BEGIN) == old.count(END)
        and old.count(BEGIN) <= 1,
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

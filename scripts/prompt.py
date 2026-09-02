"""Render coding, review, or holistic prompts from project authority."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import _common as c
import ledger
import roadmap

KNOWN = {"slice_id", "title", "round", "objective", "acceptance", "non_goals", "read_first", "allowed_prefixes", "forbidden", "focused", "full", "open_findings", "memory", "diff_manifest", "coder_notes", "receipt", "prior_findings", "report_path"}


def _bullets(values, empty="- None declared."):
    return "\n".join(f"- {x}" for x in values) if values else empty


def _argv(values):
    if not values: return "- None declared."
    if isinstance(values[0], str): values = [values]
    return "\n\n".join("```text\n" + " ".join(x) + "\n```" for x in values)


def _bounded(text, rel, limit=4096):
    raw = text.encode("utf-8")
    if len(raw) <= limit: return text
    clipped = raw[:limit].decode("utf-8", "ignore")
    return clipped + f"\n\n[Embedded text truncated; read the full artifact at `{rel}`.]"


def _render(path, values, optional=()):
    text = path.read_text(encoding="utf-8"); found = set(re.findall(r"{{([a-z_]+)}}", text))
    unknown = found - KNOWN
    if unknown: raise ValueError(f"unknown placeholders: {sorted(unknown)}")
    for heading, key in optional:
        if not values.get(key): text = re.sub(rf"\n## {re.escape(heading)}\n.*?(?=\n## |\Z)", "", text, flags=re.S)
    for key in found: text = text.replace("{{" + key + "}}", str(values.get(key, "")))
    if "{{" in text or "}}" in text: raise ValueError("unresolved placeholder")
    return text.rstrip() + "\n"


def _next(root):
    used = set()
    for folder in (root / "prompts/for_coding_agent", root / "prompts/for_review_agent"):
        for path in folder.glob("*.md"):
            match = re.match(r"(\d{3})_", path.name)
            if match: used.add(int(match.group(1)))
    for value in range(1, 1000):
        if value not in used: return value
    raise ValueError("prompt number space exhausted")


def _memory(rm, item):
    memory = rm.get("memory")
    if not memory: return ""
    root = memory["root"].rstrip("/"); lines = [f"Root: `{root}`", "", "Allowed read commands:"]
    lines += [f"- `llloom --root {root} {verb}`" for verb in memory["read_verbs"]]
    pages = item.get("memory_pages", memory.get("read_first_pages", []))
    if pages: lines += ["", "Read for this slice:"] + [f"- `{x}`" for x in pages]
    lines += ["", "Cite claim or page ids used. Report stale or contradicted claims; do not hand-edit memory."]
    return "\n".join(lines)


def _findings(root, state):
    if state["open"] and state["report"]:
        report = ledger.parse_review((root / state["report"]).read_text(encoding="utf-8"))
        return "\n".join(f"| {f['id']} | {f['severity']} | {f['disposition']} | {f['summary']} |" for f in report["findings"] if f["id"] in state["open"])
    if state["receipt"]:
        receipt = json.loads((root / state["receipt"]).read_text(encoding="utf-8"))
        if not receipt["ok"]:
            cmd = receipt["commands"][-1]
            return f"Previous verification failed.\n\nstdout tail:\n```text\n{cmd['stdout_tail']}\n```\n\nstderr tail:\n```text\n{cmd['stderr_tail']}\n```"
    return ""


def coding(root, sid):
    rm, events = roadmap.load(root), ledger.read(root / "05_governance/ledger.jsonl"); state = ledger.fold(events, rm); s = state["slices"].get(sid)
    if not s or s["step"] not in ("unstarted", "fix"): raise ValueError(f"{sid} is not ready for coding prompt")
    _, item = roadmap.slice_by_id(rm, sid); focused = item.get("focused") or rm["verification"].get("focused_default", [])
    values = {"slice_id": sid, "title": item["title"], "round": s["round"], "objective": item["objective"].strip(), "acceptance": _bullets(item["acceptance"]), "non_goals": _bullets(item.get("non_goals", [])), "read_first": _bullets([f"`{x}`" for x in item.get("read_first", [])]), "allowed_prefixes": ", ".join(f"`{x}`" for x in roadmap.effective_prefixes(rm, item)), "forbidden": ", ".join(f"`{x}`" for x in rm["forbidden"]), "focused": _argv(focused), "full": _argv(item.get("verification", rm["verification"]["full"])), "open_findings": _findings(root, s), "memory": _memory(rm, item)}
    text = _render(root / "prompts/templates/coding_prompt.md", values, (("Findings to resolve", "open_findings"), ("Memory", "memory")))
    number = _next(root); path = root / "prompts/for_coding_agent" / f"{number:03d}_{sid}_r{s['round']}.md"; c.atomic_text(path, text)
    rel = path.relative_to(root).as_posix(); ledger.append(root / "05_governance/ledger.jsonl", {"ev": "prompt", "by": "architect", "slice": sid, "round": s["round"], "path": rel, "sha": c.sha(path)})
    if len(text.encode()) > 8192: print("warning: coding prompt exceeds 8 KB", file=sys.stderr)
    return rel


def review(root, sid):
    rm, events = roadmap.load(root), ledger.read(root / "05_governance/ledger.jsonl"); state = ledger.fold(events, rm); s = state["slices"].get(sid)
    if not s or s["step"] != "reviewing": raise ValueError(f"{sid} is not awaiting review")
    _, item = roadmap.slice_by_id(rm, sid); folder = f"05_governance/reviews/{sid.split('-')[0].lower()}"; report = f"{folder}/{sid}_r{s['round']}_review.md"
    receipt_text = (root / s["receipt"]).read_text(encoding="utf-8"); notes = _bounded((root / s["notes"]).read_text(encoding="utf-8"), s["notes"]) if s["notes"] else ""
    prior = _findings(root, s) if s["open"] else ""; changed = _bullets([f"`{x['path']}` ({x['kind']}, sha256 `{x['sha']}`)" for x in s["changed"]])
    values = {"slice_id": sid, "title": item["title"], "round": s["round"], "objective": item["objective"].strip(), "acceptance": _bullets(item["acceptance"]), "diff_manifest": changed, "coder_notes": notes, "receipt": f"Path: `{s['receipt']}`\n\nSHA-256: `{c.sha(root / s['receipt'])}`\n\n```json\n{receipt_text.rstrip()}\n```", "prior_findings": prior, "report_path": report}
    text = _render(root / "prompts/templates/review_prompt.md", values, (("Coder notes", "coder_notes"), ("Prior findings", "prior_findings")))
    number = _next(root); path = root / "prompts/for_review_agent" / f"{number:03d}_{sid}_r{s['round']}.md"; c.atomic_text(path, text)
    if len(text.encode()) > 24576: print("warning: review prompt exceeds 24 KB", file=sys.stderr)
    return path.relative_to(root).as_posix()


def holistic(root, mid):
    rm, events = roadmap.load(root), ledger.read(root / "05_governance/ledger.jsonl"); state = ledger.fold(events, rm); milestone = next((m for m in rm["milestones"] if m["id"] == mid), None)
    if not milestone or not milestone["holistic_review"] or any(state["slices"][x["id"]]["step"] != "accepted" for x in milestone["slices"]): raise ValueError(f"{mid} is not ready for holistic review")
    changed, receipts = [], []
    for item in milestone["slices"]:
        s = state["slices"][item["id"]]; changed += [f"`{x['path']}` ({item['id']}, {x['kind']})" for x in s["changed"]]
        if s["receipt"]: receipts.append(f"### {item['id']}\n\nVerification: `{s['receipt']}` (sha256 `{c.sha(root / s['receipt'])}`)\n\nReview: `{s['report']}`\n\n```json\n{(root / s['receipt']).read_text(encoding='utf-8').rstrip()}\n```")
    report = f"05_governance/reviews/{mid.lower()}/{mid}_holistic_review.md"; values = {"slice_id": mid, "title": milestone["title"], "round": "holistic", "objective": f"Judge holistic closure of {mid} across its accepted slices.", "acceptance": _bullets([f"{x['id']}: {a}" for x in milestone["slices"] for a in x["acceptance"]]), "diff_manifest": _bullets(changed), "coder_notes": "", "receipt": "\n\n".join(receipts), "prior_findings": "", "report_path": report}
    text = _render(root / "prompts/templates/review_prompt.md", values, (("Coder notes", "coder_notes"), ("Prior findings", "prior_findings"))); number = _next(root); path = root / "prompts/for_review_agent" / f"{number:03d}_{mid}_holistic.md"; c.atomic_text(path, text); return path.relative_to(root).as_posix()


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("slice", nargs="?"); parser.add_argument("--review", action="store_true"); parser.add_argument("--holistic"); parser.add_argument("--root", type=Path, default=c.ROOT); args = parser.parse_args(argv)
    try:
        if args.holistic: rel = holistic(args.root.resolve(), args.holistic)
        elif not args.slice: raise ValueError("provide a slice or --holistic Mnnn")
        elif args.review: rel = review(args.root.resolve(), args.slice)
        else: rel = coding(args.root.resolve(), args.slice)
        print(rel); return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc: print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())

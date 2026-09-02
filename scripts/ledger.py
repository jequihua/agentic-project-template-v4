import argparse, hashlib, json, os, re, sys
import _common as c, roadmap
SCHEMA, EVENTS = "frutlups.ledger/1", {"prompt", "coded", "verified", "reviewed", "accepted", "reopened", "milestone_done", "note", "stop"}
COMMON = {"schema", "t", "ev", "by"}
FIELDS = {"prompt": {"slice", "round", "path", "sha"}, "coded": {"slice", "round", "changed", "notes_path", "seat", "secs", "tokens_in", "tokens_out"}, "verified": {"slice", "round", "receipt", "sha", "ok"}, "reviewed": {"slice", "round", "report", "sha", "verdict", "open", "seat", "secs", "tokens_in", "tokens_out", "cost_usd"}, "accepted": {"slice", "round", "commit"}, "reopened": {"slice", "round", "reason"}, "milestone_done": {"milestone", "holistic_report"}, "note": {"text", "slice"}, "stop": {"reason", "detail"}}
OPTIONAL = {"coded": {"notes_path", "seat", "secs", "tokens_in", "tokens_out"}, "reviewed": {"seat", "secs", "tokens_in", "tokens_out", "cost_usd"}, "accepted": {"commit"}, "milestone_done": {"holistic_report"}, "note": {"slice"}}
SHA, COMMIT = re.compile(r"[0-9a-f]{64}$"), re.compile(r"[0-9a-f]{7,64}$")
def _need(ok, message): return None if ok else (_ for _ in ()).throw(ValueError(message))
def _validate(event, line="event"):
    _need(isinstance(event, dict), f"{line}: event must be an object"); ev = event.get("ev")
    _need(event.get("schema") == SCHEMA and ev in EVENTS, f"{line}: invalid schema or event"); _need(event.get("by") in ("human", "architect", "frutlups"), f"{line}: invalid by"); _need(isinstance(event.get("t"), str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", event["t"]), f"{line}: invalid UTC timestamp")
    unknown, missing = set(event) - COMMON - FIELDS[ev], FIELDS[ev] - OPTIONAL.get(ev, set()) - set(event)
    _need(not unknown and not missing, f"{line}: unknown={sorted(unknown)} missing={sorted(missing)}"); _need("round" not in event or type(event["round"]) is int and event["round"] >= 1, f"{line}: invalid round"); _need("slice" not in event or bool(re.fullmatch(r"M\d{3}-S\d{2}", str(event["slice"]))), f"{line}: invalid slice"); _need("milestone" not in event or bool(re.fullmatch(r"M\d{3}", str(event["milestone"]))), f"{line}: invalid milestone")
    for key in ("path", "receipt", "report", "notes_path", "holistic_report"):
        if key in event: c.safe_rel(event[key])
    _need("sha" not in event or isinstance(event["sha"], str) and bool(SHA.fullmatch(event["sha"])), f"{line}: invalid sha"); _need("commit" not in event or isinstance(event["commit"], str) and bool(COMMIT.fullmatch(event["commit"])), f"{line}: invalid commit")
    if ev == "coded":
        _need(isinstance(event["changed"], list), f"{line}: changed must be a list")
        for n, item in enumerate(event["changed"]):
            _need(isinstance(item, dict) and set(item) == {"path", "sha", "kind"} and item.get("kind") in ("added", "modified", "deleted", "renamed") and bool(SHA.fullmatch(str(item.get("sha", "")))), f"{line}: invalid changed[{n}]"); c.safe_rel(item["path"])
    _need(ev != "verified" or isinstance(event["ok"], bool), f"{line}: ok must be boolean"); _need(ev != "reviewed" or event["verdict"] in ("pass", "needs_work", "blocked", "override") and (event["verdict"] != "override" or event["by"] == "human") and isinstance(event["open"], list) and all(isinstance(x, str) and x for x in event["open"]), f"{line}: invalid review fields"); _need(all(key not in event or isinstance(event[key], str) and event[key].strip() for key in ("reason", "detail", "text", "seat")) and all(key not in event or type(event[key]) in (int, float) and event[key] >= 0 for key in ("secs", "cost_usd")) and all(key not in event or type(event[key]) is int and event[key] >= 0 for key in ("tokens_in", "tokens_out")) and (ev != "stop" or event["by"] == "frutlups"), f"{line}: invalid text, usage, or actor field")
    return event
def read(path: c.Path):
    if not path.exists(): return []
    out = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw: continue
        try: out.append(_validate(json.loads(raw), f"line {n}"))
        except json.JSONDecodeError as exc: raise ValueError(f"line {n}: malformed JSON: {exc.msg}") from exc
    return out
def append(path: c.Path, event):
    event = {"schema": SCHEMA, "t": c.now(), **event}; _validate(event); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream: stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"); stream.flush(); os.fsync(stream.fileno())
    return event
def fold(events, rm):
    states = {item["id"]: {"step": "unstarted", "round": 1, "open": [], "prompt": None, "receipt": None, "report": None, "changed": [], "notes": None, "reopened": False, "corrective_rounds_used": 0} for _, item in roadmap.slices(rm)}; done = set()
    milestone_ids = {m["id"] for m in rm["milestones"]}
    for event in events:
        ev = event["ev"]
        if ev in ("note", "stop"): continue
        if ev == "milestone_done":
            mid = event["milestone"]; _need(mid in milestone_ids, f"unknown milestone in ledger: {mid}"); milestone = next(m for m in rm["milestones"] if m["id"] == mid)
            _need(milestone["holistic_review"] and mid not in done and all(states[x["id"]]["step"] == "accepted" for x in milestone["slices"]), f"{mid}: invalid or premature milestone_done"); done.add(mid); continue
        sid = event.get("slice"); _need(sid in states, f"unknown slice in ledger: {sid}"); state, round_no = states[sid], event["round"]
        if ev == "prompt":
            _need(state["step"] in ("unstarted", "fix") and round_no == state["round"], f"{sid}: prompt out of order"); state.update(step="coding", prompt=event["path"]); state["corrective_rounds_used"] += round_no > 1
        elif ev == "coded":
            _need(state["step"] == "coding" and round_no == state["round"], f"{sid}: coded out of order"); state.update(step="verifying", changed=event["changed"], notes=event.get("notes_path"))
        elif ev == "verified":
            _need(state["step"] == "verifying" and round_no == state["round"], f"{sid}: verified out of order"); state.update(step="reviewing" if event["ok"] else "fix", receipt=event["receipt"], round=round_no if event["ok"] else round_no + 1)
        elif ev == "reviewed":
            _need(state["step"] == "reviewing" and round_no == state["round"], f"{sid}: reviewed out of order"); step = {"pass": "accept_pending", "override": "accept_pending", "needs_work": "fix", "blocked": "blocked"}[event["verdict"]]; state.update(step=step, report=event["report"], open=event["open"], round=round_no + (step == "fix"))
        elif ev == "accepted":
            _need(state["step"] == "accept_pending" and round_no == state["round"], f"{sid}: accepted out of order"); state.update(step="accepted", open=[], reopened=False)
        elif ev == "reopened":
            _need(state["step"] == "accepted" and round_no == state["round"] + 1, f"{sid}: reopened out of order"); state.update(step="fix", round=round_no, open=[], reopened=True); done.discard(sid.split("-")[0])
    return {"slices": states, "milestones_done": done, "events": len(events)}
def next_slice(rm, state):
    for _, item in roadmap.slices(rm):
        if state["slices"][item["id"]]["reopened"] and state["slices"][item["id"]]["step"] != "accepted": return item["id"]
    for milestone in rm["milestones"]:
        if milestone["status"] == "active": return next((x["id"] for x in milestone["slices"] if state["slices"][x["id"]]["step"] != "accepted"), None)
    return None
def status_text(rm, state): return "\n".join([f"{item['id']} r{state['slices'][item['id']]['round']} {state['slices'][item['id']]['step']}" for _, item in roadmap.slices(rm)] + [f"next: {next_slice(rm, state) or 'none'}"])
def _visible_lines(text):
    out, fence = [], None
    for line in text.splitlines():
        mark = re.match(r"^\s*(`{3,}|~{3,})", line)
        if mark: token = mark.group(1)[0]; fence = token if fence is None else None if fence == token else fence; continue
        if fence is None: out.append(line)
    return out
def parse_review(text):
    lines = _visible_lines(text); headings = {h: [i for i, line in enumerate(lines) if line.strip() == h] for h in ("## Findings", "## Closure Decision", "## Verdict")}
    if any(len(found) != 1 for found in headings.values()): raise ValueError("review requires exactly one Findings, Closure Decision, and Verdict heading")
    fi, ci, vi = (headings[h][0] for h in headings)
    if not fi < ci < vi: raise ValueError("review sections are out of order")
    title = next((line for line in lines[:fi] if re.fullmatch(r"# Review: M\d{3}(?:-S\d{2})? round (?:\d+|holistic)", line.strip())), None)
    if not title: raise ValueError("review title is missing or invalid")
    identity, round_text = re.fullmatch(r"# Review: (M\d{3}(?:-S\d{2})?) round (\d+|holistic)", title.strip()).groups(); table = [line for line in lines[fi + 1:ci] if line.strip().startswith("|")]
    if len(table) < 2 or [x.strip() for x in table[0].strip().strip("|").split("|")] != ["id", "severity", "disposition", "summary"] or not all(set(x.strip()) <= {"-", ":"} for x in table[1].strip().strip("|").split("|")): raise ValueError("findings table header or separator is missing")
    findings, seen = [], set()
    for line in table[1:]:
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) == 4 and all(set(x) <= {"-", ":"} for x in cells): continue
        if len(cells) != 4 or cells[0] in seen or cells[1] not in ("P0", "P1", "P2", "P3") or cells[2] not in ("open", "closed_by_review", "carried", "waived_by_human") or not cells[0] or not cells[3]: raise ValueError(f"invalid findings row: {line.strip()}")
        seen.add(cells[0]); findings.append(dict(zip(("id", "severity", "disposition", "summary"), cells)))
    closure = [x.strip() for x in lines[ci + 1:vi] if x.strip()]; statuses = [x.removeprefix("Objective status: ") for x in closure if x.startswith("Objective status: ")]; evidence = [x.removeprefix("Objective evidence: ") for x in closure if x.startswith("Objective evidence: ")]
    if len(statuses) != 1 or statuses[0] not in ("achieved", "not_achieved", "indeterminate") or len(evidence) != 1 or not evidence[0]: raise ValueError("invalid closure decision")
    verdict_lines = [x.strip() for x in lines[vi + 1:] if x.strip()]
    match = re.fullmatch(r"Verdict: (pass|needs_work|blocked|override) - next: (.+)", verdict_lines[0]) if verdict_lines else None
    if not match or any(x.startswith("Verdict:") for x in verdict_lines[1:]): raise ValueError("invalid verdict line")
    verdict, move = match.groups(); open_ids = [x["id"] for x in findings if x["severity"] in ("P0", "P1", "P2") and x["disposition"] == "open"]
    if verdict in ("pass", "override") and open_ids: raise ValueError(f"{verdict} cannot have open P0-P2 findings")
    return {"identity": identity, "round": None if round_text == "holistic" else int(round_text), "findings": findings, "objective_status": statuses[0], "objective_evidence": evidence[0], "verdict": verdict, "next_move": move, "open": open_ids}
def changed_files(root):
    raw, out, i = c.status_bytes(root).split(b"\0"), [], 0
    while i < len(raw) and raw[i]:
        record = raw[i].decode("utf-8", "surrogateescape"); code, rel = record[:2], record[3:].replace("\\", "/"); i += 1
        kind = "renamed" if "R" in code else "deleted" if "D" in code else "added" if code == "??" or "A" in code else "modified"
        if kind == "renamed" and i < len(raw): i += 1
        path = c.repo_path(root, c.safe_rel(rel))
        if path.is_symlink(): raise ValueError(f"changed path is a symlink: {rel}")
        if kind == "deleted": digest = hashlib.sha256(c.git(root, "show", f"HEAD:{rel}").stdout).hexdigest()
        elif path.is_file(): digest = c.sha(path)
        else: raise ValueError(f"changed path is not a regular file: {rel}")
        out.append({"path": rel, "sha": digest, "kind": kind})
    return out
def _matches(path, rule): return path.startswith(rule) if rule.endswith("/") else path == rule
def fence(changed, allowed, forbidden): return [x["path"] for x in changed if any(_matches(x["path"], rule) for rule in forbidden) or not any(_matches(x["path"], rule) for rule in allowed)]
def _rel_file(root, value):
    rel = c.safe_rel(value); path = c.repo_path(root, rel)
    if not path.is_file() or path.is_symlink(): raise ValueError(f"not a regular repository file: {rel}")
    return rel, path
def _tool_paths(events):
    paths = {"05_governance/ledger.jsonl", "05_governance/backlog.md"}
    paths.update(event[key] for event in events for key in ("path", "notes_path", "receipt", "report", "holistic_report") if event.get(key))
    return paths
def _artifacts_for(root, events, sid):
    return sorted({"05_governance/ledger.jsonl", "05_governance/backlog.md"} | {event[key] for event in events if event.get("slice") == sid for key in ("path", "notes_path", "receipt", "report") if event.get(key)} | {item["path"] for event in events if event.get("slice") == sid and event["ev"] == "coded" for item in event["changed"]} | {path.relative_to(root).as_posix() for folder in ("for_coding_agent", "for_review_agent") for path in (root / "prompts" / folder).glob(f"*_{sid}_*.md")})
def check(root, rm, events):
    fold(events, rm); errors, latest = [], {}
    for event in events:
        for key in ("path", "receipt", "report"):
            if event.get(key):
                path = c.repo_path(root, event[key])
                if path.is_symlink() or not path.is_file() or c.sha(path) != event["sha"]: errors.append(f"drift: {event[key]}")
        if event.get("notes_path") and (c.repo_path(root, event["notes_path"]).is_symlink() or not c.repo_path(root, event["notes_path"]).is_file()): errors.append(f"missing: {event['notes_path']}")
        if event["ev"] == "coded":
            for item in event["changed"]: latest[item["path"]] = item
    for rel, item in latest.items():
        path = c.repo_path(root, rel)
        if item["kind"] == "deleted":
            if path.exists(): errors.append(f"drift: {rel} was deleted")
        elif path.is_symlink() or not path.is_file() or c.sha(path) != item["sha"]: errors.append(f"drift: {rel}")
    return errors
def _parser():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=c.Path, default=c.ROOT); sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prompt"); item.add_argument("slice"); item.add_argument("path"); item.add_argument("--by", default="architect")
    item = sub.add_parser("coded"); item.add_argument("slice"); item.add_argument("--notes"); item.add_argument("--by", default="architect")
    item = sub.add_parser("record"); item.add_argument("report"); item.add_argument("--milestone"); item.add_argument("--by", default="architect")
    item = sub.add_parser("accept"); item.add_argument("slice"); item.add_argument("--commit", action="store_true"); item.add_argument("--commit-id"); item.add_argument("--by", default="architect")
    item = sub.add_parser("reopen"); item.add_argument("slice"); item.add_argument("--reason", required=True); item.add_argument("--by", default="human")
    sub.add_parser("status"); item = sub.add_parser("index"); item.add_argument("--output"); sub.add_parser("check"); return parser
def _record(root, path, args, rm, events, state):
    rel, file = _rel_file(root, path); review = parse_review(file.read_text(encoding="utf-8")); ledger_path = root / "05_governance/ledger.jsonl"
    if args.milestone:
        if review["identity"] != args.milestone or review["round"] is not None or review["verdict"] == "override" and args.by != "human" or not any(m["id"] == args.milestone and m["holistic_review"] and all(state["slices"][x["id"]]["step"] == "accepted" for x in m["slices"]) for m in rm["milestones"]): raise ValueError("holistic report identity, authority, or readiness mismatch")
        if review["verdict"] in ("pass", "override"): append(ledger_path, {"ev": "milestone_done", "by": args.by, "milestone": args.milestone, "holistic_report": rel})
        else:
            targets = [(finding, next((x for _, x in roadmap.slices(rm) if finding.startswith(x["id"] + "-")), None)) for finding in review["open"]]
            if not targets or any(not item or state["slices"][item["id"]]["step"] != "accepted" for _, item in targets): raise ValueError("every holistic open finding must identify an accepted slice")
            for finding, item in targets:
                current = state["slices"][item["id"]]
                append(ledger_path, {"ev": "reopened", "by": args.by, "slice": item["id"], "round": current["round"] + 1, "reason": f"holistic finding {finding}"})
        print(f"{args.milestone} holistic {review['verdict']}"); return
    sid, round_no = review["identity"], review["round"]; current = state["slices"].get(sid)
    if not current or current["step"] != "reviewing" or round_no != current["round"]: raise ValueError("review identity/round is not awaiting review")
    if (review["verdict"] == "override" or any(x["disposition"] == "waived_by_human" for x in review["findings"])) and args.by != "human": raise ValueError("override or waiver requires --by human")
    carried = [f"- {x['id']}: {x['summary']}" for x in review["findings"] if x["severity"] == "P3" and x["disposition"] == "carried"]
    if carried:
        backlog = root / "05_governance/backlog.md"; old = backlog.read_text(encoding="utf-8"); missing = [x for x in carried if x.split(":", 1)[0][2:] not in old]
        if missing: c.atomic_text(backlog, old.rstrip() + "\n\n" + "\n".join(missing) + "\n")
    append(ledger_path, {"ev": "reviewed", "by": args.by, "slice": sid, "round": round_no, "report": rel, "sha": c.sha(file), "verdict": review["verdict"], "open": review["open"]}); print(f"{sid} r{round_no} review {review['verdict']} open={len(review['open'])}")
def main(argv=None):
    args = _parser().parse_args(argv); root = args.root.resolve(); ledger_path = root / "05_governance/ledger.jsonl"
    try:
        rm, events = roadmap.load(root), read(ledger_path); state = fold(events, rm)
        if args.command == "prompt":
            roadmap.slice_by_id(rm, args.slice); current = state["slices"][args.slice]
            if current["step"] not in ("unstarted", "fix"): raise ValueError(f"{args.slice} is {current['step']}, not ready for a prompt")
            rel, path = _rel_file(root, args.path); append(ledger_path, {"ev": "prompt", "by": args.by, "slice": args.slice, "round": current["round"], "path": rel, "sha": c.sha(path)}); print(f"{args.slice} r{current['round']} prompt -> {rel}")
        elif args.command == "coded":
            _, item = roadmap.slice_by_id(rm, args.slice); current = state["slices"][args.slice]
            if current["step"] != "coding": raise ValueError(f"{args.slice} is {current['step']}, not coding")
            notes = _rel_file(root, args.notes)[0] if args.notes else None; owned = _tool_paths(events) | {current["prompt"]} | ({notes} if notes else set()); changed = [x for x in changed_files(root) if x["path"] not in owned and not x["path"].startswith(("prompts/for_coding_agent/", "prompts/for_review_agent/"))]; violations = fence(changed, roadmap.effective_prefixes(rm, item), rm["forbidden"])
            if violations: raise ValueError("write boundary violation: " + ", ".join(violations))
            event = {"ev": "coded", "by": args.by, "slice": args.slice, "round": current["round"], "changed": changed}; event.update({"notes_path": notes} if notes else {}); append(ledger_path, event); print(f"{args.slice} r{current['round']} coded changed={len(changed)}")
        elif args.command == "record": _record(root, args.report, args, rm, events, state)
        elif args.command == "accept":
            current = state["slices"][args.slice]
            if current["step"] != "accept_pending": raise ValueError(f"{args.slice} is {current['step']}, not accept_pending")
            event = {"ev": "accepted", "by": args.by, "slice": args.slice, "round": current["round"]}; event.update({"commit": args.commit_id} if args.commit_id else {}); append(ledger_path, event)
            if args.commit: c.git(root, "add", "-A", "--", *_artifacts_for(root, read(ledger_path), args.slice)); c.git(root, "commit", "-m", f"Accept {args.slice} round {current['round']}"); print(f"{args.slice} accepted commit {c.git(root, 'rev-parse', 'HEAD', text=True).stdout.strip()}")
            else: print(f"{args.slice} accepted")
        elif args.command == "reopen":
            current = state["slices"][args.slice]
            if current["step"] != "accepted": raise ValueError(f"{args.slice} is not accepted")
            append(ledger_path, {"ev": "reopened", "by": args.by, "slice": args.slice, "round": current["round"] + 1, "reason": args.reason}); print(f"{args.slice} reopened r{current['round'] + 1}")
        elif args.command == "status": print(status_text(rm, state))
        elif args.command == "index":
            rows = ["| Slice | Round | Verdict | Report |", "| --- | ---: | --- | --- |"] + [f"| {e['slice']} | {e['round']} | {e['verdict']} | `{e['report']}` |" for e in events if e["ev"] == "reviewed"]; text = "# Review index\n\n" + "\n".join(rows) + "\n"
            if args.output: c.atomic_text(c.repo_path(root, c.safe_rel(args.output)), text)
            else: print(text, end="")
        else:
            errors = check(root, rm, events)
            if errors: print("\n".join(f"error: {x}" for x in errors), file=sys.stderr); return 2
            print("ledger: ok")
        return 0
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc: print(f"error: {exc}", file=sys.stderr); return 2
if __name__ == "__main__": raise SystemExit(main())

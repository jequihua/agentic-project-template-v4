"""Optional approval-bound Git completion, without a second mutable history."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from uuid import uuid4

import _common as c
import _git as g

SCHEMA = "frutlups.commit-manifest/1"
LEDGER = "05_governance/ledger.jsonl"
BLOB_LIMIT = g.BLOB_LIMIT
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})$")
SHA = re.compile(r"[0-9a-f]{64}$")
OPERATION = re.compile(r"[0-9a-f]{32}$")


def _json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _hash(data, storage="normalized"):
    return hashlib.sha256(data).hexdigest() if storage == "raw" else c.evidence_sha_bytes(data)


def _read(path, limit=BLOB_LIMIT):
    if path.stat().st_size > limit:
        raise ValueError("commit evidence exceeds the bounded file allowance: " + path.name)
    return path.read_bytes()


def _head(root):
    return g.run(root, "rev-parse", "--verify", "HEAD", limit=1024).stdout.decode().strip()


def _tree(root, revision):
    cache = c.cache("commit_trees") if OID.fullmatch(revision) else None
    key = (str(Path(root).resolve()), revision)
    if cache is not None and key in cache:
        return cache[key]
    data = g.run(root, "ls-tree", "-r", "-z", "--full-tree", revision).stdout
    output = {}
    for row in data.split(b"\0"):
        if not row:
            continue
        info, path = row.split(b"\t", 1)
        mode, kind, oid = info.decode("ascii").split()
        output[c.safe_rel(path.decode("utf-8"))] = (mode, kind, oid)
    if cache is not None and cache.get(None, 0) + len(data) <= g.OUTPUT_LIMIT:
        cache[key] = output
        cache[None] = cache.get(None, 0) + len(data)
    return output


def _at(root, tree, path):
    row = tree.get(path)
    if row is None or row[1] != "blob":
        raise ValueError("missing committed evidence: " + path)
    cache = c.cache("commit_small_blobs")
    key = (str(Path(root).resolve()), row[2])
    if cache is not None and key in cache:
        return cache[key]
    ((_, data),) = g.read_blobs(root, [row[2]])
    if cache is not None and cache.get(None, 0) + len(data) <= g.OUTPUT_LIMIT:
        cache[key] = data
        cache[None] = cache.get(None, 0) + len(data)
    return data


def _storage(root, paths):
    data = g.run(
        root,
        "check-attr",
        "-z",
        "--stdin",
        "text",
        input=b"".join(path.encode("utf-8") + b"\0" for path in paths),
    ).stdout.split(b"\0")
    return {
        data[i].decode("utf-8"): "raw" if data[i + 2] == b"unset" else "normalized"
        for i in range(0, len(data) - 1, 3)
    }


def _mode(root, path, parent_tree):
    if os.name == "nt":
        return parent_tree.get(path, ("100644",))[0]
    value = c.repo_path(root, path).stat().st_mode
    filemode = g.run(root, "config", "--bool", "core.filemode", check=False, limit=1024)
    if filemode.stdout.strip() == b"false" and path in parent_tree:
        return parent_tree[path][0]
    return "100755" if value & 0o111 else "100644"


def _boundary_policy(rm):
    verification = rm.get("verification", {})
    command = verification.get("git_boundary")
    if not command:
        return None
    value = {
        "argv": list(command),
        "timeout_seconds": verification.get("timeout_seconds", 600),
        "runtime": dict(rm.get("runtime", {})),
    }
    _validate_policy(value)
    return value


def _validate_policy(value):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"argv", "timeout_seconds", "runtime"}:
        raise ValueError("invalid frozen Git-boundary policy")
    argv, timeout, runtime = value["argv"], value["timeout_seconds"], value["runtime"]
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
        or type(timeout) is not int
        or timeout <= 0
    ):
        raise ValueError("invalid frozen Git-boundary command or timeout")
    if not isinstance(runtime, dict) or set(runtime) - {"python"}:
        raise ValueError("invalid frozen project runtime")
    if runtime and not re.fullmatch(r"3\.\d+(?:\.\d+)?", str(runtime.get("python", ""))):
        raise ValueError("Git-boundary runtime must be a portable Python version")


def request_intent(root, paths, scope, message, rm, artifact_dir):
    """Create the immutable payload manifest before the caller appends approval."""
    root = Path(root)
    if rm.get("schema") != "frutlups.roadmap/2":
        raise ValueError("commit intent requires frutlups.roadmap/2")
    if not re.fullmatch(r"M\d{3}(?:-S\d{2})?", scope):
        raise ValueError("invalid commit operation scope")
    if not isinstance(message, str) or not message.strip() or len(message.encode()) > 4096:
        raise ValueError("commit message must contain 1..4096 UTF-8 bytes")
    if "Template-Operation:" in message:
        raise ValueError("commit message cannot supply an operation trailer")
    paths = g.approved_paths(root, paths)
    paths = [path for path in paths if path != LEDGER]
    g.guard_index(root, [*paths, LEDGER])
    parent = _head(root)
    parent_tree = _tree(root, parent)
    index_tree = g.run(root, "write-tree", limit=1024).stdout.decode().strip()
    initial_index = _tree(root, index_tree)
    storage = _storage(root, paths) if paths else {}
    deleted = [path for path in paths if not c.repo_path(root, path).exists()]
    old_blobs = g.blob_hashes(root, [parent_tree[p][2] for p in deleted if p in parent_tree])
    entries = []
    for path in paths:
        target = c.repo_path(root, path)
        mode = target.lstat().st_mode if target.exists() or target.is_symlink() else None
        if mode is not None and not stat.S_ISREG(mode):
            raise ValueError("commit payload must be a regular file: " + path)
        kind = storage[path]
        if mode is None:
            old = parent_tree.get(path)
            if old is None:
                # A prior-round untracked addition can end as a cumulative tombstone.
                # Its evidence manifest persists, but it has no Git payload or delta.
                continue
            if old[1] != "blob":
                raise ValueError("approved deletion has no parent blob: " + path)
            digest = old_blobs[old[2]][kind]
            git_mode = old[0]
        else:
            digest = _hash(_read(target), kind)
            git_mode = _mode(root, path, initial_index)
        entries.append(
            {
                "path": path,
                "state": "deleted" if mode is None else "file",
                "sha": digest,
                "storage": kind,
                "mode": git_mode,
            }
        )
    operation = uuid4().hex
    directory = c.safe_rel(str(artifact_dir).replace("\\", "/").rstrip("/"))
    rel = directory + "/commit-" + operation + ".json"
    target = c.repo_path(root, rel)
    ledger_path = c.repo_path(root, LEDGER)
    if ledger_path.is_symlink() or ledger_path.exists() and not ledger_path.is_file():
        raise ValueError("commit ledger must be a regular file")
    prefix = _read(ledger_path) if ledger_path.exists() else b""
    if prefix and not prefix.endswith(b"\n"):
        raise ValueError("ledger must end in a newline before commit intent")
    manifest = {
        "schema": SCHEMA,
        "id": operation,
        "scope": scope,
        "parent": parent,
        "index_tree": index_tree,
        "entries": entries,
        "ledger": {"path": LEDGER, "prefix_sha": c.evidence_sha_bytes(prefix)},
        "git_boundary": _boundary_policy(rm),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = _json(manifest).encode("utf-8")
    c.artifact_text(target, encoded.decode("utf-8"))
    return {
        "id": operation,
        "parent": parent,
        "manifest": {"path": rel, "sha": c.evidence_sha_bytes(encoded)},
        "message": message.strip(),
    }


def _intent(value):
    if not isinstance(value, dict) or set(value) != {"id", "parent", "manifest", "message"}:
        raise ValueError("invalid commit intent fields")
    if not OPERATION.fullmatch(str(value["id"])) or not OID.fullmatch(str(value["parent"])):
        raise ValueError("invalid commit operation or parent identity")
    ref = value["manifest"]
    if not isinstance(ref, dict) or set(ref) != {"path", "sha"}:
        raise ValueError("invalid commit manifest reference")
    c.safe_rel(ref["path"])
    if not SHA.fullmatch(str(ref["sha"])):
        raise ValueError("invalid commit manifest hash")
    message = value["message"]
    if not isinstance(message, str) or not message.strip() or len(message.encode()) > 4096:
        raise ValueError("invalid commit message")
    if "Template-Operation:" in message:
        raise ValueError("duplicate operation trailer in commit message")
    return value


def _manifest(data, intent, scope):
    if c.evidence_sha_bytes(data) != intent["manifest"]["sha"]:
        raise ValueError("commit manifest hash mismatch")
    manifest = json.loads(data)
    keys = {"schema", "id", "scope", "parent", "index_tree", "entries", "ledger", "git_boundary"}
    if not isinstance(manifest, dict) or set(manifest) != keys:
        raise ValueError("invalid commit manifest fields")
    if (manifest["schema"], manifest["id"], manifest["scope"], manifest["parent"]) != (
        SCHEMA,
        intent["id"],
        scope,
        intent["parent"],
    ):
        raise ValueError("commit manifest operation does not match approval")
    if not OID.fullmatch(str(manifest["index_tree"])):
        raise ValueError("invalid initial index identity")
    _validate_policy(manifest["git_boundary"])
    ledger = manifest["ledger"]
    if (
        not isinstance(ledger, dict)
        or set(ledger) != {"path", "prefix_sha"}
        or ledger["path"] != LEDGER
        or not SHA.fullmatch(str(ledger["prefix_sha"]))
    ):
        raise ValueError("invalid commit ledger identity")
    entries = manifest["entries"]
    if not isinstance(entries, list) or len(entries) > 100_000:
        raise ValueError("invalid commit payload entries")
    seen = {LEDGER, intent["manifest"]["path"]}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "state",
            "sha",
            "storage",
            "mode",
        }:
            raise ValueError("invalid commit payload entry")
        path = c.safe_rel(entry["path"])
        if (
            path in seen
            or entry["state"] not in ("file", "deleted")
            or not SHA.fullmatch(str(entry["sha"]))
            or entry["storage"] not in ("raw", "normalized")
            or entry["mode"] not in ("100644", "100755")
        ):
            raise ValueError("invalid or duplicate commit payload identity")
        seen.add(path)
    return manifest


def _ledger_prefix(root, event, manifest):
    data = _read(Path(root) / LEDGER)
    prefix = b""
    for line in data.splitlines(keepends=True):
        if line.strip():
            parsed = json.loads(line)
            if parsed.get("commit_intent", {}).get("id") == event["commit_intent"]["id"]:
                if parsed != event:
                    raise ValueError("commit approval differs from supplied ledger history")
                if c.evidence_sha_bytes(prefix) != manifest["ledger"]["prefix_sha"]:
                    raise ValueError("ledger prefix preceding approval has changed")
                return prefix + line
        prefix += line
    raise ValueError("commit approval is missing from the working ledger")


def _candidates(root, intent):
    result = g.run(
        root,
        "log",
        "--all",
        "--ancestry-path",
        intent["parent"] + "^{commit}..",
        "--max-count=10001",
        "--format=%H%x00%P%x00%B%x00",
    )
    fields = result.stdout.split(b"\0")
    count = (len(fields) - 1) // 3
    if count > 10_000:
        raise ValueError("commit witness search exceeds 10000 descendant commits")
    found = []
    message_expected = intent["message"] + "\n\nTemplate-Operation: " + intent["id"]
    for index in range(0, len(fields) - 2, 3):
        oid = fields[index].decode("ascii").strip()
        parents = fields[index + 1].decode("ascii").split()
        message = fields[index + 2].decode("utf-8", "replace")
        if parents == [intent["parent"]] and message.strip() == message_expected:
            found.append((oid, parents, message))
    return found


def _candidate(root, tree, parent_tree, manifest, intent, prefix):
    allowed = {e["path"] for e in manifest["entries"]} | {LEDGER, intent["manifest"]["path"]}
    changed = {p for p in tree.keys() | parent_tree.keys() if tree.get(p) != parent_tree.get(p)}
    if changed - allowed:
        raise ValueError("commit candidate contains unrelated changed paths")
    ledger_mode = parent_tree.get(LEDGER, ("100644",))[0]
    for path, mode in ((LEDGER, ledger_mode), (intent["manifest"]["path"], "100644")):
        if tree.get(path, ())[:2] != (mode, "blob"):
            raise ValueError("framework commit evidence type or mode differs: " + path)
    framework = [LEDGER, intent["manifest"]["path"]]
    objects = [tree[path][2] for path in framework]
    for entry in manifest["entries"]:
        path = entry["path"]
        row = tree.get(path)
        if entry["state"] == "deleted":
            if row is not None or path not in parent_tree:
                raise ValueError("approved deletion differs: " + path)
            row = parent_tree[path]
        if row is None or row[:2] != (entry["mode"], "blob"):
            raise ValueError("approved file type or mode differs: " + path)
        objects.append(row[2])
    blobs = g.blob_hashes(root, objects)
    for entry in manifest["entries"]:
        source = parent_tree if entry["state"] == "deleted" else tree
        if blobs[source[entry["path"]][2]][entry["storage"]] != entry["sha"]:
            raise ValueError("approved Git blob content differs: " + entry["path"])
    if blobs[tree[LEDGER][2]]["normalized"] != c.evidence_sha_bytes(prefix):
        raise ValueError("committed ledger is not the intended ordered approval prefix")
    manifest_hash = blobs[tree[intent["manifest"]["path"]][2]]["normalized"]
    if manifest_hash != intent["manifest"]["sha"]:
        raise ValueError("committed manifest differs from approval")


def _load(root, event, candidate=None):
    intent = _intent(event["commit_intent"])
    scope = event.get("slice", event.get("milestone"))
    tree = _tree(root, candidate[0]) if candidate else None
    data = (
        _at(root, tree, intent["manifest"]["path"])
        if tree is not None
        else _read(c.repo_path(Path(root), intent["manifest"]["path"]))
    )
    manifest = _manifest(data, intent, scope)
    prefix = _ledger_prefix(root, event, manifest)
    if candidate:
        expected_message = intent["message"] + "\n\nTemplate-Operation: " + intent["id"]
        if candidate[1] != [intent["parent"]] or candidate[2].strip() != expected_message:
            raise ValueError("commit witness has the wrong parent or message")
        cache = c.cache("commit_witnesses")
        key = (
            str(Path(root).resolve()),
            candidate[0],
            _json(event),
            intent["manifest"]["sha"],
            c.evidence_sha_bytes(prefix),
        )
        if cache is None or key not in cache:
            _candidate(root, tree, _tree(root, intent["parent"]), manifest, intent, prefix)
            if cache is not None:
                cache[key] = True
    return intent, manifest, prefix


def status(root, events, rm):
    """Derive Git completion without looking at today's payload/index for witnesses."""
    cancelled = {e["operation"] for e in events if e.get("ev") == "commit_cancelled"}
    output = []
    seen = set()
    for event in events:
        if "commit_intent" not in event:
            continue
        intent = _intent(event["commit_intent"])
        if intent["id"] in seen:
            raise ValueError("duplicate commit operation identity")
        seen.add(intent["id"])
        state = "cancelled" if intent["id"] in cancelled else "pending"
        row = {"id": intent["id"], "scope": event.get("slice", event.get("milestone"))}
        candidates = _candidates(root, intent)
        valid, failures = [], []
        for candidate in candidates:
            try:
                _load(root, event, candidate)
            except ValueError as exc:
                failures.append(exc)
                continue
            valid.append(candidate)
        if len(valid) > 1 and state != "cancelled":
            raise ValueError("duplicate commit witnesses for operation " + intent["id"])
        if state == "cancelled":
            _load(root, event)
            if valid:
                raise ValueError("cancelled intent has an unexpected completion witness")
            row["state"] = state
            output.append(row)
            continue
        if valid:
            row.update(state="completed", commit=valid[0][0])
        else:
            if failures:
                raise failures[0]
            _load(root, event)
            row["state"] = state
        output.append(row)
    if sum(row["state"] == "pending" for row in output) > 1:
        raise ValueError("more than one pending commit operation")
    return output


def _marker(root):
    directory = g.run(root, "rev-parse", "--git-common-dir", limit=4096).stdout.decode().strip()
    return (Path(root) / directory).resolve() / "template-commit-inflight"


def resolve_inflight(root, operation_id, reason, by):
    """Caller must first obtain explicit human/architect attribution of Git exit."""
    valid = by in ("human", "architect") and isinstance(reason, str) and reason.strip()
    if not valid:
        raise ValueError("Git attribution requires human/architect and a reason")
    if not OPERATION.fullmatch(str(operation_id)):
        raise ValueError("invalid commit operation identity")
    marker = _marker(root)
    if marker.exists():
        if marker.is_symlink() or not marker.is_file():
            raise ValueError("in-flight Git marker must remain a regular file")
        data = json.loads(_read(marker, 4096))
        if data.get("operation") != operation_id:
            raise ValueError("in-flight Git marker belongs to another operation")
        data["resolution"] = {"by": by, "reason": reason}
        # Preserve diagnostics; resolution does not manufacture an approval or Git witness.
        resolved = marker.with_name("template-commit-resolved-" + operation_id)
        c.atomic_text(resolved, _json(data))
        marker.unlink()


def _index_idle(root):
    directory = g.run(root, "rev-parse", "--absolute-git-dir", limit=4096).stdout.decode().strip()
    if (Path(directory) / "index.lock").exists():
        raise ValueError("Git index.lock exists; resolve the in-flight Git operation first")


def _idle(root):
    if _marker(root).exists():
        raise ValueError("prior Git dispatch is unresolved; architect must attribute its exit")
    _index_idle(root)


def _resolve_completed_marker(root, rows, events):
    marker = _marker(root)
    if not marker.exists():
        return
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("in-flight Git marker must remain a regular file")
    data = json.loads(_read(marker, 4096))
    row = next((item for item in rows if item["id"] == data.get("operation")), None)
    if row is None or row["state"] != "completed":
        return  # Pending/unknown ownership still needs explicit exit attribution.
    event = next(item for item in events if item.get("commit_intent", {}).get("id") == row["id"])
    if data.get("parent") != event["commit_intent"]["parent"]:
        raise ValueError("in-flight Git marker parent differs from the witnessed operation")
    _index_idle(root)
    # status already proved the exact immutable commit; this archives completion,
    # not an inferred PID exit or permission to terminate a process.
    data["completion"] = {"commit": row["commit"]}
    resolved = marker.with_name("template-commit-resolved-" + row["id"])
    c.atomic_text(resolved, _json(data))
    marker.unlink()


def cancel_check(root, events, rm, operation_id):
    events_for_id = [e for e in events if e.get("commit_intent", {}).get("id") == operation_id]
    cancelled = any(
        e.get("ev") == "commit_cancelled" and e.get("operation") == operation_id for e in events
    )
    if len(events_for_id) != 1 or cancelled:
        raise ValueError("only an unwitnessed pending commit intent can be cancelled")
    event = events_for_id[0]
    intent = _intent(event["commit_intent"])
    _load(root, event)
    for candidate in _candidates(root, intent):
        try:
            _load(root, event, candidate)
        except ValueError:
            continue
        raise ValueError("completed commit intent cannot be cancelled")
    _idle(root)


def _worktree(root, manifest, intent, prefix):
    if _head(root) != intent["parent"]:
        raise ValueError("pending commit refuses unexplained HEAD movement")
    ledger_path = c.repo_path(Path(root), LEDGER)
    if ledger_path.is_symlink() or not ledger_path.is_file():
        raise ValueError("pending ledger must remain a regular file")
    if _read(ledger_path) != prefix:
        raise ValueError("ledger writes are frozen while commit intent is pending")
    if c.sha(c.repo_path(Path(root), intent["manifest"]["path"])) != intent["manifest"]["sha"]:
        raise ValueError("pending commit manifest changed")
    parent_tree = _tree(root, intent["parent"])
    initial_index = _tree(root, manifest["index_tree"])
    for entry in manifest["entries"]:
        target = c.repo_path(Path(root), entry["path"])
        if entry["state"] == "deleted":
            if target.exists() or target.is_symlink():
                raise ValueError("approved deletion was replaced: " + entry["path"])
            continue
        if not target.is_file() or target.is_symlink():
            raise ValueError("approved payload type changed: " + entry["path"])
        if _hash(_read(target), entry["storage"]) != entry["sha"]:
            raise ValueError("approved payload changed: " + entry["path"])
        if _mode(Path(root), entry["path"], initial_index) != entry["mode"]:
            raise ValueError("approved payload mode changed: " + entry["path"])
    return parent_tree


def _boundary(root, policy, tree):
    if policy is None:
        return
    import _process
    import _workspace

    before = _workspace.snapshot(Path(root))
    executable, _ = _workspace.resolve_runtime(Path(root), {"runtime": policy["runtime"]})
    command = _workspace.runtime_argv(policy["argv"], executable)
    env = dict(os.environ, TEMPLATE_CANDIDATE_TREE=tree)
    timeout = policy["timeout_seconds"]
    result = _process.run(command, cwd=Path(root), env=env, timeout=timeout, tail_limit=4096)
    after = _workspace.snapshot(Path(root))
    if before != after:
        raise ValueError("Git-boundary check mutated approved worktree/index/HEAD")
    if result.returncode != 0 or result.timed_out:
        raise ValueError("Git-boundary check rejected the exact candidate; inspect project policy")


def recover(root, events, rm, execute=False):
    """Recognize completion first; otherwise perform only exact missing Git work."""
    rows = status(root, events, rm)
    if execute:
        _resolve_completed_marker(root, rows, events)
    pending = next((r for r in rows if r["state"] == "pending"), None)
    if pending is None:
        return rows
    event = next(e for e in events if e.get("commit_intent", {}).get("id") == pending["id"])
    intent, manifest, prefix = _load(root, event)
    if _boundary_policy(rm) != manifest["git_boundary"]:
        raise ValueError(
            "Git-boundary policy changed after approval; cancel and review the new policy"
        )
    _idle(root)
    parent_tree = _worktree(root, manifest, intent, prefix)
    paths = [e["path"] for e in manifest["entries"]] + [LEDGER, intent["manifest"]["path"]]
    g.guard_index(root, paths)
    unchanged_index = g.run(
        root,
        "diff",
        "--cached",
        "--quiet",
        "--no-ext-diff",
        manifest["index_tree"],
        "--",
        check=False,
    )
    if unchanged_index.returncode not in (0, 1):
        raise ValueError("cannot inspect the pending Git index")
    if unchanged_index.returncode == 1:
        data = g.run(root, "ls-files", "--stage", "-z").stdout
        index = {}
        for row in data.split(b"\0"):
            if row:
                info, path = row.split(b"\t", 1)
                mode, oid, stage = info.decode("ascii").split()
                if stage != "0":
                    raise ValueError("unmerged entries in pending commit index")
                index[path.decode("utf-8")] = (mode, "blob", oid)
        _candidate(root, index, parent_tree, manifest, intent, prefix)
    pending["detail"] = "stage the exact approved paths and commit once"
    if not execute:
        return rows
    marker = _marker(root)
    with marker.open("x", encoding="utf-8") as stream:
        stream.write(_json({"operation": intent["id"], "parent": intent["parent"]}))
        stream.flush()
        os.fsync(stream.fileno())
    # A process crash leaves this marker for attribution. Observed results remove it.
    observed = False
    try:
        g.stage_exact(root, paths)
        _worktree(root, manifest, intent, prefix)
        tree = g.run(root, "write-tree", limit=1024).stdout.decode().strip()
        _candidate(root, _tree(root, tree), parent_tree, manifest, intent, prefix)
        _boundary(root, manifest["git_boundary"], tree)
        message = intent["message"] + "\n\nTemplate-Operation: " + intent["id"]
        g.run(root, "commit", "-m", message, limit=32768)
        observed = True
    except (ValueError, OSError):
        # These represent observed refusal, process result, or inability to launch.
        observed = True
        raise
    finally:
        if observed:
            marker.unlink(missing_ok=True)
    result = status(root, events, rm)
    if not any(r["id"] == intent["id"] and r["state"] == "completed" for r in result):
        raise ValueError("Git returned without a valid completion witness")
    return result

# Upgrading and operating the manual candidate

Manual `/2` operation requires Python 3.11+, PyYAML and Git. Package numbering
does not assert runner compatibility; the exact pair needs qualification.

| Project and tools | Supported claim |
| --- | --- |
| Existing `/1` history with the new template readers | Legacy evidence remains readable without rewriting or relabeling it. Legacy writers retain `/1` grammar. |
| `/2` project with these manual scripts | Manual candidate; use the locally recorded qualification and limitations. |
| `/2` project with frutlups 0.3.2 | Unsupported. The new roadmap schema is the static refusal gate; do not bypass it or downgrade the schema to make an old runner proceed. |
| `/2` project with a future matching runner | Pending paired conformance, offline manual/autonomous switching and final live canary; no compatible released version is asserted here. |

## New projects

Start from a reviewed export. Replace example brief/roadmap facts, prepare the
project interpreter and configure the project-owned full verifier. From the
extracted directory, run `python scripts/roadmap.py check`, then `git init`,
`git add --all` and `git commit -m "Initialize project"` (configure your Git
name/email if needed). Now run `python scripts/roadmap.py render` and perform
the ordinary prompt → coder → verification →
review → acceptance sequence. The empty shipped verifier fails intentionally.
Use `docs/project_checks.md` only for the runtime, user-path, byte policy or
research boundaries the project actually has.

`git archive HEAD` contains committed files only; select the reviewed candidate
explicitly. Publication and runner installation remain owner actions.

## Existing projects

1. Inspect the current roadmap schema, template version, customized scripts and
   prompt templates, project dependency declarations and runner version. Preserve
   a recoverable copy or owner-approved Git checkpoint. This is architect work.
2. Finish an active round at a stable accepted boundary using the current tools.
   Resolve blockers and interrupted requested commits first. Do not activate new
   writers halfway through issued prompts or a pending external invocation. A
   legacy interrupted commit has no inferred new operation trailer; it needs
   explicit architect attribution if recovery is desired.
3. Selectively merge the reviewed scripts, supporting helpers and relevant
   documentation. Preserve the real roadmap, brief, decisions, accepted reviews,
   ledger, product code and custom prompt content. In particular, preserve the
   configured project-owned verifier and merge runtime support deliberately;
   never replace it with the scaffold's empty `COMMANDS` example.
   Merge `.gitattributes` deliberately: preserve existing raw-byte `-text` scopes
   and export exclusions. Inspect existing manifests before changing line-ending
   policy; do not rehash frozen raw evidence to make an upgrade pass.
4. Install the dual readers first. Check the existing `/1` project and history
   without enabling `/2` output. Review custom templates against the full new
   acceptance-envelope placeholders and use actual preview to expose omissions.
   Add ignored `project.local.toml` only if explicit runtime selection is needed.
5. At a stable boundary, explicitly change only the roadmap writer declaration
   to `schema: frutlups.roadmap/2`, plus any separately admitted optional fields.
   Run `python scripts/roadmap.py check`, `python scripts/ledger.py check` and
   `python scripts/prompt.py <slice> --preview` with the selected interpreter.
   Do not rewrite ledger event schemas or old receipt fields. New events append
   after the byte-preserved `/1` prefix; `/1` may never follow `/2`.
6. Qualify a small disposable project and the maintained product verifier before
   using the upgraded project. Keep incompatible runner versions disabled.
   Test matching runner semantics separately before switching to autonomous use.

There is no automatic migration service. Reverting scripts or editing `/2` back
to `/1` after new events were written cannot undo a protocol upgrade safely.
Inspect and recover the real recorded state instead.

Legacy same-scope re-lists update the original disposition, retaining its first
report path/hash/ID. Cross-scope re-lists, including a milestone report closing
a slice finding, leave the slice source open. Before a later `/2` pass, close
that source explicitly. Put this section before Closure Decision, substituting
your original report identity (this example uses the conformance fixture):

```markdown
## Finding updates
| source | sha | id | disposition | related |
| --- | --- | --- | --- | --- |
| 05_governance/reviews/first.md | 972407208e033095845d05ef8c13fa07071cde1f469f3dc0fa1122da3a69e4a5 | F1 | closed_by_review | - |
```

Legacy collisions and architect holistic waivers retain their meaning with
diagnostics; `/2` waivers require human authority. Never edit historical evidence
to satisfy new rules. Non-Git `/1` ledger/render APIs retain their carve-out;
`/2` writers, including derived rendering, require the shared Git lock.

## Exceptional commands

Ordinary `coded <slice>` means implemented work, including zero changes;
`--notes <path>` optionally binds the manual handoff. Preserve blocked edits.
For a short manual blocker, avoid hand-authoring JSON:

```powershell
python scripts/ledger.py blocked M001-S01 --requirement "acceptance 1" --reason "Allowance absent" --actor human --action "Record allowance"
```

Use `--result blocked_environment` for an environment blocker. Repeatable
`--remaining`, `--evidence` and `--authority` identify actions, evidence files
and relative decision/budget paths. `--outcome <file.json>` supplies a saved
outcome instead; exact grammar is in [contracts](contracts.md). A blocker stops
before verification. Human/architect resumption uses:

```text
python scripts/ledger.py resolve M001-S01 --reason "authority now recorded" --authority 00_brief/decisions.md
```

The same verb resolves a blocked milestone. It preserves the original frozen
acceptance and grants no undeclared budget. Materially changed scope belongs in
a new slice. Legacy `/1` reviewer blocks retain `unblock <slice> --reason ...`.

`accept <slice>` is ledger-only. Inspect and manually commit accepted products
and loop evidence before the next slice. If the original approval requested
`--commit`, use `ledger.py recover` to diagnose, then `recover --execute` to
complete only missing exact Git work. Never repeat approval. An exact completed
witness permits executable recovery to archive its stale marker automatically.
A stale filename/PID alone is insufficient.

For unresolved Git ownership, first establish that the owned process ended,
then use `recover --git-resolved <operation> --reason ... --by human|architect`.
An unfinishable intent uses `cancel <operation> --reason ... --by human|architect`;
add `--git-resolved` to combine explicit process attribution with cancellation.
Only human may add `--retain-acceptance` to keep ledger-only approval; otherwise
the scope reopens. Cancellation preserves evidence, files and index and grants
no cleanup authority. Unknown model/probe reservations use the separate
[`ledger.py attempt` examples](operating.md#recovery).

Record holistic reports with `record <report> --milestone M001`. A `/2` pass
persists `close_pending`; `close M001` completes closure, optionally with an
authorized `--commit`. Blocked requires resolution; needs-work reopens affected
slices. Manual selection of another active slice remains architect authority.

`ledger.py reconcile` rebuilds only the backlog's marked region. Preserve
outside prose. `/2` closures are explicit and source-bound; only human may waive
findings. See [operating](operating.md) for the ordinary loop and crash recovery.

## Qualification handoff

Record the tested identity, toolchain, results and limitations. Local synthetic
tests do not qualify model adapters, T40/F40 mode switching, autonomous budgets
or F41's paired live canary. Upgrading authorizes no host cleanup, experiment
rerun, paid invocation or publication.

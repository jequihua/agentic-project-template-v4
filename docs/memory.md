# Optional llloom memory

No `memory` block in `roadmap.yaml` means no lane, prompt section, directory, or
command. A plain project fact file needs no lane: put it in `00_brief/` and list
it in a slice's `read_first`.

When source-grounded claims justify the cost, declare:

```yaml
memory:
  kind: llloom
  root: memory/llloom
  manual: docs/memory.md
  read_verbs: [status, query, claim-card, list-claims, list-pages, verify]
  read_first_pages: [memory/llloom/pages/navigation/index.md]
```

Enable the three commented `.gitignore` rules for rebuildable search, graph, and
lock state. Commit durable raw sources, claims, pages, schema, source registry,
and journals only after review.

## Read posture

Normal coders are read-only. The rendered prompt supplies ready-to-run
`llloom --root <root> <verb>` commands and the slice's `memory_pages`. Use only
declared verbs. Cite claim or page ids when memory shapes the change. Report
stale, missing, or contradicted claims; do not patch them during code work.

## Mutation

Only a slice with `kind: memory_update` may write the memory root. Its explicit
allowed prefixes include that root. Use a focused `doctor` command and make
`llloom --root memory/llloom verify` the slice's full verification override.

Populate/update through deterministic seed manifests: dry-run, apply, inspect
`doctor --last-op`, then verify. Never hand-edit claim YAML, registry, journals,
locks, or rendered claim blocks. A code slice may not target the memory root.

frutlups does not call llloom. When local config names the executable and the
roadmap activates memory, frutlups adds its directory to the seat PATH; the seat
uses the same prompt rules as manual mode.

# Optional llloom initialization

Use this only after `roadmap.yaml` declares a `memory` block. Install llloom from
the owner-approved source into a local environment, then use the declared root:

```powershell
llloom --root memory/llloom init
llloom --root memory/llloom doctor
llloom --root memory/llloom verify
```

Populate memory through a reviewed `memory_update` slice. Add source material,
write a deterministic seed manifest, run `seed apply --dry-run`, apply it, then
run `doctor --last-op` and `verify`. Commit durable raw sources, claims, pages,
schema, source registry, and journals; enable the commented ignores for search,
graph, and lock sidecars.

Normal coders are read-only and use only the roadmap's verbs. They cite claim or
page ids and report stale or contradicted claims rather than patching memory.

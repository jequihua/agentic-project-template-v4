# Old-Consumer Fence Fixture (executable)

Proves that a released legacy consumer refuses to render an opted-in project
rather than emitting a lossy prompt.

Released consumer identity this fixture is pinned against: frutlups 0.1.8 —
annotated tag object `f370e0743acf6f73ad08eaa13b755c87d41c5628`, peeled commit
`2d4f1c1ff76b057c79a106d6b586d4949110ed31`, package version 0.1.8.

## Compose

```text
python tests/fixtures/slice_contract/optin_project_for_old_consumer/compose.py --template <template checkout> --out <empty dir>
```

`compose.py` copies the template checkout (minus `.git` and governed local
surfaces), installs `active_roadmap.md`, `development_roadmap.md` and both
sidecars under the roadmap workspace (0.1.8 needs a milestone `Status:` line
and both projections to infer the frontier), and switches the layout's
configured coding template to the contract-v1 scaffold — the two effects of
opt-in and nothing else.

## Run the released consumer

```text
<python with frutlups 0.1.8> -m frutlups make-coding-prompt <out> --dry-run --json
```

## Expected result

- exit code 1, `would_write: false`;
- exactly the nine diagnostics in `expected_refusal.txt` (workflow metadata
  slots `milestone` and `slice` missing; expected slot missing in the seven
  legacy sections);
- no file under `<out>/prompts/for_coding_agent/` (0.1.8 wrote nothing).

The refusal keys on the v1 scaffold's slots (`TBD:<field>` tokens and the
Write Manifest form) not matching the legacy slot forms the 0.1.8 renderer
consumes; it is not an unconsumed-`TBD` diagnostic. Emitting a legacy-shaped
prompt, or leaving any slot token in an output, fails this fixture.

The template suite composes this project on a temporary directory on every
run and, when the environment variable `FRUTLUPS_0_1_8_PYTHON` names an
interpreter with frutlups 0.1.8 installed, also runs the dry-run and asserts
the refusal; otherwise that step is skipped and named as external evidence.

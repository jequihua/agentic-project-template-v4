# Failure-Model Ledger (Optional)

Optional artifact for a subsystem whose seams meet the powerful-harness
definition in `docs/template_framework/closure_convergence.md`
(operating-system, process, filesystem, network, provider, or concurrency
behavior with destructive or authority-bearing effects). Ordinary slices do
not use this template.

Write the ledger before the coding prompt is finalized; name its version in
the prompt and freeze it with the round's candidate identity. A reviewer who
believes the frozen ledger is missing a real outcome files an `envelope
expansion` finding routed to the architect — the ledger is corrected between
rounds, not argued mid-round.

Ledger version: TBD

Frozen with candidate identity: TBD

| ID | Seam | Real outcome | Support class | Authorized effect | Required response | Release severity | Causal test |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TBD | exact API, adapter, or ownership boundary | return, exception, timeout, partial effect, or host condition the real seam can produce | required / known host limitation / hostile out-of-scope / synthetic robustness | what may already have occurred when the outcome is observed | refuse, retry, clean up, preserve evidence, or report limitation | default impact if the required response is missing | how production behavior is driven without duplicating it |

Only `required` real outcomes enter the release-blocking state space by
default. A synthetic outcome may reveal valuable hardening work, but it
blocks only when a baseline safety rail is crossed or the owner explicitly
adopts it into the supported model.

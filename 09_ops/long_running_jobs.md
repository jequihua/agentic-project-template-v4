# Long-Running Job Pattern

Use this for multi-hour, resumable, expensive, or background work.

## Before Running

- state expected runtime and cost;
- run cheap decisive checks first;
- define resume behavior;
- define stop conditions;
- define what artifacts are committed.

## During Running

- write progress to a durable run artifact;
- avoid relying on chat as the only status;
- keep bulky outputs local unless curated.

## After Running

- summarize result in `03_experiments/run_summary.md`;
- record limitations;
- update `PROJECT_STATE.md` if the next action changes.


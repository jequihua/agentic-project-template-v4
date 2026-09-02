# Question Policy

When the agent cannot safely decide because evidence or ownership lives outside
the repo, it should write a question artifact instead of inventing an answer.

Questions live under `questions/open/`.

Answers live under `questions/answered/` and should cite who answered, when, and
what later artifacts should treat as authoritative.

Question statuses:
- open
- answered
- superseded
- withdrawn

Use questions for:
- external platform practice;
- unresolved product authority;
- unclear data ownership;
- credential or cost decisions;
- architecture choices outside the active scope.

Not every unknown is a question:
- a precise question whose evidence or ownership is external belongs in
  `questions/open/`;
- an in-scope concern that cannot yet be stated precisely belongs in the
  optional roadmap `Not Yet Specified` register
  (`docs/template_framework/method.md`);
- sharp work blocked on an open question stays sharp and blocked; do not hide it
  as `Not Yet Specified`.


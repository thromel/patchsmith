# MVP Definition of Done Checklist

The MVP is complete when all items below are satisfied.

## Core flow

- [ ] User can submit repository URL and issue text.
- [ ] System clones repository into isolated workspace.
- [ ] System records commit hash.
- [ ] System builds basic file index.
- [ ] System retrieves candidate files.
- [ ] LangGraph repair loop runs.
- [ ] Agent can read files through bounded tool.
- [ ] Agent can apply patch through controlled tool.
- [ ] Tests run in Docker sandbox.
- [ ] Final diff is generated.
- [ ] Markdown run report is generated.

## Observability

- [ ] Run status is persisted.
- [ ] Retrieved context is saved.
- [ ] Tool calls are logged.
- [ ] Sandbox commands are logged.
- [ ] Test output is saved.
- [ ] Cost is estimated.
- [ ] Latency is recorded.

## Safety

- [ ] No host secrets are mounted.
- [ ] Command allowlist exists.
- [ ] Timeout exists.
- [ ] Workspace path validation exists.
- [ ] Unsafe command rejection test exists.

## Evaluation

- [ ] At least 5 seeded bugs exist.
- [ ] Evaluation runner can run the seeded suite.
- [ ] Results table includes success, cost, latency, and failure category.

## Portfolio

- [ ] README explains the project in under 60 seconds.
- [ ] Demo issue is selected.
- [ ] Example run report is committed.
- [ ] Architecture diagram exists.

# Safety and Sandboxing

## Status

Draft v0.1

## Safety principle

PatchSmith Research handles untrusted repository code, generated commands, dependency install scripts, and model-written patches. Treat every repository and every generated command as potentially unsafe.

The system should be useful, but not reckless.

## Threat model

### Assets to protect

- host machine,
- environment variables,
- API keys,
- local filesystem,
- network resources,
- user identity,
- GitHub credentials,
- evaluation dataset integrity,
- run artifact integrity.

### Potential adversaries

- malicious public repository,
- compromised dependency,
- prompt injection hidden in repo files,
- model hallucinating unsafe commands,
- accidental destructive command,
- user-provided issue text requesting unsafe behavior.

### Risky operations

- installing dependencies,
- running tests,
- executing shell commands,
- applying patches,
- reading files,
- making network calls,
- pushing code,
- opening pull requests.

## Major risks

| Risk | Example | Control |
|---|---|---|
| Secret leakage | test script reads environment variables | no secrets mounted into sandbox |
| Filesystem escape | command attempts to read host files | container isolation, workspace allowlist |
| Network exfiltration | package script calls remote server | disable network by default |
| Resource exhaustion | infinite test loop | CPU, memory, and time limits |
| Prompt injection | repo file says ignore safety rules | tool policy outside model control |
| Dangerous command | model suggests `rm -rf /` | command allowlist and path validation |
| Unsafe PR action | agent pushes code automatically | human approval gate |

## Sandbox design

### MVP sandbox

Use Docker with:

- per-run container,
- isolated workspace mount,
- no host secrets,
- resource limits,
- timeout limits,
- minimal image,
- command allowlist,
- captured logs.

Current implementation:

- `local` mode is the default command-policy runner for fast development and seeded offline evals,
- `docker` mode is opt-in through `--sandbox-mode docker`,
- Docker mode runs policy-checked commands with implicit image pulls disabled, network disabled, dropped capabilities, resource limits, a `/workspace` bind mount, and a sanitized host environment,
- Docker mode requires an image that already contains the task test dependencies.
- focused public-issue setup execution defaults to dry-run and keeps dependency installs blocked unless `--allow-dependency-installs` is explicitly set with Docker mode.

### Network policy

Default:

```text
network disabled during tests
```

Exceptions:

- dependency installation may require network,
- exceptions require explicit config,
- network-enabled runs must be labeled in reports.
- setup dependency installs require Docker mode, explicit dependency-install opt-in, and an explicit network mode such as `--sandbox-network bridge`.

### Filesystem policy

Allowed:

- read and write inside run workspace,
- read project files,
- write patch artifacts and logs.

Disallowed:

- read host home directory,
- read environment secret files,
- write outside workspace,
- mount Docker socket into sandbox,
- mount SSH keys or GitHub tokens.

### Command policy

All commands must be checked before execution.

MVP allowlist:

```text
python -m pytest
pytest
python -m unittest
ruff
mypy
npm test
pnpm test
```

Focused setup allowlist:

```text
python -m pip install -e .
python -m pip install -e ".[test]"
```

This focused setup allowlist is separate from the default test-command allowlist. It is only intended for disposable Docker setup execution after readiness checks and explicit dependency-install approval.

Blocked command patterns:

```text
rm -rf /
sudo
curl ... | sh
wget ... | sh
ssh
scp
chmod 777 /
docker run
cat ~/.ssh/*
cat /etc/passwd
printenv
```

This list is not complete. It is a starting guardrail.

## Human approval gates

Human approval is required for:

- pushing code,
- opening a pull request,
- posting comments to GitHub,
- installing unusual dependencies,
- enabling network access,
- running non-allowlisted commands,
- running long or costly jobs,
- accepting new self-generated skills.

## Prompt injection handling

Repository files and issues are untrusted input. The model may read text that tries to override system behavior.

Controls:

- safety policy enforced in code, not prompt only,
- tool schemas restrict behavior,
- retrieved context is labeled as untrusted,
- generated commands are validated outside the model,
- external actions require human approval.

## Patch safety

Patch review should check:

- unexpected file changes,
- large diffs,
- dependency changes,
- test deletion,
- skipped tests,
- weakened validation,
- hardcoded secrets,
- suspicious network calls,
- broad exception swallowing.

## Self-improvement safety

The self-improving skill system must be gated.

Allowed:

- propose new textual debugging skills,
- evaluate skills offline,
- store approved skills in registry.

Disallowed:

- automatically modifying production agent code,
- accepting skills without evaluation,
- using skills that bypass sandbox policy,
- allowing skills to alter command policy.

## Logging and auditability

Every run must record:

- commands requested,
- commands approved or rejected,
- command outputs,
- files edited,
- diffs generated,
- network setting,
- sandbox settings,
- approval decisions.

## Safety checklist before public demo

- [ ] No host secrets in sandbox environment.
- [ ] Docker socket is not mounted into sandbox.
- [ ] Workspace paths are validated.
- [ ] Command allowlist exists.
- [ ] Test timeouts exist.
- [ ] Memory limits exist.
- [ ] Network is disabled by default.
- [ ] Final report labels network-enabled runs.
- [ ] Human approval gates are documented.
- [ ] Unsafe command rejection is tested.

## Known limitations

- Docker isolation is useful but not a perfect security boundary.
- Dependency installation can execute arbitrary code.
- Tests can be flaky or malicious.
- Model-generated safety reasoning is not sufficient by itself.
- Public demo should avoid arbitrary untrusted execution unless sandboxing is hardened.

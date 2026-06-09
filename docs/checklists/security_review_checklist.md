# Security Review Checklist

## Sandbox

- [ ] Sandbox uses isolated workspace.
- [ ] Host secrets are not mounted.
- [ ] Docker socket is not mounted.
- [ ] Resource limits are configured.
- [ ] Timeouts are enforced.
- [ ] Network is disabled by default or clearly labeled.

## Commands

- [ ] Commands are validated before execution.
- [ ] Command allowlist exists.
- [ ] Dangerous shell patterns are blocked.
- [ ] Path traversal is rejected.
- [ ] Commands and outputs are logged.

## Agent tools

- [ ] Tool schemas are structured.
- [ ] File reads are bounded.
- [ ] File writes are workspace-limited.
- [ ] External actions require approval.
- [ ] Tool failures are handled.

## Prompt injection

- [ ] Repo content is treated as untrusted.
- [ ] Tool policy is enforced outside the model.
- [ ] Retrieved context is labeled as untrusted.
- [ ] Suspicious instructions in files are not followed as system instructions.

## Public demo

- [ ] Demo repositories are preselected or execution is hardened.
- [ ] Arbitrary public repo execution is disabled unless safe.
- [ ] Costs are capped.
- [ ] Run artifacts do not leak secrets.

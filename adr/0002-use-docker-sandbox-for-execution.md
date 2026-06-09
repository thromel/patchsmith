# ADR 0002: Use Docker Sandbox for Execution

## Status

Accepted

## Context

PatchSmith Research must clone public repositories, install dependencies, and run tests. Public repository code and generated commands are untrusted. Running them directly on the host machine is unsafe.

## Decision

Use Docker as the MVP sandbox mechanism for repository setup and test execution.

Each run will use an isolated workspace and container configuration with:

- no host secrets,
- resource limits,
- timeouts,
- command policy checks,
- captured stdout/stderr,
- optional network isolation.

## Consequences

### Positive

- Stronger isolation than host execution.
- Reproducible run environments.
- Clear safety story for portfolio review.
- Easier artifact capture.

### Negative

- Docker is not a perfect security boundary.
- Dependency installation can still be risky.
- Environment reproduction may be complex.
- Hosted demos require additional hardening.

## Alternatives considered

### Direct host execution

Rejected because it is unsafe for untrusted code.

### Firecracker microVMs

Stronger isolation, but too heavy for MVP.

### Kubernetes jobs

Useful later, but premature for local MVP.

## Guardrail

The sandbox runner must be accessed through a dedicated interface. Agent code cannot directly call arbitrary shell commands.

## Follow-up

Add sandbox safety tests before public demo.

# Artifact Compatibility Policy

PatchSmith persists evidence as local artifacts, so refactors must preserve the
ability to read older runs unless a migration is explicit and tested.

## Transcript JSONL

- Chat transcripts are append-only JSONL files under `artifacts/chat_sessions/`.
- The stable row shape is `event` plus `payload`; `timestamp` and `session_id`
  are preferred for new rows but older rows without them must still feed
  metrics, timelines, resume summaries, and Markdown export.
- Invalid JSON lines are ignored. Dict rows with unknown or malformed event
  shapes are preserved by the raw-row reader and isolated by the typed event
  decoder instead of being silently coerced into known events.
- New transcript events must be additive. Existing event names and payload keys
  that feed metrics, gates, resume, or reports need migration tests before they
  are renamed or removed.

## Complex Benchmark JSON

- `complex_benchmark_results.json` remains a flat list of result rows produced
  by `ComplexBenchmarkResult.to_dict()`.
- Domain evidence views such as `model_usage`, `patch_outcome`, and
  `repair_attempt` are in-memory adapters. They must not appear in the flat
  JSON output without a schema-versioned migration.
- New benchmark fields should have defaults or nullable values so older flat
  rows can still hydrate into `ComplexBenchmarkResult`.
- Use `load_complex_benchmark_results()` for saved result files. It filters
  unknown future keys and normalizes JSON arrays back into tuple-shaped evidence
  fields before constructing result objects.

## Required Evidence

Any persisted-format change should include:

- a focused test with an older/minimal transcript row or benchmark row,
- a current writer test proving the public artifact shape did not gain nested
  internal evidence objects by accident,
- a note in the product refactor plan when the change affects compatibility
  guarantees.

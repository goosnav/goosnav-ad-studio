# Ad Studio development

Start with [STATE.md](STATE.md), then the [harness specification](HARNESS_SPEC.md).
The [implementation roadmap](IMPLEMENTATION_ROADMAP.md) decomposes the work;
the [repository audit](REPOSITORY_AUDIT.md) explains what already exists.

These documents describe the proposed upgrade requested on 2026-10-15. They
are not a claim that a harness, GUI, new audio provider, or recovery system
has been implemented. Commands in the specification are proposed interfaces.

The intended product is a local workspace in which human operators and
tool-using agents make batches of short advertisements. A deterministic
controller owns progression and validation; workers own creative production.

Keep this folder useful to the next implementer:

- Record actual implementation and verification in `STATE.md`.
- Keep interface decisions and acceptance criteria in `HARNESS_SPEC.md`.
- Mark completed roadmap items only after their acceptance checks pass.
- Preserve existing films, the legacy CLI, and uncommitted user edits.
- Keep customer configuration, imported documents, media, weights, generated
  code, transcripts, databases, and run logs out of version control.
- Never describe fake-worker tests as evidence of a real agent or audio run.


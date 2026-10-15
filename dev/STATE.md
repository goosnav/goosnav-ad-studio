# Development state

Updated: 2026-10-15

## Current position

**Design prepared for review; harness implementation has not started.**

Requested outcome: optional concept + brand/source configuration + requested
video count -> a recoverable, agent-operated production workflow -> that many
validated short videos, editable sources, and evidence of review.

Completed discovery:

- Read Ad Studio's CLI, configuration, assembly, audio, voice, QA, playbook,
  and unattended-session launcher.
- Inspected the 3D library's current characters and five-ad example campaign.
- Inspected Frame's settings, export functions, application service and project
  instructions. Frame remains an external integration; it is not being changed.
- Checked installed Codex and Claude command help without starting paid workers.
- Found stale Ad Studio paths: `business/AD STUDIO` is absent; `business/studio`
  contains the source assets, script bank, theory, and outputs.
- Verified the old `assets/textures` directory is absent too; current inputs
  include `assets/images` and the 3D library's textures. Migration needs separate
  roots rather than only a parent-directory rename.
- Confirmed both worker CLIs, Blender and FFmpeg are on PATH. This does not
  establish that worker authentication or quotas are available.
- Identified the current machine as Intel HD Graphics 530, about 62 GiB RAM,
  with no `nvidia-smi` command. No CUDA acceleration has been verified.
- Checked official Hugging Face model cards for audio adapter candidates.

## Next action

Review `HARNESS_SPEC.md`, especially its unattended-operation defaults,
writing workflow, CPU audio strategy and acceptance criteria. After design
approval, turn roadmap slices into executable test-first implementation tasks
and build them in dependency order. Keep implementation and evidence here.

The installed brainstorming workflow requires written-spec approval before
implementation. No application code, local configuration, dependencies, worker
sessions, assets, or external repositories were changed in this design pass.

## Existing work to preserve

- Ad Studio had an uncommitted `PLAYBOOK.md` change before this work.
- The 3D library had an uncommitted README and astronaut/print-related files.
- Frame was clean at inspection. Its own milestone rules govern changes to it.

Do not revert, stage, or commit those unrelated files as part of the harness.
Recheck status before implementing; other agents may have continued working.

## Evidence still required

There are no harness test results yet. Before calling the upgrade complete,
demonstrate the real CLI and GUI, process interruption and resume, provider
failover, local model generation, Frame export, and a real end-to-end batch.
Track synthetic integration tests separately from those demonstrations.

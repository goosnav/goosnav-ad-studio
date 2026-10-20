# Relocatable asset library

`harness.library` reads an asset catalog and prepares isolated, local publication
commits. `push_publication()` then pushes the validated commit and its LFS objects.
Neither operation switches the shared checkout, updates its current branch, or
changes the parent repository's submodule pin. The separate `adopt_publication()`
helper fast-forwards a clean source checkout after a successful push. Configuration
belongs to the controller. `harness.publication.publish_run()` orchestrates commit,
push, adoption and matching parent-pin publication after packaging, persisting
independent outcomes for `./ad publish RUN_ID` retries.

## Controller API

```python
from harness.library import (
    LibraryError, catalog, library_root, snapshot_identities,
    resolve_identity, resolve_snapshot, publish_candidates, push_publication, adopt_publication,
)
from harness.sources import reconcile_sources

warnings = reconcile_sources(config)  # fresh run; persist relocation warnings
entries = catalog(config)
saved_identities = snapshot_identities(config)  # persist in the run state
saved_paths = {entry["id"]: entry["path"] for entry in entries}  # persist separately

# On resume, resolve saved identities BEFORE any basename reconciliation.
# If reloading config, first replay saved character-relocation warnings as the
# controller does, so stale config paths map to this run's saved_paths.
warnings = reconcile_sources(config, identities=saved_identities,
                            identity_paths=saved_paths)
current_entries = resolve_snapshot(config, saved_identities)
current_paths = {entry["id"]: entry["path"] for entry in current_entries}
# Persist refreshed paths/warnings; never substitute a same-basename asset.

# Low-level publication API; the controller supplies the trusted workspace path.
publication = publish_candidates(config, run_workspace / "candidates.json", run_id)
if publication["status"] == "published":
    publication = push_publication(config, publication)
if publication.get("pushed"):
    publication = adopt_publication(config, publication)
# Persist the result, including a pending push's commit/ref, for retry.
```

`snapshot_identities()` snapshots the whole active catalog. Main instead persists
the selected approved character identities initially and adds used assets as
needed, with a separate `{id: absolute_path}` map. `resolve_identity(config, identity)`
resolves one snapshot record; `resolve_snapshot()` resolves a list. Neither chooses
or authorizes cast. Persist old paths and relocation warnings as well as identities
so a reloaded, stale source configuration cannot select a same-named replacement.

`catalog()` returns a list of active entry dictionaries. Each includes `id`,
`kind`, `sha256`, `status`, an absolute resolved `path`, `capabilities` (default
`[]`), and `preview` (an absolute path or `None`). Other catalog metadata survives.
Read operations never rewrite the catalog or configuration. Identity errors raise
`LibraryError`, a subclass of the harness's `ContractError`. Snapshot identities
contain exactly `id`, `kind`, and `sha256`; they contain no machine-specific paths.
Resume resolution fails explicitly if any saved asset is retired, unavailable,
ambiguous, or changed. The controller must invalidate affected plans instead of
silently substituting another asset. This API does not itself modify run state.

```json
{
  "library": {
    "root": "",
    "catalog": "asset-catalog.json",
    "publish": true
  }
}
```

An explicit `root` may name any existing folder. With an empty root, discovery
uses `sources.assets`: roots belonging to the same independent Git repository
coalesce to its Git top-level. Additional non-Git source folders do not compete
with that repository. The application repository is never selected implicitly.
Missing configured subfolders recover through the nearest existing ancestor's
independent Git top-level. `sources.reconcile_sources()` applies the same recovery
to the config and records relocation warnings. Saved identity/hash resolution
precedes catalog-path matching; basename fallback is only for fresh uncataloged
legacy character paths, never a replacement for saved identity. With a catalog,
configured characters missing from it or retired are removed from the authorized
set; an entirely unavailable requested cast fails explicitly. Generic scene/prop
entries do not widen the character whitelist. Missing non-library roots remain errors;
an explicit `library.root` does not suppress those required-source checks.
Multiple independent repositories are ambiguous and require an explicit root.
If no independent Git repository exists, a single configured folder is usable
for catalog reads; multiple folders require an explicit root. With no configured
roots at all, `catalog()` returns `[]`.

The catalog setting is relative to `root`, including when stored in a subfolder.
Catalog entry paths and publication destinations are also relative to **root**,
not to the catalog JSON's containing folder. No model, export, or preview directory
layout is assumed. The config loader should resolve a relative explicit root
against its configuration file; direct API callers resolve it against the current
working directory.

## Catalog schema

```json
{
  "schema_version": 1,
  "entries": [
    {
      "id": "character-astronaut-v1",
      "kind": "character",
      "path": "characters/astronaut.blend",
      "sha256": "<64 lowercase hexadecimal characters>",
      "status": "active",
      "capabilities": ["talk", "walk"],
      "preview": "previews/astronaut.png",
      "preview_sha256": "<64 lowercase hexadecimal characters>",
      "reuse": {
        "description": "Rigged astronaut with reusable talk actions",
        "license": "original"
      }
    }
  ]
}
```

IDs must be unique, 1–128 characters, start with an ASCII letter or digit, and use
only letters, digits, `_`, `.`, `:`, or `-`. Kind is nonempty text. Required entry
fields are `id`, `kind`, `path`, `sha256`, and `status`. `status` is `active` or
`retired`; retired entries remain as tombstones and are never discovered again.
Unknown metadata is preserved. Publication also adds `provenance`, `validation`,
and a top-level `publications` receipt map keyed by run ID.

If an active entry's original file is absent or has a different hash, resolution
searches under the selected root for its SHA-256. Exactly one eligible match is
required. An unchanged file at the recorded path wins even if another copy exists.
Preview relocation uses the same rule when `preview_sha256` is present. Without
a preview hash, the exact preview path must still exist. Hashes refer to file
contents, not Git LFS pointer text; hydrate required active LFS assets before
catalog reads/use.

Hidden directories/files, `archive`, `archives`, and `archived` directories
(case insensitive), and symlinks are excluded from relocation scans. Recorded
active paths reject traversal, absolute paths, backslashes, colon characters,
hidden components, archive components, and symlinks, including aliases inside the
root. This deliberately rejects more than just symlink escapes. A malformed
active entry fails the read; it is not silently dropped.

Without a catalog, `sources.characters` is imported as a transient character
whitelist. Archived characters are omitted. Missing paths fail explicitly; callers
may use source reconciliation first. Other active `.blend` files under the root
are discovered as generic `kind: "scene"` entries, making props and environments
available without directory-name assumptions. Generic entries do not authorize
new cast characters or modify `sources.characters`. They have empty capabilities;
discovery itself does not certify successful Blender loading/rendering. Workers
must inspect them before use. Only `.blend` files are hashed by this discovery;
raw video, exports, archives, hidden files, and symlinks are not read. Unhydrated
LFS files are skipped in optional discovery and fail explicitly if whitelisted.
Legacy IDs are `legacy-<full SHA-256>`, and byte-identical files share one identity,
with whitelist entries taking priority. Once a catalog exists, it is authoritative;
neither the whitelist nor discovery supplements it. To retain old snapshots when
adopting a catalog, retain the generated legacy IDs in its initial entries.

First-catalog **publication bootstrap** has a separate inventory-only rule:
in its clean committed worktree, `_legacy(..., committed_inventory=True)` preserves
active `.blend` entries even when smudge is disabled. A valid canonical LFS pointer's
SHA-256 content OID supplies the hash and `legacy-<hash>` identity, never the hash
of the pointer text. Only configured characters become `kind: "character"`; other
entries remain generic scenes. Archives, hidden paths, symlinks and uncommitted
files stay excluded; malformed/unsupported pointers leave publication pending.
This does not validate or load the missing geometry.

Ordinary uncataloged discovery is unchanged: optional pointers are skipped.
Once the catalog exists, an unhydrated active entry instead fails explicitly with
LFS guidance; it is never silently removed from inventory. In the configured asset
repository, hydrate exact active paths with `git lfs pull --include="<active-paths>"`
and explicit archive exclusions, then retry `catalog(config)` to verify content
hashes. Avoid unrestricted archive downloads. The bootstrap fix does not repair an
already-written incomplete catalog: that needs explicit inventory reconciliation
preserving existing IDs, hashes and retired tombstones.

## Candidate manifest

Place the manifest directly in the **trusted run workspace**. Its parent is the
workspace boundary; the controller must supply the actual run's path, not a path
chosen by an untrusted worker. The run workspace and selected library root must
be separate, non-nested directories. Candidate source paths are relative to that
workspace. Every candidate has an explicit library-relative destination.

```json
{
  "schema_version": 1,
  "run_id": "20261019-example",
  "candidates": [
    {
      "id": "prop-phone-original-v1",
      "kind": "prop",
      "path": "authored/phone.blend",
      "sha256": "<64 lowercase hexadecimal characters>",
      "destination": "props/phone/phone.blend",
      "preview_destination": "previews/phone.png",
      "proxy": false,
      "dependencies": [],
      "provenance": {
        "run_id": "20261019-example",
        "method": "Authored and rigged in this run's Blender scene",
        "sources": []
      },
      "reuse": {
        "description": "Phone prop with screen material and grip origin",
        "license": "original"
      },
      "capabilities": ["handheld", "replaceable-screen"]
    }
  ]
}
```

Required fields are shown above, except `preview_destination` is required only
for `.blend` candidates. `provenance.sources` contains catalog snapshot identities
for reused assets, each revalidated against the current active catalog. An empty
array declares original work. The manifest's and provenance's run IDs must equal
the caller's `run_id`. Candidate bytes must match the declared hash, both before
copying and after copying. Sources and destinations cannot traverse or use
symlinks. Destinations preserve the source extension, cannot overwrite existing
files or collide with other candidates, and cannot replace catalog identities,
including retired IDs. No Git control files or hidden paths may be destinations.
The SHA-256 of retired content also cannot be published under a new ID.

Supported candidate formats:

- **Packed `.blend`:** `tools.blender` runs as a subprocess with factory startup,
  file auto-execution disabled, an execution-error exit code, two threads, and a
  180-second timeout. It opens the actual copied file, rejects external paths and
  linked libraries, rejects objects marked `proxy`/`is_proxy`, requires renderable
  geometry, and renders a 256×256 CPU Cycles preview using a validation camera and
  light. Object, armature, and action names are saved as validation metadata. The
  scene changes exist only in the validator process; the authored file is not
  resaved. A PNG preview and its hash are committed with the asset.
- **PNG/JPEG:** Pillow verifies the image structure. Pillow must be installed.
- **PCM WAV:** the standard library validates the header and complete sample data.
- **Python `.py` rebuild source:** Python compiles the source to validate syntax;
  it never executes the code, imports its dependencies, or writes bytecode. This
  does not certify that running the builder will succeed.
- **JSON `.json` manifests:** the file must parse as JSON. Referenced companion
  assets may be separate candidates in the same manifest; JSON validation does
  not execute or resolve arbitrary paths named inside its contents.
- **GLB `.glb` exports:** validates glTF 2.0 magic/version/length, chunk alignment
  and ordering, embedded JSON asset metadata, and binary buffer lengths. External
  resource URIs are rejected; embedded/data resources are permitted. Binary chunks
  are inspected by length without reading their entire contents into memory. This
  is container/portability validation, not a Blender import/render or a full glTF
  semantic validator. Submit the corresponding `.blend` candidate for a rendered
  preview, and use shared provenance/reuse metadata to identify the bundle.

All candidates require `dependencies: []`: Blender resources must be packed or
made local and GLB resources embedded before submission. Submit builders, portable
exports, and manifests as separate uniquely named candidates in the same run;
they are committed atomically together. Script/runtime dependency execution and
arbitrary external dependency bundles are not supported. Video and other formats
stay pending rather than being copied without validation. Unsupported media can
be added with a corresponding validator.
`proxy:false`, authorship, source completeness, licensing, and reuse descriptions
are worker attestations, not independent proof of originality or legal rights.
Visual quality and the truth of declared capabilities still require the ordinary
asset review. Blender is not an OS sandbox for hostile files.

## Publication lifecycle and retry

`publish_candidates()` returns either:

```json
{
  "status": "published",
  "run_id": "20261019-example",
  "pushed": false,
  "error": "",
  "repository": "/absolute/asset/repository",
  "ref": "refs/heads/asset-publication/<deterministic key>",
  "commit": "<local commit>",
  "base_commit": "<original checked-out commit>",
  "remote": "origin",
  "target_ref": "refs/heads/main",
  "ids": ["prop-phone-original-v1"]
}
```

or `{ "status": "pending", "run_id": "...", "pushed": false, "error": "..." }`.
Persist that result in the run state. Here **published means validated and committed
locally on the returned ref**, not remotely available or visible in the shared
checkout. Disabled publication also returns pending with an explicit reason.

Publishing requires a separate asset Git repository, a configured commit identity,
and a reachable configured upstream branch. A dirty shared checkout is supported:
inherited files, provenance source identities, and the catalog are read exclusively
from the committed tree in a temporary worktree. Staged changes, uncommitted catalog
edits, and untracked environment sets are never incorporated. Candidate destinations
must be absent in both that committed tree and the live checkout, and must still be
absent just before the publication commit. No existing artist work is overwritten.
An explicit library folder inside that repository is supported. The application
repository cannot be used for publication. A detached checkout is acceptable only
when exactly one local tracked branch points at its exact commit. Otherwise
publication remains pending. No branch is guessed from a newer remote tip.

A Git-common-directory advisory lock serializes this library's publishers. Each
attempt creates a temporary detached worktree based on the current checkout's
commit, validates there, stages only candidate files, generated previews, and the
catalog, and checks the source HEAD and destination occupancy again before
committing. Catalog/whitelisted LFS resources are hydrated from already available
local objects; missing objects leave publication pending. Existing Git LFS
attributes are honored using explicit required LFS filters; absent/broken LFS
support leaves publication pending. The module does not invent or alter LFS policy.
Git hooks and commit signing are disabled for this isolated local commit. Existing
repo filters still execute and must be trusted.

The successful commit is retained on a deterministic `asset-publication/` local
branch; the temporary worktree is removed on success or failure. It does not move
the source branch or touch unrelated edits. The receipt records the canonical
manifest hash and base commit. Retrying the same run and manifest returns the same
commit. Reusing the run ID with a changed manifest fails explicitly. If the source
checkout advances independently of the retained commit, retry stays pending for
reconciliation. The manifest and source files must remain available and unchanged
for retries. These branches are durable artifacts; the controller may delete them
after confirming integration. Failures leave no candidate copies in the shared
asset checkout.

`push_publication(config, publication)` also accepts a previous pending push
result. It preserves commit/ref metadata on failure. Before pushing, it verifies
the retained ref, receipt, parent commit, exact changed-file allowlist, asset and
preview hashes, and `git diff --check`. Against the **live remote tip**, the entire
outgoing ancestry must be exactly the approved publication commit, or empty for
an already-pushed retry. Unrelated ahead commits, divergence or an unavailable
ancestor remain pending. The check is repeated immediately before upload/push.
The push uses an explicit `--force-with-lease=<target>:<verified-tip>` as a
compare-and-swap race guard only after proving fast-forward ancestry; it does not
authorize rewriting remote history or shipping unrelated commits.

It uses another isolated temporary worktree and runs
`git submodule update --init --recursive --checkout` before any committed
`make check-layout` target. This checks out recorded nested gitlinks, not newer
remote branch tips, and does not initialize or modify the artist's checkout.
Normal Git URL/protocol restrictions remain in force; no arbitrary transport
allowance is added. Missing credentials, network access or nested commits leave
publication pending. Cleanup removes the owned temporary checkout and its Git
metadata even when ordinary worktree removal refuses initialized submodules;
it never globally prunes worktrees or deinitializes the source submodules.
LFS objects are explicitly uploaded before the guarded Git push, then the remote
tip is verified.
This honors the discovered asset repository's layout-check and LFS requirements;
failure is never silently skipped. It does not run dirty/untracked check scripts.
Its successful result has `status: "published"` and `pushed: true`. Existing
repository Makefiles, `.gitmodules`, and Git/LFS filters must be trusted. Per-format validation
already happened in `publish_candidates`; other repository-specific asset checks
remain the controller's responsibility when relevant.

`adopt_publication(config, publication)` requires `pushed: true`, the same configured
repository, a completely clean checkout (including untracked files/submodule
changes), and a current HEAD that is an ancestor of the published commit. It
checks changed LFS objects in a temporary worktree first, rechecks cleanliness,
and performs `git merge --ff-only --no-overwrite-ignore`, followed by local LFS
hydration. It never rebases, resets, stashes, or discards artist work. Missing local
LFS objects leave adoption pending; it does not fetch them automatically.

Adoption preserves the remote result's `status` and `pushed` fields and adds
`adopted: true`, `adoption_status: "adopted"`, `adoption_error: ""`, and
`checkout_commit` on success. Otherwise it adds `adopted: false`,
`adoption_status: "pending"`, and a descriptive `adoption_error`. Thus remote
publication can succeed while integration waits for the user's refactor. Retry
with this same result after the checkout becomes clean. A filesystem failure after
the fast-forward can leave HEAD advanced but hydration pending; retry completes
hydration without rolling back the checkout.

The implemented controller order is:

1. `harness.publication.publish_run(store, state)` selects a declared
   `candidate_manifest` from a succeeded assets task only when that ad's package
   task succeeded. It uses publication ID `state["id"] + ":" + task["id"]`; the
   manifest/provenance run IDs must match that value. An undeclared manifest is
   rejected. Do not bypass accepted-artifact validation to promote worker files.
2. Create/reuse the local commit with `publish_candidates()`, then call
   `push_publication()` until `pushed: true`. A remote change requiring merge/rebase
   needs explicit reconciliation; helpers never rewrite the retained publication
   branch. Preserve the complete returned receipt on every attempt.
3. Attempt `adopt_publication()` and then `harness.publication.pin_parent(result)`.
   Adoption of the configured external checkout and updating a matching parent
   submodule are independent checks: a dirty external artist checkout may remain
   pending while a separate clean matching submodule can advance safely.
4. Persist results under `state["asset_publications"][task_id]`. Run
   `./ad publish RUN_ID` (or `python3 -m harness publish RUN_ID`) to retry without
   rerendering. `pushed`, `adoption_status`, and `parent_status` distinguish remote
   assets, local availability, and parent publication; do not collapse them into
   one success flag or turn a finished video into a failed render.

`pin_parent()` matches exactly one `.gitmodules` entry by asset remote, verifies
that the asset commit is pushed and its immediate parent is `base_commit`, and
allows only the intended gitlink transition in a clean submodule/otherwise clean
parent. `parent_asset_base` separately records the old parent gitlink, which may
lag `base_commit` but must be its ancestor. `parent_base_commit`, `parent_commit`
and `parent_path` retain the parent operation's receipt for retry. Unrelated
checkout/index changes, ahead commits, ambiguous matches or remote changes remain
pending; the helper does not stash/reset artist edits or include them in a commit.
Parent push uses the same guarded fast-forward principle. A purely external
library has no parent pin unless a matching submodule exists; the current helper
reports a missing/ambiguous match as `parent_status: "pending"`, not as success.

A remote failure, destination collision, ambiguous detached HEAD, unconfigured
branch, missing tool, or failed candidate/check validation remains a retryable
pending result.
Concurrent external editors do not honor this module's advisory lock; the extra
checkout check catches ordinary races but is not a global transaction. No caller
should automatically reset or switch a shared checkout to the returned commit.

## Reported live checkpoint (2026-10-19)

Latest reported asset commit: `c2328b0`, with 70 content-verified records including
4 approved characters and 15 products, excluding archives. Inventory includes the
upstream red mesas/pyramids and nested brain revision `ae51`. Active LFS inventory
was hydrated in the clean checked-in submodule; the dirty artist checkout remains
untouched, with its adoption pending.
These revisions are evidence for that publication checkpoint, not configured
roots, permanent version pins, or proof that the full ad workflow completed.
See [production validation status](production-upgrade-progress.md).

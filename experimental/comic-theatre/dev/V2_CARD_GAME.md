# V2: card-hand conversations — future product rail

Recorded from the owner's 2026-10-21 direction. **Not part of book-v1 implementation.**

## The format

Two characters hold cards and discuss what they have, what they might do, and what
the other character might be planning. Suspense, bluffing, uncertainty and reactions
carry the scene. The viewer can see authentic cards clearly in hand inserts, then
return to wider views of the same characters holding the same cards.

Do not begin with a complete playable card-game simulation. No slapping cards onto
a table, dealing physics, procedural finger grasping or complex exchanges are
required for this format. Stationary hands with expressive heads/faces/voices may
be enough. Any later game-rule simulation is separate from animation.

## What v1 should leave reusable

- Human/optional-writer JSON interface, defaults and deterministic seed resolution.
- Independent character rigs, facial overrides, reactions, local voices and timing.
- Product/edition asset binding, source inserts and readable close-up cameras.
- Rail capability metadata, channel ownership, safe state transitions and tests.
- Checkpointed export and verified per-video delivery.

Do not build a generalized game-rule engine or card implementation into v1 just
to anticipate this. Introduce a new product rail/schema version when the book
engine has demonstrated reliable complete output.

## Card-specific work

1. Author fixed left/right grip sockets and one-, three- and five-card fan poses
   for the supported rig. Restrict hand sizes to those that pass visual tests;
   keep fingers around edges without covering essential art/text.
2. Build a handheld card asset adapter with correct dimensions, thickness, fronts,
   backs, edition IDs and verified card IDs. Original artwork is unchanged.
3. Provide wide, speaker, over-shoulder and square-to-hand insert cameras. Close
   shots must show the same card IDs, order and ownership as wide shots, not an
   unrelated “hero card” image substituted by the editor.
4. Add finite rails such as `cards.hold`, `cards.inspect`, `cards.reveal`,
   `cards.lower`. Holds own arm/hand channels. Reactions still own face/head and
   unreserved motion. Intentional reveals change visibility; random camera angles
   must not leak a hidden card early.
5. Card selection happens before script binding and is saved in resolved JSON.
   Use a seeded shuffle without replacement within the configured deck's actual
   multiplicities. Explicit hands override the shuffle and are validated against
   that same deck. No random change every frame or at each camera cut.
6. A human can specify exact card IDs, or use safe structured references such as
   `reader.hand[0].name` in an authored line template. Rendered dialogue must refer
   to the resolved hand. Never shuffle cards under a literal script that names
   different cards. Reject mismatches detectable from structured references.
7. Optional AI writing receives the already resolved hands and verified rules;
   it cannot silently redeal afterward. In no-agent mode, deterministic authored
   templates/branches can vary the dialogue/outcome with the resolved hands.
   Static JSON dialogue otherwise stays static: randomness alone does not invent
   a coherent different story.
8. Facts about card effects, legality, victory and strategy need the exact rulebook.
   If rules are not implemented/verified, the characters may discuss possible moves
   without claiming a legal game outcome. Do not invent effects or rarity.

## Tentative JSON direction (not yet a v1 field)

```json
{
  "schema": "comic-theatre/cards-v2",
  "product": "verified-card-edition",
  "seed": 42,
  "deal": {"deck": "approved-deck", "hand_size": 3},
  "beats": [
    {"kind": "action", "actor": "reader", "rail": "cards.hold"},
    {"kind": "card_insert", "actor": "reader", "slot": 0, "seconds": 2},
    {"kind": "line", "speaker": "reader",
     "text_template": "I still have {reader.hand[0].name}.",
     "emotion": "dry"}
  ]
}
```

This fragment only illustrates references; cast, other required fields and the
full card schema remain future design work. Template substitution is allowlisted
property lookup, never JavaScript evaluation.

## Acceptance before calling v2 reliable

- Fixed seed, resolved hands and original voices reproduce the same episode.
- Every visible card in every camera matches the saved deal and source hashes.
- No clipping/obscured text at approved grip, pose and camera extremes.
- Dialogue references agree with held cards and any claimed rules.
- Multiple seeds change hands/eligible authored branches without unsupported claims.
- No paid API or AI animator is needed to render; local speech continues to work.
- Interrupted runs retain the same deal and resume verified segments.
- Owner reviews a full tense/funny conversation; a technically correct card fan
  alone is not evidence of an interesting film.

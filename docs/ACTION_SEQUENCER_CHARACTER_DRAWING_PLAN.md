# Action Sequencer Character Drawing Plan

Runtime/PVP scope is defined in
`docs/SPEC_ACTION_SEQUENCER_PVP_RUNTIME.md`. This document focuses on how the
preview should analyze and draw characters for that role-based action system.

## Purpose

This note defines how the external 3D engine link should analyze a character
and decide how to draw it in the Tiger Studio action-sequencer preview.

The goal is not to reproduce arbitrary game logic. The first useful target is:

- read a character actor or character Blueprint,
- identify the visible skeletal character surface,
- identify the animations and action hooks that drive it,
- draw a faithful preview of a two-character action,
- keep the result deterministic enough for AI-driven action layout.

Body-slam and complex paired wrestling moves are intentionally later scope.
The first scope is a strong hit/action pair: character A performs an attack,
character B reacts with a matching hit pose, and the preview shows timing,
spacing, contact, camera, and optional effects.

## Character Analysis Contract

When analyzing a character, collect a structured character descriptor instead
of guessing from the first mesh asset found.

Required fields:

- `actor_path`: selected actor or Blueprint asset path.
- `actor_class`: resolved native or generated class name.
- `mesh_component`: primary visible skeletal mesh component name.
- `skeletal_mesh`: skeletal mesh asset path used by that component.
- `skeleton`: skeleton asset path.
- `animation_blueprint`: animation instance class or asset path when present.
- `materials`: material slot names, material paths, and missing-slot flags.
- `bounds`: local and world bounds for mesh, capsule, and visible children.
- `root_offset`: mesh relative transform under the actor root/capsule.
- `sockets`: important sockets and bones used by combat or attachments.
- `notifies`: animation notify names, frame times, and source animations.
- `montages`: montage paths, section names, blend settings, and play rates.
- `physics_asset`: physics asset path and whether ragdoll can be previewed.
- `tags`: actor tags or gameplay labels useful for choosing actor A/B.
- `diagnostics`: missing assets, unsupported components, and fallback choices.

Do not draw a raw skeletal mesh in isolation when a character Blueprint exists.
The Blueprint may define mesh offset, capsule height, material overrides,
camera-facing defaults, sockets, and montage references. The mesh alone is a
useful fallback, not the preferred source of truth.

## What To Draw

V1 should draw the visible character stack only:

- capsule or root reference as a faint editor guide,
- primary skeletal mesh with material slots,
- selected animation pose or montage playback,
- optional weapon/attachment meshes only when they are direct child components
  or socket-attached assets with resolvable transforms,
- contact markers for attack traces and hit frames,
- simple floor/contact shadow for grounding.

V1 should not try to execute arbitrary Blueprint rendering logic. If a
Blueprint adds unsupported runtime visual behavior, show a diagnostic entry and
fall back to the primary skeletal mesh plus known child components.

## Pose And Motion Sampling

The preview must be pose-driven, not thumbnail-driven.

For each candidate action:

1. Resolve the source animation or montage.
2. Expand montage sections into a timeline.
3. Sample pose bounds at a small number of key times:
   - start,
   - anticipation,
   - contact,
   - follow-through,
   - recovery.
4. Record root motion, pelvis height, foot contact, and hand/weapon contact
   sockets if available.
5. Use notify frames to identify attack traces, combo checks, hit windows, and
   reaction timing.

The preview camera should fit the sampled animated bounds, not only the bind
pose bounds. This avoids cropped limbs and floating characters when an action
extends outside idle stance.

## Two-Character Action Layout

For a two-character action preview, build a paired action descriptor:

- `attacker`: actor descriptor for character A.
- `receiver`: actor descriptor for character B.
- `attacker_action`: attack montage/section or animation.
- `receiver_action`: hit reaction, stagger, knockback, or fallback pose solve.
- `contact_time`: time where the attack should visually connect.
- `contact_socket`: hand, foot, weapon, or trace source bone.
- `receiver_target`: chest, head, pelvis, or nearest supported hit region.
- `spacing`: relative transform from A to B at contact.
- `sync_offset`: receiver animation start offset relative to attacker action.
- `camera_plan`: framing and focal length for preview.
- `effects`: optional impact flash, dust, trail, or hit marker.

## Owner / Target Stage Convention

Use `Owner` and `Target` as the paired-action terminology. `Owner` is the
character that owns and starts the action sequence. `Target` is the controlled
participant affected by that action.

Default V1 stage layout:

- `Owner` starts on the left side of the preview stage.
- `Owner` faces right, like the opening stance in a fighting game.
- `Target`, when present, starts on the right side and faces left.
- The first render-window milestone drew only `Owner`; the current pair-preview
  milestone draws a static `Target` slot on the right so spacing and facing can
  be authored before reaction matching exists.
- `Target` bone transforms are later stored as part of the Owner-owned action
  descriptor, not as a separate competing sequence.

This convention keeps contact solving, camera framing, and action preview
exports deterministic. Mirrored variants can be derived later by flipping the
stage layout after the base action is stable.

If B has a matching hit reaction, use it. If B does not have a matching
reaction, solve a temporary procedural reaction:

- rotate chest/head away from impact direction,
- shift pelvis or root along knockback vector,
- bend knees slightly for heavy impacts,
- apply a short easing curve,
- mark the result as procedural fallback in diagnostics.

## Drawing Quality Rules

Use measured data before artist-like guessing:

- Fit camera from animated world bounds.
- Ground the character by sampled foot or capsule base contact.
- Use mesh component relative transform from the actor.
- Preserve material slot order.
- Show missing materials as neutral gray, not black.
- Keep debug overlays optional and off by default.
- Make contact frames inspectable with a frame step control.

The preview should have two modes:

- `clean`: final-looking character preview with no JSON or debug text.
- `diagnostic`: overlays for skeleton, bounds, sockets, traces, notifies, and
  timing.

## Initial Sample Project Notes

The current sample project at `E:/ue5example/ActionSequencer` is suitable for
V1 because it already contains:

- a runtime character module,
- combat player and enemy character classes,
- attacker and damageable interfaces,
- combo and charged attack montage hooks,
- attack trace animation notifies,
- damage, knockback, partial ragdoll, and death behavior,
- unarmed attack animations,
- rifle hit-reaction animations,
- death animations.

Good first action candidate:

- attacker: unarmed attack animation or combo montage section,
- receiver: front heavy hit reaction,
- layout: attacker in front of receiver, contact aligned to attack notify,
- fallback: if hit reaction is unavailable, procedural chest/head recoil.

Body-slam should wait until the basic two-character action pair is reliable.
It requires matched grab/contact constraints, root-motion alignment, receiver
lift/fall pose solving, and likely authored paired animation data.

## MCP Toolset Shape

The engine MCP connection is usable when launched on a free port such as
`8765`. The default `8000` can fail to bind on this machine, so do not hardcode
that port in tests or tools.

The built-in MCP server currently exposes only meta tools unless a project
toolset is registered. Therefore the action sequencer needs a project toolset
with a small, explicit API.

Recommended first toolset:

- `list_character_candidates`
  - returns actors, Blueprint assets, skeletal meshes, and confidence scores.
- `inspect_character`
  - returns the character descriptor described above.
- `list_action_candidates`
  - returns montages, animations, notifies, sections, and likely action roles.
- `inspect_action`
  - returns sampled timing, bounds, contact frames, sockets, and root motion.
- `preview_action_pair`
  - returns a deterministic preview plan and optional screenshot path.

Recommended later tools:

- `create_action_clip`
- `apply_action_pair_to_sequence`
- `bake_contact_markers`
- `export_action_preview`

## Acceptance Criteria

V1 is good enough when:

- the tool can identify the primary visible skeletal mesh from a character
  Blueprint,
- material slots and mesh offsets are preserved,
- an attack animation can be paired with a hit reaction,
- camera framing is based on sampled animated bounds,
- contact timing is derived from notifies or sampled motion,
- unsupported Blueprint behavior produces a diagnostic instead of a broken
  preview,
- the same character/action pair produces the same preview plan every time.

## Explicit Non-Goals For V1

- arbitrary Blueprint graph rendering,
- full gameplay simulation,
- multiplayer or network state,
- complex throw/grab moves,
- physics-authored cinematic ragdoll,
- full level-sequence authoring UI,
- replacement for the external engine editor.

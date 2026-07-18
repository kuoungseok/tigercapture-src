# Action Sequencer PVP Runtime Spec

## Purpose

Action Sequencer is a runtime combat-action authoring surface for Unreal-facing
game workflows. It is not a replacement for Level Sequencer. Its first product
shape is a reusable, role-based action template:

> Actor A performs an action against Actor B.

Both actors are runtime bindings, not fixed preview meshes. The same action
asset should be reusable for players, NPCs, bosses, and PVP opponents when their
skeleton family and role requirements match.

Korean product wording:

> PVP에서도 쓸 수 있는 역할 기반 전투 액션 시퀀서.

## Terminology

Use simple role terms in the UI:

- `Actor A`: the visible role that starts the action.
- `Actor B`: the visible role affected by the action.

Use more explicit technical terms in code and asset schemas:

- `Performer`: the role that owns and plays the primary action.
- `Target`: the role receiving the action.
- `Instigator`: the gameplay authority source, especially in Unreal or network
  code.

Avoid using `slave` terminology. If a paired-action UI needs directional names,
prefer `Performer / Target` or `Actor A / Actor B`.

## Product Boundary

Level Sequencer is strong for fixed cinematic scenes bound to concrete actors in
a concrete level. Action Sequencer should instead be strong at short gameplay
actions that can run during combat:

- grabs,
- counters,
- hit reactions,
- finishers,
- ultimate skill cut-ins,
- paired melee actions,
- weapon execution moves,
- cooperative attacks,
- PVP stun/counter/impact moments.

The tool should author a reusable action package that can be bound at runtime,
not a one-off movie timeline.

## PVP Design Rule

If the design works for PVP, it will usually work for PVE. Therefore V1 should
be planned against this rule:

> The server decides gameplay truth; each client plays a safe presentation.

Server-authoritative state:

- action activation permission,
- target resolution,
- distance and angle validation,
- hit confirmation,
- damage,
- state changes,
- knockback or forced movement,
- cancel and interrupt rules,
- invulnerability, armor, dodge, and guard windows.

Client-side presentation:

- camera cuts and shakes,
- Niagara effects,
- bloom, exposure, color, vignette, DOF, and other post process blends,
- cut-in overlays,
- local hit flashes,
- audio and voice cues,
- target reaction interpolation,
- IK and bone correction used only for visual alignment.

PVP actions must not depend on client-only presentation to determine damage or
state changes.

## Action Asset Shape

An Action Sequencer asset stores role requirements and time-based tracks. It
must not store a hard reference to one specific player character as the only
valid user.

Recommended top-level fields:

- `id`
- `version`
- `compatible_skeleton_families`
- `roles`
- `tracks`
- `markers`
- `network_policy`
- `runtime_safety`
- `diagnostics`

Example:

```json
{
  "id": "body_slam_v1",
  "version": 1,
  "roles": {
    "performer": {
      "display_name": "Actor A",
      "skeleton_family": "UE_Mannequin_Compatible",
      "animation": "/Game/Actions/BodySlam_A"
    },
    "target": {
      "display_name": "Actor B",
      "skeleton_family": "UE_Mannequin_Compatible",
      "reaction": "/Game/Actions/BodySlam_Target",
      "fallback_pose_track": true
    }
  },
  "markers": {
    "start": 0.0,
    "approach": 0.15,
    "grab": 0.42,
    "impact": 0.88,
    "recover": 1.25,
    "end": 1.45
  },
  "events": [
    {
      "time": 0.42,
      "type": "attach",
      "source": "performer.hand_r",
      "target": "target.spine_03"
    },
    {
      "time": 0.88,
      "type": "gameplay_hit",
      "authority": "server"
    },
    {
      "time": 0.88,
      "type": "niagara",
      "asset": "/Game/VFX/ImpactBurst",
      "bind": "contact_point"
    }
  ]
}
```

## Required Tracks

### Actor Track

Defines role slots, preview meshes, skeleton compatibility, facing direction,
and stage position.

V1 convention:

- `Actor A` starts left.
- `Actor A` faces right, like a fighting-game opening stance.
- `Actor B`, when present, starts right and faces left.
- Preview characters are sample bindings only. Saved action data is role-based.

### Animation Track

Stores performer animation, target reaction animation, montage section, play
rate, root motion policy, and start offset.

When a target has no matching reaction animation, V1 may use a procedural
fallback pose track and must mark that fallback in diagnostics.

### Alignment Track

Controls relative transform between roles:

- contact distance,
- facing angle,
- root offset,
- motion-warp target,
- contact marker alignment,
- optional snap or blend-in policy.

This is critical because runtime Actor A and Actor B can be different character
instances.

### Contact / Hit Track

Defines contact markers, hit frames, damage windows, block/parry windows,
cancel windows, and hit-stop timing. Gameplay-affecting events must be
server-authoritative in PVP.

### IK / Bone Correction Track

Defines visual-only correction for:

- hands gripping a target,
- feet staying grounded,
- pelvis or chest recoil,
- head/chest aim,
- weapon contact,
- target body alignment during paired actions.

This track is allowed to improve presentation, but it must not replace server
collision or gameplay authority.

### Niagara Track

Niagara events must bind to role slots and semantic markers rather than one
fixed world-space location.

Supported V1 spawn bindings:

- performer socket,
- target socket,
- contact point,
- ground impact point,
- between Actor A and Actor B,
- target-relative offset,
- camera-space or screen-space effect.

Useful user parameters:

- performer position,
- target position,
- contact normal,
- impact direction,
- weapon type,
- damage type,
- speed,
- camera direction.

### Camera Track

Defines short runtime camera presentation:

- lock-on camera,
- zoom,
- cut-in,
- shake,
- target-relative orbit,
- return-to-gameplay blend.

PVP camera changes must be bounded and should have remote-player and spectator
policies.

### Post Process Track

Defines time-based blend curves for:

- exposure,
- bloom,
- vignette,
- color tint,
- contrast,
- saturation,
- chromatic aberration,
- depth of field,
- motion blur,
- hit flash.

Rules:

- Every value must have blend-in and blend-out.
- Cancel or interrupt must restore the previous state.
- Low-spec mode may scale or disable expensive presentation.
- PVP may show different post effects to the performer, target, and spectators.

### Audio Track

Defines voice, hit, whoosh, impact, UI sting, environmental response, and
optional camera cut-in sound. Audio can be local-only, but hit-confirm audio
should follow authoritative game events.

### Cut-In / Overlay Track

Optional track for Super Robot Wars-style presentation:

- character portrait,
- manga-panel slash,
- skill name typography,
- screen-space particles,
- short overlay animation.

This track should be duration-limited for live gameplay.

### Gameplay Event Track

Defines gameplay signals:

- ability commit,
- damage apply,
- hit-stop,
- input lock,
- movement lock,
- invulnerable window,
- cancel window,
- combo branch window,
- gameplay cue trigger.

In PVP these events are data for server/client synchronization, not merely
editor decorations.

## Duration Policy

Recommended live-gameplay lengths:

- normal skill: `0.3s - 0.8s`
- heavy attack or counter: `0.8s - 1.5s`
- grab or execution: `1.2s - 2.5s`
- ultimate or finisher cut-in: `2.5s - 5.0s`

Longer sequences require stronger policy:

- skip or abbreviate option,
- remote-player shortened presentation,
- spectator/replay full presentation,
- server-confirmed gameplay result before local flourish,
- guaranteed camera and post-process restore.

## Runtime Binding Flow

Recommended runtime flow:

1. Game selects an action asset.
2. Server validates performer, target, distance, facing, state, and cooldown.
3. Server confirms action start and gameplay timeline anchors.
4. Each client binds runtime Actor A/B to the role slots.
5. Skeleton compatibility and role requirements are checked.
6. Animation, motion warp, IK, Niagara, camera, post process, and audio tracks
   are prepared.
7. Gameplay events follow authoritative time anchors.
8. Presentation runs locally with safe cancellation and restore behavior.
9. On cancel, interrupt, death, disconnect, or target invalidation, the action
   falls back to the configured safety policy.

## Runtime Safety

Each action asset must define failure behavior:

- missing animation,
- incompatible skeleton,
- target disappeared,
- target died,
- performer died,
- action interrupted,
- network correction,
- camera blocked,
- low-spec presentation fallback,
- Niagara asset missing,
- post-process restore failure.

The default should be a diagnostic and a safe visual fallback, not a crash or a
stuck camera.

## V1 Scope

V1 should be deliberately narrow:

- UE mannequin-compatible skeleton family first.
- One performer and one target.
- Owner-only preview remains valid as an initial milestone.
- Two-role preview follows after single-role animation playback is reliable.
- Animation selection should play immediately and reset to the first frame when
  selected.
- Basic alignment markers.
- Basic contact and hit markers.
- Basic Niagara events.
- Basic camera cuts.
- Basic post-process blend curves.
- JSON or Unreal-facing descriptor export.

V1 should not attempt:

- arbitrary Blueprint graph simulation,
- full Level Sequencer replacement,
- fully automatic retargeting for every skeleton,
- multiple targets,
- complex physics-authored throws,
- complete network prediction,
- full game-mode simulation.

## Implementation Notes For Tiger Studio

The current Tiger Studio preview work should be treated as an authoring and
inspection surface. Unreal remains the runtime target.

## Automation Direction

Other production tools and engines do not expect animators to rotate every bone
on every frame for paired actions. The practical pattern is:

1. Start from an authored base animation.
2. Pick or recommend a close target reaction.
3. Align root motion and contact markers.
4. Add temporary constraints and IK.
5. Bake or export compact curves and markers for runtime playback.

Tiger Studio should follow that model instead of becoming a frame-by-frame bone
posing tool.

Recommended automation tools:

- `Reaction Base Finder`: scans target animations and recommends likely
  reaction bases using name, duration, direction, strength, and pose metadata.
- `Sync Marker Solver`: aligns performer contact markers with target reaction
  markers such as grab, lift, impact, ground contact, and recovery.
- `Target Root Warp`: creates target root/pelvis transform curves so throws,
  knockdowns, and grabs can move the whole target through space instead of only
  bending bones.
- `Constraint Layer`: pins hands, weapons, torso, feet, or contact points over
  a time range without destructively editing the source animation.
- `IK Polish`: applies focused pelvis, spine, head, arm, and leg correction on
  top of the reaction base.
- `Bake / Export`: stores the result as animation references, marker curves,
  root offsets, constraints, and diagnostics rather than a giant hand-authored
  per-bone-per-frame blob.

V1 UI flow:

1. Select Actor A action animation.
2. Auto-list Actor B reaction candidates.
3. Click a candidate to preview paired timing.
4. Adjust contact frame, target root offset, pelvis/spine/head correction, and
   optional hand/foot pins.
5. Save the non-destructive correction layer.

Near-term implementation order:

1. Make the owner-only AR/PBR preview stable, fast, and correct.
2. Add Actor B as a visible right-side role slot facing Actor A. Current V1
   implementation uses an AR/PBR stage-pair descriptor that duplicates the
   performer mesh into a static target slot for composition only.
3. List owner-compatible animation sequences without per-click slow exports.
4. Play selected owner animation immediately in the preview.
5. Add target reaction animation selection.
6. Add contact marker authoring.
7. Add relative alignment authoring.
8. Add Niagara event track.
9. Add camera track.
10. Add post-process blend track.
11. Add gameplay event markers and runtime export schema.

Do not let the authoring UI become a full Unreal editor clone. The value is in
focused action authoring, preview, diagnostics, and exportable runtime data.

## Acceptance Criteria

The PVP-runtime spec is credible when:

- Actor A/B are clearly role slots.
- Runtime characters can be swapped within a compatible skeleton family.
- Gameplay authority and local presentation are separated.
- Action preview can show animation, contact, camera, VFX, post process, and
  audio as tracks.
- Every presentation effect has restore behavior.
- Missing assets produce diagnostics rather than broken output.
- The same action asset can be used by a player, NPC, or PVP opponent when
  bindings match.

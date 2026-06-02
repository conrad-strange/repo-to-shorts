# Architecture

```text
GitHub URL / Local Path
        |
        v
Repo Reader Agent
        |
        v
Project Understanding Agent
        |
        v
Script Writer Agent
        |
        v
Storyboard Agent
        |
        v
Verifier Agent
        |
        v
Visual Spec Builder
        |
        v
TTS + Timing
        |
        v
Remotion Renderer
        |
        v
9:16 MP4
```

The MVP keeps agents as typed workflow steps instead of introducing a heavy multi-agent runtime. Each step reads and writes Pydantic models so that the system remains easy to debug and extend.

## Model Strategy

The first implementation should prefer one LLM provider to reduce setup friction for users.

- Strong reasoning model: project understanding and verification.
- Smaller generation model: script and storyboard.
- No LLM: repo reading, visual mapping, rendering.

TTS is treated separately from LLM generation. The default MVP provider can be Edge TTS, with API-based TTS added as an optional quality upgrade.

## Renderer Strategy

The current renderer uses Remotion as the main timeline owner. Remotion is responsible for:

- global duration and frame count
- audio playback
- scene sequencing
- final MP4 render
- 9:16 output constraints

The MVP now keeps a single render path: Remotion owns the full timeline and all scene templates. This reduces setup friction and keeps every frame deterministic.

## Micro Beats

Storyboard scenes now include `visual.micro_beats`. A scene is still the main narrative unit, but each scene can contain 2-4 smaller visual beats:

- short text cards
- flow nodes
- code or command beats
- stack tags
- CTA beats

Remotion uses these beats for staggered entrance timing inside each scene. This avoids static PPT-like pages while keeping the video deterministic and easy to evaluate.

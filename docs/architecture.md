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
HyperFrames Enhancement Layer
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

The HyperFrames layer is intentionally local and partial in the MVP. `hyperframes-lite` generates HTML scene assets for high-impact scenes such as the first hook scene, writes a manifest to `logs/hyperframes-manifest.json`, and lets Remotion embed that scene in the main timeline.

This keeps the working video pipeline stable while leaving a narrow adapter for the real HyperFrames CLI later. When the CLI path is available, `HYPERFRAMES_CMD` can be used to switch the adapter from embedded HTML to pre-rendered scene clips.

## Micro Beats

Storyboard scenes now include `visual.micro_beats`. A scene is still the main narrative unit, but each scene can contain 2-4 smaller visual beats:

- short text cards
- flow nodes
- code or command beats
- stack tags
- CTA beats

Remotion uses these beats for staggered entrance timing inside each scene. This avoids static PPT-like pages while keeping the video deterministic and easy to evaluate. HyperFrames-lite uses the same beat data for the enhanced hook HTML.

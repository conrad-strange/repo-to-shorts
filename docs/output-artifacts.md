# Output Artifacts

Each run writes useful intermediate artifacts so generation errors can be traced.

## Root Output Files

- `repo-summary.json`: deterministic repository scan result.
- `project-insight.json`: LLM-generated project understanding.
- `video-script.json`: structured Chinese narration script.
- `script.md`: human-readable narration script.
- `storyboard.json`: LLM-generated visual storyboard before TTS timing.
- `storyboard-timed.json`: storyboard adjusted from measured TTS audio duration.
- `workflow-metadata.json`: high-level run metadata and next pipeline step.
- `videos/latest/video.mp4`: latest rendered vertical video.

## Logs

- `logs/tts-input.json`: exact text submitted to TTS for every scene.
- `logs/tts-manifest.json`: generated audio paths, measured durations, and adjusted scene durations.
- `logs/timing-adjustment.json`: before/after total duration and timing method.

## Audio

- `audio/scenes/*.mp3`: per-scene narration audio.
- `audio/voice.mp3`: combined narration track for the final video.

The current MVP combines scene MP3 files directly. A later render phase should prefer FFmpeg concat when FFmpeg is configured.

## Video Versioning

The current CLI writes the newest rendered video to:

```text
outputs/<project>/videos/latest/video.mp4
```

For a future web UI, keep `latest` as a convenience pointer and create immutable run folders:

```text
outputs/<project>/videos/
  latest/
  20260530-183910-short/
  20260530-190205-style-test/
```

Each run folder should eventually contain its own `video.mp4`, preview image, render metadata, and evaluation report so users can compare versions instead of overwriting history.

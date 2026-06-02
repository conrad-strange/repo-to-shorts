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
- `video.mp4`: rendered vertical video for this immutable run.

## Logs

- `logs/tts-input.json`: exact text submitted to TTS for every scene.
- `logs/tts-manifest.json`: generated audio paths, measured durations, and adjusted scene durations.
- `logs/timing-adjustment.json`: before/after total duration and timing method.

## Audio

- `audio/scenes/*.mp3`: per-scene narration audio.
- `audio/voice.mp3`: combined narration track for the final video.

The current MVP combines scene MP3 files directly. A later render phase should prefer FFmpeg concat when FFmpeg is configured.

## Video Versioning

The current CLI writes each rendered video into its run folder:

```text
outputs/<project>/runs/<run_id>/video.mp4
```

Run folders are immutable by default so users can compare versions:

```text
outputs/<project>/runs/
  0001/
    video.mp4
  0002/
    video.mp4
```
Each run folder should contain its own `video.mp4`, preview image, render metadata, and evaluation report.

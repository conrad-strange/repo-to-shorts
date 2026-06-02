# Current MVP Status

## Minimal Closed Loop

The current pipeline can generate a complete vertical video from a public GitHub repository:

```text
GitHub URL
-> clone/cache repo
-> Repo Reader
-> Project Understanding Agent
-> Script Writer Agent
-> Storyboard Agent
-> Edge TTS
-> TTS timing adjustment
-> Remotion render
-> Rule-based evaluation
```

Using `https://github.com/conrad-strange/rag-demo`, the pipeline currently produces:

- `repo-summary.json`
- `project-insight.json`
- `video-script.json`
- `script.md`
- `storyboard.json`
- `storyboard-timed.json`
- `audio/voice.mp3`
- `video.mp4`
- `evaluation-report.json`
- `evaluation-report.md`

The current video is 42.35 seconds, 1080x1920, 9:16, 30fps, with an AAC audio track. The rule-based evaluation score is 100.

## What Is Still Missing

- Visual quality is improved for the hook scene, but the rest of the Remotion scene templates are still basic.
- Verifier Agent is still not fully implemented. We have evidence fields, but no strict claim checking yet.
- Evaluation is rule-based only. It checks artifacts, timing, aspect ratio, audio, and basic scene structure, but does not judge narrative quality or visual taste.
- Repo analysis is still mostly heuristic. It does not yet use embeddings, code symbol extraction, or Tree-sitter.
- Audio concatenation is still simple. It works for MVP, but FFmpeg concat should replace byte concatenation.
- UI is not started. The tool is currently CLI-first.
- Renderer has only a small set of simple scene layouts beyond the enhanced hook.

## Recommended Priority

1. Regenerate for mobile-short pacing.
   The default script/storyboard prompts now target 30-45 seconds, require a hook scene, and use faster TTS. Existing cached outputs need to be regenerated to benefit from this.

2. Improve Remotion visual templates.
   The pipeline already works, so the next biggest product leap is making the generated video feel polished: better typography, scene layouts, code cards, flow diagrams, subtle motion, and consistent spacing.

3. Add Verifier Agent.
   After visuals improve, add a strong LLM-based verifier that checks script and storyboard claims against repo evidence.

4. Improve TTS and audio handling.
   Replace direct MP3 byte concatenation with FFmpeg concat, add optional voice choices, and produce subtitle timing.

5. Add LLM Evaluator later.
   Once visuals are mature, add an LLM evaluator for narrative quality, pacing, and style fit. It should complement the current rule-based evaluator, not replace it.

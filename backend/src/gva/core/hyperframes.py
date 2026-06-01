from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from gva.models.storyboard import Scene, Storyboard


def prepare_hyperframes_scene_assets(
    output_dir: Path,
    renderer_dir: Path,
    storyboard: Storyboard,
    render_strategy: str = "remotion-primary",
) -> Storyboard:
    """Prepare deterministic HTML scene assets for the HyperFrames enhancement layer.

    remotion-primary: Remotion owns most scenes and HyperFrames-lite enhances the hook.
    hyperframes-primary: HyperFrames-lite owns every scene while Remotion remains the
    timeline, audio and encoding shell.
    """
    enhanced = storyboard.model_copy(deep=True)
    for scene in enhanced.scenes:
        scene.visual.enhanced_html = None
        scene.visual.enhanced_by = None

    scenes_to_enhance = _select_scenes(enhanced, render_strategy)
    manifest = {
        "enhancer": "hyperframes-lite",
        "mode": render_strategy,
        "scene_assets": [],
    }

    if not scenes_to_enhance:
        _write_manifest(output_dir, manifest)
        return enhanced

    output_asset_dir = output_dir / "render-assets" / "hyperframes"
    renderer_asset_dir = renderer_dir / "public" / "generated" / "hyperframes"
    output_asset_dir.mkdir(parents=True, exist_ok=True)
    renderer_asset_dir.mkdir(parents=True, exist_ok=True)

    for scene in scenes_to_enhance:
        html_filename = f"{scene.id}.html"
        html_text = _render_scene_html(scene)
        output_html_path = output_asset_dir / html_filename
        renderer_html_path = renderer_asset_dir / html_filename
        output_html_path.write_text(html_text, encoding="utf-8")
        shutil.copyfile(output_html_path, renderer_html_path)

        scene.visual.enhanced_html = f"generated/hyperframes/{html_filename}"
        scene.visual.enhanced_by = "hyperframes-lite"
        manifest["scene_assets"].append(
            {
                "scene_id": scene.id,
                "layout": scene.visual.layout,
                "output_html_path": str(output_html_path),
                "renderer_html_path": str(renderer_html_path),
                "public_src": scene.visual.enhanced_html,
            }
        )

    _write_manifest(output_dir, manifest)
    return enhanced


def _select_scenes(storyboard: Storyboard, render_strategy: str) -> list[Scene]:
    if render_strategy.strip().lower() == "hyperframes-primary":
        return storyboard.scenes

    for scene in storyboard.scenes:
        if scene.visual.layout == "hook":
            return [scene]
    return storyboard.scenes[:1]


def _write_manifest(output_dir: Path, manifest: dict) -> None:
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "hyperframes-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_scene_html(scene: Scene) -> str:
    accent = scene.visual.accent_color or "#111827"
    headline = html.escape(scene.visual.headline)
    lead = html.escape(scene.visual.caption or _truncate_text(scene.narration, 34))
    beat_texts = [beat.text for beat in scene.visual.micro_beats[:4]] or scene.visual.bullets[:4]
    bullets = [html.escape(item) for item in beat_texts]
    bullet_html = "" if scene.visual.layout == "flow" else "".join(f"<li>{item}</li>" for item in bullets)
    nodes = scene.visual.diagram_nodes[:5] or beat_texts[:5]
    node_html = "".join(f"<span>{html.escape(node)}</span>" for node in nodes)
    code = html.escape(scene.visual.code or (beat_texts[0] if scene.visual.layout == "code" and beat_texts else ""))
    layout_class = html.escape(scene.visual.layout)
    kicker = html.escape(_layout_label(scene.visual.layout))
    duration = f"{max(1, round(scene.duration))}s"
    flow_block = f'<div class="flow">{node_html}</div>' if scene.visual.layout == "flow" else ""
    code_block = f'<div class="terminal">$ {code}</div>' if scene.visual.layout == "code" and code else ""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{
      --accent: {accent};
      --ink: #111111;
      --muted: #6e6e73;
      --line: #d9d9df;
      --paper: #f7f7f5;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      width: 1080px;
      height: 1920px;
      margin: 0;
      overflow: hidden;
      background: var(--paper);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
    }}
    .stage {{
      position: relative;
      width: 1080px;
      height: 1920px;
      padding: 172px 92px 104px;
      isolation: isolate;
    }}
    .grid {{
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, rgba(17,17,17,0.045) 1px, transparent 1px),
        linear-gradient(rgba(17,17,17,0.045) 1px, transparent 1px);
      background-size: 120px 120px;
      mask-image: radial-gradient(circle at 50% 36%, black, transparent 72%);
      opacity: 0.72;
      z-index: -2;
    }}
    .focus {{
      position: absolute;
      left: 86px;
      top: 138px;
      width: 8px;
      height: 0;
      border-radius: 99px;
      background: var(--accent);
      animation: barIn 0.5s cubic-bezier(.2,.8,.2,1) forwards;
    }}
    .kicker {{
      display: inline-flex;
      align-items: center;
      gap: 16px;
      height: 52px;
      padding: 0 22px;
      border: 1px solid rgba(17,17,17,0.13);
      border-radius: 999px;
      background: rgba(255,255,255,0.62);
      color: var(--muted);
      font-size: 28px;
      letter-spacing: 0;
      opacity: 0.45;
      transform: translateY(18px);
      animation: rise 0.34s cubic-bezier(.2,.8,.2,1) 0s forwards;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--accent);
    }}
    h1 {{
      width: 880px;
      margin: 126px 0 0;
      font-size: 106px;
      line-height: 1.02;
      letter-spacing: 0;
      font-weight: 760;
      text-wrap: balance;
      opacity: 0.38;
      transform: translateY(30px) scale(0.985);
      animation: titleIn 0.38s cubic-bezier(.2,.8,.2,1) 0.02s forwards;
    }}
    .hook h1 {{
      font-size: 118px;
      margin-top: 146px;
    }}
    .lead {{
      width: 820px;
      margin-top: 48px;
      color: var(--muted);
      font-size: 34px;
      line-height: 1.36;
      letter-spacing: 0;
      opacity: 0.22;
      transform: translateY(22px);
      animation: rise 0.34s cubic-bezier(.2,.8,.2,1) 0.12s forwards;
    }}
    .panel {{
      position: absolute;
      left: 92px;
      right: 92px;
      bottom: 148px;
      min-height: 312px;
      border: 1px solid rgba(17,17,17,0.1);
      border-radius: 8px;
      background: rgba(255,255,255,0.82);
      box-shadow: 0 34px 90px rgba(0,0,0,0.08);
      padding: 38px 42px;
      opacity: 0.18;
      transform: translateY(34px);
      animation: panelIn 0.36s cubic-bezier(.2,.8,.2,1) 0.22s forwards;
    }}
    .panel-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 30px;
      color: var(--muted);
      font-size: 24px;
    }}
    ul {{
      margin: 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 16px;
      color: #262628;
      font-size: 32px;
      line-height: 1.28;
    }}
    li::before {{
      content: "";
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 14px;
      border-radius: 50%;
      background: var(--accent);
      vertical-align: 8%;
    }}
    .flow {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}
    .flow span {{
      min-height: 82px;
      display: flex;
      align-items: center;
      padding: 0 22px;
      border: 1px solid rgba(17,17,17,0.12);
      border-radius: 8px;
      background: #fff;
      color: #171717;
      font-size: 26px;
      font-weight: 640;
    }}
    .terminal {{
      margin-top: 22px;
      border-radius: 8px;
      background: #111;
      color: #f8fafc;
      padding: 26px 28px;
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 30px;
      line-height: 1.34;
      word-break: break-word;
    }}
    .mini-code {{
      display: grid;
      gap: 16px;
      margin-top: 26px;
    }}
    .mini-code span {{
      display: block;
      height: 20px;
      border-radius: 999px;
      background: #d6d6da;
      transform-origin: left center;
      animation: linePulse 1.45s ease-in-out infinite;
    }}
    .mini-code span:nth-child(1) {{ width: 78%; background: var(--accent); animation-delay: 0s; }}
    .mini-code span:nth-child(2) {{ width: 54%; animation-delay: .14s; }}
    .mini-code span:nth-child(3) {{ width: 88%; animation-delay: .28s; }}
    @keyframes barIn {{ to {{ height: 514px; }} }}
    @keyframes rise {{ to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes titleIn {{ to {{ opacity: 1; transform: translateY(0) scale(1); }} }}
    @keyframes panelIn {{ to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes linePulse {{
      0%, 100% {{ transform: scaleX(.92); opacity: .72; }}
      50% {{ transform: scaleX(1); opacity: 1; }}
    }}
  </style>
</head>
<body>
  <main id="root" class="stage {layout_class}" data-composition-id="root" data-start="0" data-width="1080" data-height="1920">
    <div class="grid"></div>
    <div class="focus"></div>
    <div id="kicker" class="kicker clip" data-start="0" data-duration="{scene.duration:.2f}" data-track-index="1"><span class="dot"></span>{kicker}</div>
    <h1 id="headline" class="clip" data-start="0" data-duration="{scene.duration:.2f}" data-track-index="2">{headline}</h1>
    <p id="lead" class="lead clip" data-start="0.25" data-duration="{max(scene.duration - 0.25, 0.5):.2f}" data-track-index="3">{lead}</p>
    <section id="panel" class="panel clip" data-start="0.45" data-duration="{max(scene.duration - 0.45, 0.5):.2f}" data-track-index="4">
      <div class="panel-top">
        <span>{html.escape(duration)}</span>
        <span>快速看懂</span>
      </div>
      <ul>{bullet_html}</ul>
      {flow_block}
      {code_block}
      <div class="mini-code" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _layout_label(layout: str) -> str:
    return {
        "hook": "开场钩子 / GitHub Repo",
        "title": "项目承诺 / Project",
        "text": "关键解释 / Why",
        "stack": "技术栈 / Stack",
        "flow": "核心流程 / Flow",
        "code": "运行方式 / Run",
        "steps": "使用步骤 / Steps",
        "cta": "结尾行动 / CTA",
    }.get(layout, "项目讲解 / GitHub Repo")


def _truncate_text(text: str, max_chars: int) -> str:
    compact = "".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars]}..."

import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveAccent, theme} from '../styles/theme';
import type {MicroBeat, Scene} from '../types';

const layoutLabel: Record<string, string> = {
  title: '项目承诺',
  text: '关键解释',
  stack: '技术栈',
  flow: '核心流程',
  code: '运行方式',
  steps: '使用步骤',
  cta: '下一步',
};

export const TextScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = resolveAccent(scene.visual.accent_color);
  const beats = getBeats(scene);
  const progress = interpolate(
    frame,
    [0, Math.max(1, scene.duration * fps - 1)],
    [0, 1],
    {extrapolateRight: 'clamp'}
  );
  const titleY = interpolate(frame, [0, 8], [18, 0], {extrapolateRight: 'clamp'});
  const titleOpacity = interpolate(frame, [0, 6], [0.42, 1], {extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.background,
        color: theme.foreground,
        fontFamily: theme.fontFamily,
        overflow: 'hidden',
      }}
    >
      <BackgroundGrid accent={accent} />
      <div
        style={{
          position: 'absolute',
          left: 88,
          right: 88,
          top: 92,
          height: 6,
          borderRadius: 999,
          background: 'rgba(240,246,252,0.08)',
        }}
      >
        <div
          style={{
            width: `${progress * 100}%`,
            height: '100%',
            borderRadius: 999,
            background: accent,
          }}
        />
      </div>

      <div style={{position: 'absolute', left: 88, right: 88, top: 142}}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 14,
            height: 48,
            padding: '0 20px',
            border: `1px solid ${theme.border}`,
            borderRadius: 999,
            background: 'rgba(22,27,34,0.72)',
            color: theme.muted,
            fontSize: 26,
          }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: 999,
              background: accent,
            }}
          />
          {layoutLabel[scene.visual.layout] || '项目讲解'}
        </div>

        <div
          style={{
            width: 880,
            marginTop: 88,
            fontSize: scene.visual.layout === 'title' ? 88 : 76,
            fontWeight: 760,
            lineHeight: 1.04,
            letterSpacing: 0,
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
          }}
        >
          {scene.visual.headline}
        </div>
      </div>

      <div style={{position: 'absolute', left: 88, right: 88, top: 668, bottom: 212}}>
        {renderBody(scene, beats, frame, fps, accent)}
      </div>

      <div
        style={{
          position: 'absolute',
          left: 88,
          right: 88,
          bottom: 90,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: theme.muted,
          fontSize: 28,
        }}
      >
        <span>{scene.visual.caption || scene.narration.slice(0, 20)}</span>
        <span>{Math.max(1, Math.round(scene.duration))}s</span>
      </div>
    </AbsoluteFill>
  );
};

const BackgroundGrid: React.FC<{accent: string}> = ({accent}) => (
  <>
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background:
          `linear-gradient(90deg, ${theme.grid} 1px, transparent 1px), linear-gradient(${theme.grid} 1px, transparent 1px)`,
        backgroundSize: '120px 120px',
        maskImage: 'radial-gradient(circle at 48% 34%, black, transparent 74%)',
      }}
    />
  </>
);

const renderBody = (
  scene: Scene,
  beats: MicroBeat[],
  frame: number,
  fps: number,
  accent: string
) => {
  if (scene.visual.layout === 'flow') {
    const nodes = scene.visual.diagram_nodes.length
      ? scene.visual.diagram_nodes
      : beats.map((beat) => beat.text);
    return <FlowBody nodes={nodes.slice(0, 5)} frame={frame} fps={fps} duration={scene.duration} accent={accent} />;
  }

  if (scene.visual.layout === 'code') {
    return <CodeBody scene={scene} beats={beats} frame={frame} fps={fps} accent={accent} />;
  }

  if (scene.visual.layout === 'steps') {
    return <StepsBody beats={beats} frame={frame} fps={fps} duration={scene.duration} accent={accent} />;
  }

  if (scene.visual.layout === 'stack') {
    return <StackBody beats={beats} frame={frame} fps={fps} duration={scene.duration} accent={accent} />;
  }

  return <BeatCards beats={beats} frame={frame} fps={fps} duration={scene.duration} accent={accent} />;
};

const BeatCards: React.FC<{
  beats: MicroBeat[];
  frame: number;
  fps: number;
  duration: number;
  accent: string;
}> = ({beats, frame, fps, duration, accent}) => (
  <div style={{display: 'grid', gap: 24}}>
    {beats.map((beat, index) => (
      <BeatCard
        key={`${beat.text}-${index}`}
        beat={beat}
        index={index}
        frame={frame}
        fps={fps}
        duration={duration}
        accent={accent}
      />
    ))}
  </div>
);

const BeatCard: React.FC<{
  beat: MicroBeat;
  index: number;
  frame: number;
  fps: number;
  duration: number;
  accent: string;
}> = ({beat, index, frame, fps, duration, accent}) => {
  const localStart = Math.round((beat.start_ratio ?? index * 0.18) * duration * fps);
  const opacity = interpolate(frame, [localStart, localStart + 6], [0.28, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const y = interpolate(frame, [localStart, localStart + 8], [14, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        minHeight: 128,
        border: `1px solid ${theme.border}`,
        borderRadius: 28,
        background: 'rgba(22,27,34,0.78)',
        boxShadow: '0 24px 70px rgba(0,0,0,0.06)',
        padding: '30px 34px',
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
        <span
          style={{
            width: 42,
            height: 42,
            borderRadius: 999,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: accent,
            color: '#0D1117',
            fontSize: 22,
            fontWeight: 700,
          }}
        >
          {index + 1}
        </span>
        <span style={{fontSize: 38, lineHeight: 1.22, fontWeight: 620}}>
          {beat.text}
        </span>
      </div>
      {beat.emphasis ? (
        <div style={{marginTop: 16, color: theme.muted, fontSize: 26}}>{beat.emphasis}</div>
      ) : null}
    </div>
  );
};

const FlowBody: React.FC<{
  nodes: string[];
  frame: number;
  fps: number;
  duration: number;
  accent: string;
}> = ({nodes, frame, fps, duration, accent}) => (
  <div style={{display: 'grid', gap: 18}}>
    {nodes.map((node, index) => {
      const beat: MicroBeat = {
        text: node,
        kind: 'flow',
        start_ratio: index * 0.16,
      };
      return (
        <React.Fragment key={node}>
          <BeatCard beat={beat} index={index} frame={frame} fps={fps} duration={duration} accent={accent} />
          {index < nodes.length - 1 ? (
            <div
              style={{
                width: 4,
                height: 28,
                marginLeft: 52,
                borderRadius: 999,
                background: 'rgba(240,246,252,0.16)',
              }}
            />
          ) : null}
        </React.Fragment>
      );
    })}
  </div>
);

const CodeBody: React.FC<{
  scene: Scene;
  beats: MicroBeat[];
  frame: number;
  fps: number;
  accent: string;
}> = ({scene, beats, frame, fps, accent}) => {
  const code = scene.visual.code || beats.find((beat) => beat.kind === 'code')?.text || 'streamlit run app.py';
  const opacity = interpolate(frame, [2, 10], [0.36, 1], {extrapolateRight: 'clamp'});
  const y = interpolate(frame, [2, 10], [16, 0], {extrapolateRight: 'clamp'});

  return (
    <div
      style={{
        borderRadius: 28,
        background: '#111111',
        color: '#F8FAFC',
        padding: '34px 36px',
        boxShadow: '0 30px 90px rgba(0,0,0,0.18)',
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      <div style={{display: 'flex', gap: 12, marginBottom: 28}}>
        <span style={{width: 16, height: 16, borderRadius: 999, background: '#FF5F57'}} />
        <span style={{width: 16, height: 16, borderRadius: 999, background: '#FFBD2E'}} />
        <span style={{width: 16, height: 16, borderRadius: 999, background: '#28C840'}} />
      </div>
      <pre
        style={{
          margin: 0,
          whiteSpace: 'pre-wrap',
          fontSize: 36,
          lineHeight: 1.35,
          fontFamily: 'SFMono-Regular, Consolas, monospace',
        }}
      >
        <span style={{color: accent}}>$ </span>
        {code}
      </pre>
    </div>
  );
};

const StepsBody: React.FC<{
  beats: MicroBeat[];
  frame: number;
  fps: number;
  duration: number;
  accent: string;
}> = ({beats, frame, fps, duration, accent}) => (
  <BeatCards
    beats={beats.map((beat, index) => ({...beat, kind: 'text', start_ratio: index * 0.16}))}
    frame={frame}
    fps={fps}
    duration={duration}
    accent={accent}
  />
);

const StackBody: React.FC<{
  beats: MicroBeat[];
  frame: number;
  fps: number;
  duration: number;
  accent: string;
}> = ({beats, frame, fps, duration, accent}) => (
  <div style={{display: 'flex', flexWrap: 'wrap', gap: 22}}>
    {beats.map((beat, index) => {
      const start = Math.round((beat.start_ratio ?? index * 0.12) * duration * fps);
      const opacity = interpolate(frame, [start, start + 6], [0.3, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
      const scale = interpolate(frame, [start, start + 8], [0.96, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
      return (
        <div
          key={`${beat.text}-${index}`}
          style={{
            minWidth: 238,
            height: 106,
            borderRadius: 999,
            border: `1px solid ${theme.border}`,
            background: index === 0 ? accent : 'rgba(22,27,34,0.8)',
            color: index === 0 ? '#0D1117' : theme.foreground,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 30px',
            fontSize: 34,
            fontWeight: 620,
            opacity,
            transform: `scale(${scale})`,
          }}
        >
          {beat.text}
        </div>
      );
    })}
  </div>
);

const getBeats = (scene: Scene): MicroBeat[] => {
  if (scene.visual.micro_beats && scene.visual.micro_beats.length > 0) {
    return scene.visual.micro_beats.slice(0, 4);
  }

  const bullets = scene.visual.bullets.length ? scene.visual.bullets : [scene.narration];
  return bullets.slice(0, 4).map((bullet, index) => ({
    text: bullet,
    kind: 'text',
    emphasis: null,
    start_ratio: index * 0.18,
  }));
};

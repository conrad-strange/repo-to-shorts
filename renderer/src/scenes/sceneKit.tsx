import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveAccent, theme} from '../styles/theme';
import type {MicroBeat, Scene} from '../types';

export const layoutLabel: Record<string, string> = {
  hook: '开场',
  github_hero: 'GitHub',
  title: '项目',
  text: '看点',
  readme_focus: 'README',
  stack: '技术栈',
  flow: '流程',
  code: '代码',
  steps: '步骤',
  cta: '行动',
};

export const getBeats = (scene: Scene, limit = 4): MicroBeat[] => {
  if (scene.visual.micro_beats && scene.visual.micro_beats.length > 0) {
    return scene.visual.micro_beats.slice(0, limit);
  }

  const bullets = scene.visual.bullets.length ? scene.visual.bullets : [scene.narration];
  return bullets.slice(0, limit).map((bullet, index) => ({
    text: bullet,
    kind: 'text',
    emphasis: null,
    start_ratio: index * 0.18,
  }));
};

export const beatTiming = (
  frame: number,
  fps: number,
  duration: number,
  startRatio: number,
) => {
  const start = Math.round(startRatio * duration * fps);
  return {
    opacity: interpolate(frame, [start, start + 8], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
    y: interpolate(frame, [start, start + 10], [18, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
    scale: interpolate(frame, [start, start + 10], [0.985, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
  };
};

export const SceneShell: React.FC<{
  scene: Scene;
  children: React.ReactNode;
  dense?: boolean;
}> = ({scene, children, dense = false}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const progress = interpolate(
    frame,
    [0, Math.max(1, scene.duration * fps - 1)],
    [0, 1],
    {extrapolateRight: 'clamp'},
  );
  const title = beatTiming(frame, fps, scene.duration, 0);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.background,
        color: theme.foreground,
        fontFamily: theme.fontFamily,
        overflow: 'hidden',
      }}
    >
      <Background accent={accent} />
      <div
        style={{
          position: 'absolute',
          left: 88,
          right: 88,
          top: 88,
          height: 5,
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

      <div style={{position: 'absolute', left: 118, right: 88, top: 134}}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            height: 44,
            padding: '0 18px',
            border: `1px solid ${theme.border}`,
            borderRadius: 999,
            background: 'rgba(22,27,34,0.78)',
            color: theme.muted,
            fontSize: 24,
          }}
        >
          <span style={{width: 8, height: 8, borderRadius: 999, background: accent}} />
          {layoutLabel[scene.visual.layout] || '项目'}
        </div>
        <div
          style={{
            width: dense ? 860 : 900,
            marginTop: dense ? 58 : 76,
            fontSize: dense ? 66 : 76,
            fontWeight: 760,
            lineHeight: 1.04,
            letterSpacing: 0,
            opacity: title.opacity,
            transform: `translateY(${title.y}px) scale(${title.scale})`,
          }}
        >
          {scene.visual.headline}
        </div>
      </div>

      <div style={{position: 'absolute', left: 88, right: 88, top: dense ? 560 : 620, bottom: 184}}>
        {children}
      </div>

      <div
        style={{
          position: 'absolute',
          left: 88,
          right: 88,
          bottom: 82,
          display: 'flex',
          justifyContent: 'space-between',
          gap: 24,
          color: theme.muted,
          fontSize: 26,
        }}
      >
        <span style={{maxWidth: 720, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
          {scene.visual.caption || scene.narration.slice(0, 22)}
        </span>
        <span>{Math.max(1, Math.round(scene.duration))}s</span>
      </div>
    </AbsoluteFill>
  );
};

export const BeatLine: React.FC<{
  beat: MicroBeat;
  index: number;
  scene: Scene;
  accent: string;
}> = ({beat, index, scene, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const timing = beatTiming(frame, fps, scene.duration, beat.start_ratio ?? index * 0.18);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '46px 1fr',
        gap: 18,
        alignItems: 'start',
        opacity: timing.opacity,
        transform: `translateY(${timing.y}px)`,
      }}
    >
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: 999,
          background: index === 0 ? accent : 'rgba(240,246,252,0.1)',
          color: index === 0 ? '#0D1117' : theme.foreground,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 22,
          fontWeight: 760,
        }}
      >
        {index + 1}
      </div>
      <div>
        <div style={{fontSize: 38, fontWeight: 680, lineHeight: 1.18}}>
          <HighlightText text={beat.text} accent={accent} />
        </div>
        {beat.emphasis ? (
          <div style={{marginTop: 10, color: theme.muted, fontSize: 25, lineHeight: 1.28}}>
            {beat.emphasis}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const accentOf = (scene: Scene) => resolveAccent(scene.visual.accent_color);

export const HighlightText: React.FC<{text: string; accent: string}> = ({text, accent}) => {
  const keywords = [
    'RAG',
    'FAISS',
    'DeepSeek',
    'README',
    'GitHub',
    '本地',
    '检索',
    '论文',
    '代码',
    '证据',
    '项目',
  ];
  const pattern = new RegExp(`(${keywords.map(escapeRegExp).join('|')})`, 'g');
  const parts = text.split(pattern).filter(Boolean);

  return (
    <>
      {parts.map((part, index) =>
        keywords.includes(part) ? (
          <span key={`${part}-${index}`} style={{color: accent}}>
            {part}
          </span>
        ) : (
          <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>
        ),
      )}
    </>
  );
};

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const Background: React.FC<{accent: string}> = ({accent}) => (
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

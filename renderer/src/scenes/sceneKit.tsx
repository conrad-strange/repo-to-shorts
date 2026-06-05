import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveAccent, theme} from '../styles/theme';
import type {MicroBeat, Scene, VisualPage} from '../types';

export const layoutLabel: Record<string, string> = {
  hook: 'Hook',
  github_hero: 'Repo',
  title: 'Project',
  text: 'Insight',
  readme_focus: 'README',
  feature_spotlight: 'Feature',
  architecture_map: 'Flow',
  evidence_grid: 'Evidence',
  stack: 'Stack',
  flow: 'Flow',
  code: 'Code',
  result_media: 'Result',
  steps: 'Usage',
  cta: 'GitHub',
};

export const PAGE_TRANSITION_SECONDS = 1;

export const getBeats = (scene: Scene, limit = 4): MicroBeat[] => {
  if (scene.visual.micro_beats && scene.visual.micro_beats.length > 0) {
    const beats = scene.visual.micro_beats
      .map((beat) => ({...beat, text: normalizeCopy(beat.text)}))
      .filter((beat) => beat.text);
    if (beats.length) {
      return beats.slice(0, limit);
    }
  }

  const bullets = (scene.visual.bullets.length ? scene.visual.bullets : [scene.visual.caption || scene.visual.headline])
    .map((item) => normalizeCopy(item || ''))
    .filter(Boolean);
  return bullets.slice(0, limit).map((bullet, index) => ({
    text: bullet,
    kind: 'text',
    emphasis: null,
    start_ratio: index * 0.18,
  }));
};

export interface VisualPageState {
  page: VisualPage;
  index: number;
  rawPageFrame: number;
  pageFrame: number;
  pageDuration: number;
  pageCount: number;
}

export interface SceneMotionState {
  frame: number;
  fps: number;
  accent: string;
  pageState: VisualPageState | null;
  timingFrame: number;
  timingDuration: number;
}

export const useSceneMotion = (scene: Scene): SceneMotionState => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pageState = visualPageState(scene, frame, fps);

  return {
    frame,
    fps,
    accent: accentOf(scene),
    pageState,
    timingFrame: pageState?.pageFrame ?? frame,
    timingDuration: pageState?.pageDuration ?? scene.duration,
  };
};

export const visualPageState = (scene: Scene, frame: number, fps: number): VisualPageState | null => {
  const pages = normalizedVisualPages(scene);
  if (!pages.length) {
    return null;
  }
  const pageCount = pages.length;
  const pageFrames = Math.max(1, Math.round((scene.duration * fps) / pageCount));
  const index = Math.min(pageCount - 1, Math.max(0, Math.floor(frame / pageFrames)));
  const rawPageFrame = frame - index * pageFrames;
  const settledPageFrame = Math.round(fps * 0.4);
  return {
    page: pages[index],
    index,
    rawPageFrame,
    pageFrame: index === 0 ? rawPageFrame : Math.max(rawPageFrame, settledPageFrame),
    pageDuration: Math.max(0.1, pageFrames / fps),
    pageCount,
  };
};

export const visualPageTransition = (pageState: VisualPageState | null, fps: number) => {
  if (!pageState || pageState.index === 0) {
    return {opacity: 1, y: 0};
  }
  const transitionFrames = Math.max(1, Math.round(PAGE_TRANSITION_SECONDS * fps));
  const progress = interpolate(pageState.rawPageFrame, [0, transitionFrames], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return {
    opacity: interpolate(progress, [0, 1], [0.16, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
    y: interpolate(progress, [0, 1], [34, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
  };
};

export const pageBeats = (
  scene: Scene,
  pageState: VisualPageState | null,
  fallback: MicroBeat[],
  limit = 4,
): MicroBeat[] => {
  const items = pageItems(scene, pageState, fallback.map((beat) => beat.text), limit);
  if (!items.length) {
    return fallback.slice(0, limit);
  }
  return items.slice(0, limit).map((text, index) => {
    const previous = fallback[index];
    return {
      text,
      kind: previous?.kind ?? 'text',
      emphasis: previous?.emphasis ?? null,
      start_ratio: index * 0.18,
    };
  });
};

export const pageItems = (
  _scene: Scene,
  pageState: VisualPageState | null,
  fallback: string[],
  limit = 4,
): string[] => {
  const items = (pageState?.page.items || []).map((item) => normalizeCopy(item)).filter(Boolean);
  const fallbackItems = fallback.map((item) => normalizeCopy(item)).filter(Boolean);
  return (items.length ? items : fallbackItems).slice(0, limit);
};

export const beatsForScenePage = (scene: Scene, motion: SceneMotionState, limit = 4): MicroBeat[] => {
  return pageBeats(scene, motion.pageState, getBeats(scene, limit), limit);
};

export const itemsForScenePage = (
  scene: Scene,
  motion: SceneMotionState,
  fallback: string[],
  limit = 4,
): string[] => {
  return pageItems(scene, motion.pageState, fallback, limit);
};

export const timingForMotion = (motion: SceneMotionState, startRatio: number) => {
  return beatTiming(motion.timingFrame, motion.fps, motion.timingDuration, startRatio);
};

export const beatTiming = (frame: number, fps: number, duration: number, startRatio: number) => {
  const start = Math.round(startRatio * duration * fps);
  return {
    opacity: interpolate(frame, [start, start + 9], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
    y: interpolate(frame, [start, start + 12], [18, 0], {
      easing: Easing.bezier(0.16, 1, 0.3, 1),
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
    scale: interpolate(frame, [start, start + 12], [0.985, 1], {
      easing: Easing.bezier(0.16, 1, 0.3, 1),
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
  };
};

export const SceneShell: React.FC<{
  scene: Scene;
  children: React.ReactNode;
  dense?: boolean;
  motion: SceneMotionState;
}> = ({scene, children, dense = false, motion}) => {
  const {frame, fps, accent, pageState} = motion;
  const progress = interpolate(frame, [0, Math.max(1, scene.duration * fps - 1)], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const titleFrame = pageState ? pageState.pageFrame : frame;
  const titleDuration = pageState ? pageState.pageDuration : scene.duration;
  const title = beatTiming(titleFrame, fps, titleDuration, 0);
  const pageTransition = visualPageTransition(pageState, fps);
  const headline =
    normalizeCopy(pageState?.page.title || '') ||
    normalizeCopy(scene.visual.headline) ||
    layoutLabel[scene.visual.layout] ||
    'Scene';
  const caption =
    normalizeCopy(pageState?.page.caption || '') ||
    normalizeCopy(scene.visual.caption || '') ||
    layoutLabel[scene.visual.layout] ||
    'Scene';

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.background,
        color: theme.foreground,
        fontFamily: theme.fontFamily,
        overflow: 'hidden',
      }}
    >
      <Background />
      <div
        style={{
          position: 'absolute',
          left: 88,
          right: 88,
          top: 82,
          height: 4,
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

      <div style={{position: 'absolute', left: 104, right: 88, top: 124}}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            height: 42,
            padding: '0 16px',
            border: `1px solid ${theme.border}`,
            borderRadius: 999,
            background: 'rgba(22,27,34,0.78)',
            color: theme.muted,
            fontSize: 23,
          }}
        >
          <span style={{width: 8, height: 8, borderRadius: 999, background: accent}} />
          {layoutLabel[scene.visual.layout] || 'Scene'}
        </div>
        <div
          style={{
            width: dense ? 850 : 900,
            marginTop: dense ? 48 : 64,
            fontSize: dense ? 62 : 72,
            fontWeight: 780,
            lineHeight: 1.05,
            letterSpacing: 0,
            opacity: title.opacity * pageTransition.opacity,
            transform: `translateY(${title.y + pageTransition.y}px) scale(${title.scale})`,
          }}
        >
          <HighlightText text={headline} accent={accent} />
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 88,
          right: 88,
          top: dense ? 520 : 590,
          bottom: 245,
          opacity: pageTransition.opacity,
          transform: `translateY(${pageTransition.y}px)`,
        }}
      >
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
          fontSize: 24,
          opacity: pageTransition.opacity,
          transform: `translateY(${pageTransition.y * 0.35}px)`,
        }}
      >
        <span style={{maxWidth: 720, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
          {normalizeCopy(caption)}
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
  frameOverride?: number;
  durationOverride?: number;
}> = ({beat, index, scene, accent, frameOverride, durationOverride}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const localFrame = frameOverride ?? frame;
  const duration = durationOverride ?? scene.duration;
  const timing = beatTiming(localFrame, fps, duration, beat.start_ratio ?? index * 0.18);

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
  const normalizedText = normalizeCopy(text);
  const keywords = ['RAG', 'FAISS', 'DeepSeek', 'README', 'GitHub', 'MCP', 'LLM', 'API', '本地', '检索', '代码', '证据'];
  const pattern = new RegExp(`(${keywords.map(escapeRegExp).join('|')})`, 'gi');
  const parts = normalizedText.split(pattern).filter(Boolean);

  return (
    <>
      {parts.map((part, index) =>
        keywords.some((keyword) => keyword.toLowerCase() === part.toLowerCase()) ? (
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

export const normalizeCopy = (value: string) => {
  return String(value || '').replace(/READNE/gi, 'README').replace(/\s+/g, ' ').trim();
};

const normalizedVisualPages = (scene: Scene): VisualPage[] =>
  (scene.visual.visual_pages || [])
    .map((page) => ({
      title: normalizeCopy(String(page.title || '').trim()),
      caption: page.caption ? normalizeCopy(String(page.caption).trim()) : null,
      items: (page.items || []).map((item) => normalizeCopy(String(item || '').trim())).filter(Boolean),
    }))
    .filter((page) => page.title || page.caption || page.items.length);

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const Background: React.FC = () => (
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
);

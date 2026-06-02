import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {accentOf} from './sceneKit';

export const CtaScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const repoHandle = compactRepoHandle(scene.visual.repo_display_url || scene.visual.headline);
  const repoUrl = fullRepoUrl(scene.visual.repo_url || scene.visual.repo_display_url || repoHandle);
  const enter = spring({frame: frame - 4, fps, config: {damping: 20, stiffness: 86}});
  const starScale = interpolate(
    frame,
    [Math.round(fps * 0.78), Math.round(fps * 1.05), Math.round(fps * 1.28)],
    [1, 1.08, 1],
    {easing: Easing.bezier(0.16, 1, 0.3, 1), extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
  const starLight = interpolate(frame, [Math.round(fps * 0.72), Math.round(fps * 1.04)], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const shineX = interpolate(frame, [Math.round(fps * 0.96), Math.round(fps * 1.54)], [-130, 150], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const line = interpolate(frame, [Math.round(fps * 0.24), Math.round(fps * 0.78)], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.background,
        color: theme.foreground,
        fontFamily: theme.fontFamily,
        overflow: 'hidden',
      }}
    >
      <BackgroundGrid />
      <div style={{display: 'grid', placeItems: 'center', height: '100%', padding: 88}}>
        <div
          style={{
            width: 900,
            borderRadius: 8,
            border: `1px solid ${theme.border}`,
            background: 'rgba(22,27,34,0.88)',
            boxShadow: `0 34px 110px ${theme.shadow}`,
            padding: '42px 44px',
            opacity: enter,
            transform: `translateY(${interpolate(enter, [0, 1], [34, 0])}px) scale(${interpolate(enter, [0, 1], [0.985, 1])})`,
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 14, color: theme.muted, fontSize: 24}}>
              <RepoMark accent={accent} />
              Open Source
            </div>
            <StarButton starScale={starScale} starLight={starLight} shineX={shineX} accent={accent} />
          </div>

          <div
            style={{
              marginTop: 32,
              fontSize: 62,
              lineHeight: 1.08,
              fontWeight: 800,
              color: theme.foreground,
              fontFamily: 'SFMono-Regular, Consolas, monospace',
              wordBreak: 'break-word',
            }}
          >
            {repoHandle}
          </div>

          <div style={{marginTop: 24, width: `${line * 100}%`, height: 3, borderRadius: 999, background: accent}} />

          <div style={{marginTop: 34, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14}}>
            <Action label="查看代码" accent={accent} active />
            <Action label="阅读 README" accent={accent} />
            <Action label="欢迎 Star" accent={accent} />
          </div>

          <RepoLinkCard repoUrl={repoUrl} accent={accent} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const compactRepoHandle = (value?: string | null) =>
  (value || '')
    .replace(/^https?:\/\/github\.com\//i, '')
    .replace(/^github\.com\//i, '')
    .replace(/\.git$/i, '')
    .trim() || 'owner/repo';

const fullRepoUrl = (value?: string | null) => {
  const cleaned = (value || '').replace(/^https?:\/\//i, '').replace(/\.git$/i, '').trim();
  if (!cleaned) {
    return 'github.com/owner/repo';
  }
  return cleaned.startsWith('github.com/') ? cleaned : `github.com/${compactRepoHandle(cleaned)}`;
};

const StarButton: React.FC<{starScale: number; starLight: number; shineX: number; accent: string}> = ({
  starScale,
  starLight,
  shineX,
  accent,
}) => {
  const gold = '#F2CC60';
  const isLit = starLight > 0.45;
  return (
    <div
      style={{
        position: 'relative',
        height: 48,
        borderRadius: 8,
        border: `1px solid ${isLit ? gold : accent}`,
        background: isLit ? 'rgba(242,204,96,0.16)' : 'rgba(88,166,255,0.14)',
        color: theme.foreground,
        boxShadow: isLit ? `0 0 28px rgba(242,204,96,${0.18 + starLight * 0.28})` : 'none',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '0 16px',
        fontSize: 24,
        fontWeight: 760,
        overflow: 'hidden',
        transform: `scale(${starScale})`,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: -8,
          bottom: -8,
          left: shineX,
          width: 34,
          transform: 'rotate(18deg)',
          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.36), transparent)',
          opacity: starLight,
        }}
      />
      <span style={{position: 'relative', color: isLit ? gold : accent}}>★</span>
      <span style={{position: 'relative'}}>Star</span>
    </div>
  );
};

const RepoLinkCard: React.FC<{repoUrl: string; accent: string}> = ({repoUrl, accent}) => (
  <div
    style={{
      marginTop: 34,
      minHeight: 94,
      borderRadius: 8,
      border: `1px solid rgba(240,246,252,0.12)`,
      background: 'rgba(13,17,23,0.55)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 18,
      padding: '0 24px',
    }}
  >
    <div style={{minWidth: 0}}>
      <div style={{color: theme.muted, fontSize: 20, marginBottom: 8}}>GitHub repository</div>
      <div
        style={{
          color: theme.foreground,
          fontSize: 25,
          fontFamily: 'SFMono-Regular, Consolas, monospace',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {repoUrl}
      </div>
    </div>
    <div
      style={{
        flex: '0 0 auto',
        height: 44,
        borderRadius: 8,
        border: `1px solid ${accent}`,
        color: accent,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        fontSize: 21,
        fontWeight: 720,
      }}
    >
      打开项目
    </div>
  </div>
);

const Action: React.FC<{label: string; accent: string; active?: boolean}> = ({label, accent, active = false}) => (
  <div
    style={{
      height: 74,
      borderRadius: 8,
      border: `1px solid ${active ? accent : theme.border}`,
      background: active ? 'rgba(88,166,255,0.15)' : 'rgba(240,246,252,0.06)',
      color: active ? theme.foreground : theme.muted,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 25,
      fontWeight: 720,
    }}
  >
    {label}
  </div>
);

const RepoMark: React.FC<{accent: string}> = ({accent}) => (
  <div style={{width: 32, height: 32, borderRadius: 8, border: `2px solid ${accent}`, position: 'relative'}}>
    <span style={{position: 'absolute', left: 8, top: 8, width: 7, height: 7, borderRadius: 999, background: accent}} />
    <span style={{position: 'absolute', left: 8, bottom: 8, width: 14, height: 2, background: accent}} />
  </div>
);

const BackgroundGrid: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      background:
        `linear-gradient(90deg, ${theme.grid} 1px, transparent 1px), linear-gradient(${theme.grid} 1px, transparent 1px)`,
      backgroundSize: '120px 120px',
      maskImage: 'radial-gradient(circle at 50% 44%, black, transparent 72%)',
    }}
  />
);

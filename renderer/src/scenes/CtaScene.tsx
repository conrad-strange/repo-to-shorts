import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {accentOf} from './sceneKit';

export const CtaScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const repoHandle = compactRepoHandle(scene.visual.repo_display_url || scene.visual.headline);
  const enter = interpolate(frame, [0, Math.round(fps * 0.5)], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const line = interpolate(frame, [Math.round(fps * 0.26), Math.round(fps * 0.82)], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const secondaryOpacity = interpolate(
    frame,
    [Math.round(fps * 0.45), Math.round(fps * 0.82)],
    [0, 1],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    },
  );
  const cardY = interpolate(enter, [0, 1], [28, 0]);

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
      <div
        style={{
          display: 'grid',
          placeItems: 'center',
          height: '100%',
          padding: 88,
        }}
      >
        <div
          style={{
            width: 900,
            minHeight: 318,
            borderRadius: 8,
            border: `1px solid ${theme.border}`,
            background: 'rgba(22,27,34,0.86)',
            boxShadow: `0 28px 90px ${theme.shadow}`,
            padding: '38px 42px',
            opacity: enter,
            transform: `translateY(${cardY}px)`,
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 14, color: theme.muted, fontSize: 24}}>
              <RepoMark accent={accent} />
              Repository
            </div>
            <div style={{color: theme.muted, fontSize: 22}}>GitHub</div>
          </div>

          <div
            style={{
              marginTop: 28,
              fontSize: 58,
              lineHeight: 1.08,
              fontWeight: 780,
              color: theme.foreground,
              fontFamily: 'SFMono-Regular, Consolas, monospace',
              wordBreak: 'break-word',
            }}
          >
            {repoHandle}
          </div>

          <div
            style={{
              marginTop: 20,
              width: `${line * 100}%`,
              height: 3,
              borderRadius: 999,
              background: accent,
            }}
          />

          <div
            style={{
              marginTop: 30,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 24,
              opacity: secondaryOpacity,
            }}
          >
            <div style={{fontSize: 30, color: theme.foreground, fontWeight: 680}}>
              GitHub 上查看项目
            </div>
            <div style={{display: 'flex', gap: 12, color: theme.muted, fontSize: 23}}>
              <span>README</span>
              <span>/</span>
              <span>Star</span>
              <span>/</span>
              <span>Clone</span>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const compactRepoHandle = (value?: string | null) => {
  const cleaned = (value || '').trim();
  return (
    cleaned
      .replace(/^https?:\/\/github\.com\//i, '')
      .replace(/^github\.com\//i, '')
      .replace(/\.git$/i, '')
      .replace(/^GitHub搜索[:：]\s*/i, '') || 'owner/repo'
  );
};

const RepoMark: React.FC<{accent: string}> = ({accent}) => (
  <div
    style={{
      width: 32,
      height: 32,
      borderRadius: 8,
      border: `2px solid ${accent}`,
      position: 'relative',
    }}
  >
    <span
      style={{
        position: 'absolute',
        left: 8,
        top: 8,
        width: 7,
        height: 7,
        borderRadius: 999,
        background: accent,
      }}
    />
    <span
      style={{
        position: 'absolute',
        left: 8,
        bottom: 8,
        width: 14,
        height: 2,
        background: accent,
      }}
    />
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

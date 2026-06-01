import React from 'react';
import {AbsoluteFill, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveAccent, theme} from '../styles/theme';
import type {Scene} from '../types';
import {HighlightText} from './sceneKit';

export const GithubHeroScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = resolveAccent(scene.visual.accent_color);
  const asset = scene.visual.asset_path;
  const repoUrl = scene.visual.repo_display_url || scene.visual.repo_url || 'github.com/repository';
  const total = Math.max(1, scene.duration * fps);
  const screenshotOpacity = interpolate(frame, [0, 12], [0, 1], {extrapolateRight: 'clamp'});
  const zoom = spring({frame: frame - 10, fps, config: {damping: 22, stiffness: 68, mass: 0.9}});
  const screenshotScale = interpolate(zoom, [0, 1], [0.78, 1.62], {extrapolateRight: 'clamp'});
  const screenshotX = interpolate(zoom, [0, 1], [0, 260], {extrapolateRight: 'clamp'});
  const screenshotY = interpolate(zoom, [0, 1], [230, -28], {extrapolateRight: 'clamp'});
  const titleOpacity = interpolate(frame, [3, 15], [0, 1], {extrapolateRight: 'clamp'});
  const titleY = interpolate(frame, [3, 16], [30, 0], {extrapolateRight: 'clamp'});
  const frameY = interpolate(frame, [0, 18], [34, 0], {extrapolateRight: 'clamp'});
  const hudOpacity = interpolate(frame, [20, 34], [0, 1], {extrapolateRight: 'clamp'});
  const focusOpacity = interpolate(frame, [28, 44], [0, 1], {extrapolateRight: 'clamp'});

  if (!asset) {
    return <FallbackHook scene={scene} accent={accent} />;
  }

  return (
    <AbsoluteFill
      style={{
        background: theme.background,
        color: theme.foreground,
        fontFamily: theme.fontFamily,
        overflow: 'hidden',
      }}
    >
      <GridBackground accent={accent} />

      <div style={{position: 'absolute', left: 74, right: 74, top: 96}}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            color: theme.muted,
            fontSize: 22,
          }}
        >
          <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
            <RepoGlyph accent={accent} />
            <span>GitHub 项目详解</span>
          </div>
          <span>9:16 Repo Story</span>
        </div>

        <div
          style={{
            marginTop: 54,
            width: 900,
            fontSize: 88,
            fontWeight: 780,
            lineHeight: 1.02,
            letterSpacing: 0,
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
          }}
        >
          <HighlightText text={scene.visual.headline} accent={accent} />
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 64,
          right: 64,
          top: 466,
          height: 958,
          borderRadius: 8,
          overflow: 'hidden',
          border: `1px solid ${theme.border}`,
          background: theme.panel,
          boxShadow: `0 38px 100px ${theme.shadow}`,
          opacity: screenshotOpacity,
          transform: `translateY(${frameY}px)`,
        }}
      >
        <BrowserBar accent={accent} repoUrl={repoUrl} />
        <img
          src={staticFile(asset)}
          style={{
            width: '100%',
            height: 'calc(100% - 56px)',
            display: 'block',
            position: 'relative',
            zIndex: 1,
            objectFit: 'cover',
            objectPosition: '50% 0%',
            transform: `translate(${screenshotX}px, ${screenshotY}px) scale(${screenshotScale})`,
            transformOrigin: '18% 10%',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: 178,
            top: 72,
            width: 474,
            height: 68,
            zIndex: 3,
            borderRadius: 8,
            border: `2px solid ${accent}`,
            boxShadow: `0 0 0 999px rgba(13,17,23,${0.52 * focusOpacity})`,
            opacity: focusOpacity,
          }}
        />
      </div>

      <div
        style={{
          position: 'absolute',
          left: 86,
          right: 86,
          bottom: 92,
          display: 'grid',
          gridTemplateColumns: '1fr 304px',
          gap: 20,
          opacity: hudOpacity,
        }}
      >
        <div
          style={{
            borderRadius: 8,
            border: `1px solid ${theme.border}`,
            background: 'rgba(22,27,34,0.92)',
            padding: '28px 32px',
            boxShadow: `0 24px 70px ${theme.shadow}`,
          }}
        >
          <div style={{color: theme.muted, fontSize: 22, marginBottom: 10}}>
            {scene.visual.caption || '真实仓库界面'}
          </div>
          <div style={{fontSize: 34, fontWeight: 680, lineHeight: 1.24}}>
            {scene.narration}
          </div>
        </div>

        <div style={{display: 'grid', gap: 10}}>
          <SignalChip icon="repo" label="Repo" accent={accent} />
          <SignalChip icon="readme" label="README" accent={accent} />
          <SignalChip icon="code" label="Code" accent={accent} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const BrowserBar: React.FC<{accent: string; repoUrl: string}> = ({accent, repoUrl}) => (
  <div
    style={{
      height: 56,
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      padding: '0 18px',
      borderBottom: `1px solid ${theme.border}`,
      background: theme.panelElevated,
      position: 'relative',
      zIndex: 4,
    }}
  >
    <span style={{width: 10, height: 10, borderRadius: 999, background: '#FF5F57'}} />
    <span style={{width: 10, height: 10, borderRadius: 999, background: '#FFBD2E'}} />
    <span style={{width: 10, height: 10, borderRadius: 999, background: '#28C840'}} />
    <div
      style={{
        marginLeft: 12,
        height: 30,
        flex: 1,
        borderRadius: 8,
        border: `1px solid ${theme.border}`,
        background: 'rgba(13,17,23,0.72)',
        color: theme.muted,
        fontSize: 18,
        display: 'flex',
        alignItems: 'center',
        paddingLeft: 14,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    >
      {repoUrl}
    </div>
    <RepoGlyph accent={accent} small />
  </div>
);

const SignalChip: React.FC<{icon: 'repo' | 'readme' | 'code'; label: string; accent: string}> = ({
  icon,
  label,
  accent,
}) => (
  <div
    style={{
      height: 70,
      borderRadius: 8,
      border: `1px solid ${theme.border}`,
      background: 'rgba(22,27,34,0.86)',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '0 18px',
      color: theme.foreground,
      fontSize: 24,
      fontWeight: 650,
    }}
  >
    <SemanticIcon kind={icon} accent={accent} />
    {label}
  </div>
);

const SemanticIcon: React.FC<{kind: 'repo' | 'readme' | 'code'; accent: string}> = ({kind, accent}) => {
  const mark = kind === 'repo' ? 'R' : kind === 'readme' ? 'M' : '<>';
  return (
    <div
      style={{
        width: 34,
        height: 34,
        borderRadius: 8,
        background: kind === 'repo' ? accent : 'rgba(240,246,252,0.08)',
        color: kind === 'repo' ? '#0D1117' : theme.foreground,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: kind === 'code' ? 16 : 18,
        fontWeight: 780,
        fontFamily: kind === 'code' ? 'SFMono-Regular, Consolas, monospace' : theme.fontFamily,
      }}
    >
      {mark}
    </div>
  );
};

const RepoGlyph: React.FC<{accent: string; small?: boolean}> = ({accent, small = false}) => (
  <div
    style={{
      width: small ? 26 : 34,
      height: small ? 26 : 34,
      borderRadius: 8,
      border: `2px solid ${accent}`,
      position: 'relative',
    }}
  >
    <span
      style={{
        position: 'absolute',
        left: small ? 6 : 8,
        top: small ? 6 : 8,
        width: small ? 6 : 8,
        height: small ? 6 : 8,
        borderRadius: 999,
        background: accent,
      }}
    />
    <span
      style={{
        position: 'absolute',
        left: small ? 6 : 8,
        bottom: small ? 6 : 8,
        width: small ? 10 : 14,
        height: 2,
        background: accent,
      }}
    />
  </div>
);

const GridBackground: React.FC<{accent: string}> = ({accent}) => (
  <>
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background:
          `linear-gradient(90deg, ${theme.grid} 1px, transparent 1px), linear-gradient(${theme.grid} 1px, transparent 1px)`,
        backgroundSize: '120px 120px',
      }}
    />
  </>
);

const FallbackHook: React.FC<{scene: Scene; accent: string}> = ({scene, accent}) => (
  <AbsoluteFill
    style={{
      justifyContent: 'center',
      padding: 88,
      fontFamily: theme.fontFamily,
      backgroundColor: theme.background,
      color: theme.foreground,
    }}
  >
      <div style={{borderLeft: `8px solid ${accent}`, paddingLeft: 34}}>
      <div style={{fontSize: 86, fontWeight: 760, lineHeight: 1.04}}>
        {scene.visual.headline}
      </div>
      <div style={{height: 28}} />
      <div style={{fontSize: 36, lineHeight: 1.35, color: theme.muted}}>
        {scene.narration}
      </div>
    </div>
  </AbsoluteFill>
);

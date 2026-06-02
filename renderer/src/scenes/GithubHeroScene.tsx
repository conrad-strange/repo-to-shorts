import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveAccent, theme} from '../styles/theme';
import type {Scene} from '../types';
import {HighlightText} from './sceneKit';

export const GithubHeroScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = resolveAccent(scene.visual.accent_color);
  const asset = scene.visual.asset_path;
  const repoUrl = scene.visual.repo_display_url || scene.visual.repo_url || 'github.com/repository';
  const repoHandle = compactRepoHandle(repoUrl);
  const beats = (scene.visual.micro_beats || []).slice(0, 3);
  const headlineSize = heroHeadlineSize(scene.visual.headline);

  const titleIn = spring({frame: frame - 3, fps, config: {damping: 22, stiffness: 90}});
  const cardIn = interpolate(frame, [14, 32], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const screenshotIn = interpolate(frame, [4, 28], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        background: theme.background,
        color: theme.foreground,
        fontFamily: theme.fontFamily,
        overflow: 'hidden',
      }}
    >
      <GridBackground />
      {asset ? (
        <img
          src={staticFile(asset)}
          style={{
            position: 'absolute',
            left: -130,
            top: 360,
            width: 1340,
            height: 940,
            objectFit: 'cover',
            objectPosition: '50% 0%',
            opacity: 0.22 * screenshotIn,
            filter: 'blur(1.6px) brightness(0.58) saturate(0.9)',
            transform: `scale(${1.03 + screenshotIn * 0.05})`,
          }}
        />
      ) : null}

      <div style={{position: 'absolute', left: 76, right: 76, top: 86}}>
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
            <span>GitHub 项目讲解</span>
          </div>
          <span>9:16 Repo Story</span>
        </div>

        <div
          style={{
            marginTop: 52,
            width: '100%',
            maxWidth: 900,
            fontSize: headlineSize,
            fontWeight: 800,
            lineHeight: 1.02,
            letterSpacing: 0,
            overflowWrap: 'break-word',
            wordBreak: 'break-word',
            opacity: titleIn,
            transform: `translateY(${interpolate(titleIn, [0, 1], [26, 0])}px)`,
          }}
        >
          <HighlightText text={scene.visual.headline} accent={accent} />
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 72,
          right: 72,
          top: 650,
          borderRadius: 8,
          border: `1px solid ${theme.border}`,
          background: 'rgba(22,27,34,0.9)',
          boxShadow: `0 36px 100px ${theme.shadow}`,
          padding: '30px 34px',
          opacity: cardIn,
          transform: `translateY(${interpolate(cardIn, [0, 1], [32, 0])}px)`,
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20}}>
          <div style={{fontSize: 24, color: theme.muted}}>Repository</div>
          <div style={{fontSize: 20, color: theme.muted}}>{repoUrl}</div>
        </div>
        <div
          style={{
            marginTop: 14,
            fontSize: 46,
            lineHeight: 1.1,
            fontWeight: 780,
            fontFamily: 'SFMono-Regular, Consolas, monospace',
            wordBreak: 'break-word',
          }}
        >
          {repoHandle}
        </div>

        <div style={{marginTop: 24, display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 18}}>
          <div
            style={{
              borderRadius: 8,
              border: `1px solid ${theme.border}`,
              background: 'rgba(13,17,23,0.72)',
              padding: '22px 24px',
            }}
          >
            <div style={{fontSize: 21, color: theme.muted, marginBottom: 10}}>Core promise</div>
            <div style={{fontSize: 32, fontWeight: 700, lineHeight: 1.22}}>
              <HighlightText text={scene.visual.caption || '快速看懂项目价值'} accent={accent} />
            </div>
          </div>
          <div style={{display: 'grid', gap: 10}}>
            {(beats.length ? beats : fallbackBeats(scene)).map((beat, index) => (
              <SignalChip key={`${beat.text}-${index}`} label={beat.text} accent={accent} active={index === 0} />
            ))}
          </div>
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          bottom: 90,
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: theme.muted,
          fontSize: 24,
        }}
      >
        <span>README / Code / Evidence</span>
        <span style={{color: accent}}>开源仓库</span>
      </div>
    </AbsoluteFill>
  );
};

const fallbackBeats = (scene: Scene) =>
  (scene.visual.bullets.length ? scene.visual.bullets : ['README', '核心文件', '项目标签']).slice(0, 3).map((text) => ({
    text,
  }));

const compactRepoHandle = (value?: string | null) =>
  (value || '')
    .replace(/^https?:\/\/github\.com\//i, '')
    .replace(/^github\.com\//i, '')
    .replace(/\.git$/i, '')
    .trim() || 'owner/repo';

const heroHeadlineSize = (text: string) => {
  const length = Array.from(text || '').length;
  if (length > 22) return 68;
  if (length > 16) return 76;
  if (length > 11) return 84;
  return 92;
};

const SignalChip: React.FC<{label: string; accent: string; active?: boolean}> = ({label, accent, active = false}) => (
  <div
    style={{
      height: 64,
      borderRadius: 8,
      border: `1px solid ${active ? accent : theme.border}`,
      background: active ? 'rgba(88,166,255,0.16)' : 'rgba(240,246,252,0.06)',
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '0 16px',
      color: theme.foreground,
      fontSize: 24,
      fontWeight: 680,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    }}
  >
    <span style={{width: 8, height: 8, borderRadius: 999, background: active ? accent : theme.muted}} />
    {label}
  </div>
);

const RepoGlyph: React.FC<{accent: string}> = ({accent}) => (
  <div
    style={{
      width: 34,
      height: 34,
      borderRadius: 8,
      border: `2px solid ${accent}`,
      position: 'relative',
    }}
  >
    <span style={{position: 'absolute', left: 8, top: 8, width: 8, height: 8, borderRadius: 999, background: accent}} />
    <span style={{position: 'absolute', left: 8, bottom: 8, width: 14, height: 2, background: accent}} />
  </div>
);

const GridBackground: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      background:
        `linear-gradient(90deg, ${theme.grid} 1px, transparent 1px), linear-gradient(${theme.grid} 1px, transparent 1px)`,
      backgroundSize: '120px 120px',
    }}
  />
);

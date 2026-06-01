import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {CaptionCue, Scene} from '../types';

export const SubtitleOverlay: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const cue = activeCue(scene.captions || [], time);
  if (!cue) {
    return null;
  }

  const local = time - cue.start;
  const opacity = interpolate(local, [0, 0.18], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const y = interpolate(local, [0, 0.22], [18, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: 86,
        right: 86,
        bottom: 156,
        display: 'flex',
        justifyContent: 'center',
        pointerEvents: 'none',
        opacity,
        transform: `translateY(${y}px)`,
        zIndex: 20,
      }}
    >
      <div
        style={{
          maxWidth: 850,
          borderRadius: 8,
          border: `1px solid ${theme.border}`,
          background: 'rgba(13,17,23,0.82)',
          boxShadow: `0 18px 60px ${theme.shadow}`,
          padding: '18px 26px',
          color: theme.foreground,
          fontFamily: theme.fontFamily,
          fontSize: 34,
          fontWeight: 680,
          lineHeight: 1.22,
          textAlign: 'center',
          wordBreak: 'break-word',
          overflowWrap: 'anywhere',
        }}
      >
        <CaptionText cue={cue} />
      </div>
    </div>
  );
};

const activeCue = (cues: CaptionCue[], time: number): CaptionCue | null => {
  return cues.find((cue) => time >= cue.start && time <= cue.end) || null;
};

const CaptionText: React.FC<{cue: CaptionCue}> = ({cue}) => {
  const keywords = cue.keywords || [];
  if (!keywords.length) {
    return <>{cue.text}</>;
  }
  const pattern = new RegExp(`(${keywords.map(escapeRegExp).join('|')})`, 'gi');
  const parts = cue.text.split(pattern).filter(Boolean);
  return (
    <>
      {parts.map((part, index) =>
        keywords.some((keyword) => keyword.toLowerCase() === part.toLowerCase()) ? (
          <span key={`${part}-${index}`} style={{color: theme.accent}}>
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

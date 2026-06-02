import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {resolveAccent, theme} from '../styles/theme';
import type {Scene} from '../types';

export const HookScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const y = interpolate(frame, [0, 10], [18, 0], {extrapolateRight: 'clamp'});
  const accent = resolveAccent(scene.visual.accent_color);
  const headlineSize = hookHeadlineSize(scene.visual.headline);

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        padding: 88,
        fontFamily: theme.fontFamily,
        backgroundColor: theme.background,
        color: theme.foreground,
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${y}px)`,
          borderLeft: `8px solid ${accent}`,
          paddingLeft: 34,
        }}
      >
        <div
          style={{
            fontSize: headlineSize,
            fontWeight: 760,
            lineHeight: 1.04,
            letterSpacing: 0,
            overflowWrap: 'break-word',
            wordBreak: 'break-word',
          }}
        >
          {scene.visual.headline}
        </div>
        <div style={{height: 28}} />
        {scene.visual.bullets.slice(0, 2).map((bullet) => (
          <div key={bullet} style={{fontSize: 36, lineHeight: 1.35, color: theme.muted}}>
            {bullet}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const hookHeadlineSize = (text: string) => {
  const length = Array.from(text || '').length;
  if (length > 24) return 62;
  if (length > 16) return 72;
  return 86;
};

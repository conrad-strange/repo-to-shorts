import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';

export const TitleScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const y = interpolate(frame, [0, 10], [18, 0], {extrapolateRight: 'clamp'});
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        padding: 96,
        fontFamily: theme.fontFamily,
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      <div style={{fontSize: 84, fontWeight: 700, letterSpacing: 0, lineHeight: 1.06}}>
        {scene.visual.headline}
      </div>
      <div style={{height: 36}} />
      {scene.visual.bullets.map((bullet) => (
        <div
          key={bullet}
          style={{
            color: theme.muted,
            fontSize: 36,
            lineHeight: 1.4,
            maxWidth: 820,
          }}
        >
          {bullet}
        </div>
      ))}
    </AbsoluteFill>
  );
};

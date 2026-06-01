import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {accentOf, beatTiming, getBeats, HighlightText, SceneShell} from './sceneKit';

export const EvidenceGridScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const beats = getBeats(scene, 4);

  return (
    <SceneShell scene={scene} dense>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 18}}>
        {beats.map((beat, index) => {
          const timing = beatTiming(frame, fps, scene.duration, beat.start_ratio ?? index * 0.16);
          return (
            <div
              key={`${beat.text}-${index}`}
              style={{
                minHeight: 220,
                borderRadius: 8,
                border: `1px solid ${index === 0 ? accent : theme.border}`,
                background: 'rgba(22,27,34,0.86)',
                padding: 26,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                opacity: timing.opacity,
                transform: `translateY(${timing.y}px) scale(${timing.scale})`,
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 8,
                  background: index === 0 ? accent : 'rgba(240,246,252,0.08)',
                  color: index === 0 ? theme.background : theme.foreground,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 21,
                  fontWeight: 760,
                }}
              >
                {index + 1}
              </div>
              <div style={{fontSize: 30, fontWeight: 680, lineHeight: 1.2, wordBreak: 'break-word'}}>
                <HighlightText text={beat.text} accent={accent} />
              </div>
              <div style={{height: 4, width: '58%', borderRadius: 999, background: accent, opacity: 0.5}} />
            </div>
          );
        })}
      </div>
    </SceneShell>
  );
};

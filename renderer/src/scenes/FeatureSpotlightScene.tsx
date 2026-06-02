import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {accentOf, beatTiming, getBeats, HighlightText, SceneShell} from './sceneKit';

export const FeatureSpotlightScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const beats = getBeats(scene, 3);
  const sweep = interpolate(frame, [0, scene.duration * fps], [-260, 760], {
    extrapolateRight: 'clamp',
  });

  return (
    <SceneShell scene={scene}>
      <div style={{display: 'grid', gap: 20}}>
        {beats.map((beat, index) => {
          const timing = beatTiming(frame, fps, scene.duration, beat.start_ratio ?? index * 0.2);
          return (
            <div
              key={`${beat.text}-${index}`}
              style={{
                position: 'relative',
                minHeight: index === 0 ? 182 : 128,
                borderRadius: 8,
                border: `1px solid ${index === 0 ? accent : theme.border}`,
                background: index === 0 ? 'rgba(88,166,255,0.13)' : 'rgba(22,27,34,0.82)',
                overflow: 'hidden',
                padding: index === 0 ? '34px 36px' : '26px 32px',
                opacity: timing.opacity,
                transform: `translateY(${timing.y}px) scale(${timing.scale})`,
              }}
            >
              {index === 0 ? (
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    bottom: 0,
                    left: sweep,
                    width: 120,
                    background: `linear-gradient(90deg, transparent, ${accent}33, transparent)`,
                  }}
                />
              ) : null}
              <div style={{position: 'relative', color: theme.muted, fontSize: 22, marginBottom: 12}}>
                {index === 0 ? '核心亮点' : `可信证据 ${index + 1}`}
              </div>
              <div
                style={{
                  position: 'relative',
                  fontSize: index === 0 ? 46 : 34,
                  fontWeight: index === 0 ? 760 : 680,
                  lineHeight: 1.16,
                  wordBreak: 'break-word',
                }}
              >
                <HighlightText text={beat.text} accent={accent} />
              </div>
            </div>
          );
        })}
      </div>
    </SceneShell>
  );
};

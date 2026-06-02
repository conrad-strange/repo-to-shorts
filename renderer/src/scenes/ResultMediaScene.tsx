import React from 'react';
import {Easing, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../types';
import {theme} from '../styles/theme';
import {accentOf, SceneShell} from './sceneKit';

export const ResultMediaScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const asset = scene.visual.asset_path;
  const intro = spring({frame, fps, config: {damping: 18, stiffness: 110}});
  const y = interpolate(intro, [0, 1], [34, 0]);
  const scale = interpolate(frame, [0, scene.duration * fps], [1.015, 1.06], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const labelOpacity = interpolate(frame, [10, 22], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <SceneShell scene={scene} dense>
      <div
        style={{
          display: 'grid',
          gap: 24,
          transform: `translateY(${y}px)`,
        }}
      >
        <div
          style={{
            border: `1px solid ${theme.border}`,
            borderRadius: 14,
            background: 'rgba(22,27,34,0.86)',
            boxShadow: '0 34px 90px rgba(0,0,0,0.36)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: `1px solid ${theme.border}`,
              color: theme.muted,
              fontSize: 22,
              padding: '18px 22px',
            }}
          >
            <span>{scene.visual.caption || 'Result preview'}</span>
            <span style={{color: accent, fontWeight: 800}}>Live result</span>
          </div>
          <div
            style={{
              display: 'grid',
              placeItems: 'center',
              height: 820,
              overflow: 'hidden',
              background: '#010409',
            }}
          >
            {asset ? (
              <img
                src={staticFile(asset)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                  transform: `scale(${scale})`,
                }}
              />
            ) : (
              <div style={{color: theme.muted, fontSize: 34}}>No result image</div>
            )}
          </div>
        </div>
        <div
          style={{
            borderLeft: `4px solid ${accent}`,
            color: theme.foreground,
            fontSize: 34,
            fontWeight: 760,
            lineHeight: 1.22,
            opacity: labelOpacity,
            paddingLeft: 18,
          }}
        >
          {scene.visual.headline || '结果画面'}
        </div>
      </div>
    </SceneShell>
  );
};

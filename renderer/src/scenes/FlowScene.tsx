import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {accentOf, beatTiming, getBeats, SceneShell} from './sceneKit';

export const FlowScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const beats = getBeats(scene, 5);
  const nodes = (scene.visual.diagram_nodes.length ? scene.visual.diagram_nodes : beats.map((beat) => beat.text)).slice(0, 5);

  return (
    <SceneShell scene={scene} dense>
      <div style={{display: 'grid', gap: 18}}>
        {nodes.map((node, index) => {
          const timing = beatTiming(frame, fps, scene.duration, index * 0.14);
          const lineScale = interpolate(
            frame,
            [Math.round((index * 0.14 + 0.08) * scene.duration * fps), Math.round((index * 0.14 + 0.18) * scene.duration * fps)],
            [0, 1],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
          );

          return (
            <React.Fragment key={`${node}-${index}`}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '70px 1fr',
                  gap: 22,
                  alignItems: 'center',
                  opacity: timing.opacity,
                  transform: `translateY(${timing.y}px)`,
                }}
              >
                <div
                  style={{
                    width: 58,
                    height: 58,
                    borderRadius: 999,
                    background: index === 0 ? accent : 'rgba(240,246,252,0.08)',
                    border: `2px solid ${index === 0 ? accent : theme.border}`,
                    color: index === 0 ? '#0D1117' : theme.foreground,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 24,
                    fontWeight: 760,
                  }}
                >
                  {index + 1}
                </div>
                <div
                  style={{
                    minHeight: 108,
                    border: `1px solid ${theme.border}`,
                    borderRadius: 8,
                    background: 'rgba(22,27,34,0.78)',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '0 32px',
                    fontSize: 36,
                    fontWeight: 680,
                    lineHeight: 1.16,
                  }}
                >
                  {node}
                </div>
              </div>
              {index < nodes.length - 1 ? (
                <div
                  style={{
                    width: 2,
                    height: 34,
                    marginLeft: 28,
                    background: accent,
                    opacity: 0.45,
                    transformOrigin: 'top center',
                    transform: `scaleY(${lineScale})`,
                  }}
                />
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
    </SceneShell>
  );
};

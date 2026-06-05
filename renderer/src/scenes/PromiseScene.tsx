import React from 'react';
import {interpolate} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {BeatLine, beatsForScenePage, itemsForScenePage, SceneShell, useSceneMotion} from './sceneKit';

export const PromiseScene: React.FC<{scene: Scene}> = ({scene}) => {
  const motion = useSceneMotion(scene);
  const {accent, timingFrame, timingDuration, fps} = motion;
  const beats = beatsForScenePage(scene, motion, 3);
  const pageBullets = itemsForScenePage(scene, motion, scene.visual.bullets, 2);
  const lineWidth = interpolate(timingFrame, [8, 22], [0, 100], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <SceneShell scene={scene} motion={motion}>
      <div style={{display: 'grid', gap: 34}}>
        <div
          style={{
            height: 2,
            width: `${lineWidth}%`,
            background: accent,
          }}
        />
        <div style={{display: 'grid', gap: 30}}>
          {beats.map((beat, index) => (
            <BeatLine
              key={`${beat.text}-${index}`}
              beat={beat}
              index={index}
              scene={scene}
              accent={accent}
              frameOverride={timingFrame}
              durationOverride={timingDuration}
            />
          ))}
        </div>
        <div
          style={{
            marginTop: 26,
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 14,
          }}
        >
          {pageBullets.map((bullet, index) => {
            const opacity = interpolate(
              timingFrame,
              [
                Math.round((0.52 + index * 0.12) * timingDuration * fps),
                Math.round((0.52 + index * 0.12) * timingDuration * fps) + 8,
              ],
              [0, 1],
              {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
            );
            return (
              <div
                key={bullet}
                style={{
                  border: `1px solid ${theme.border}`,
                  borderRadius: 8,
                  background: 'rgba(22,27,34,0.7)',
                  padding: '24px 26px',
                  color: theme.muted,
                  fontSize: 25,
                  lineHeight: 1.28,
                  opacity,
                }}
              >
                {bullet}
              </div>
            );
          })}
        </div>
      </div>
    </SceneShell>
  );
};

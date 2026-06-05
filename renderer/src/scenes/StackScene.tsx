import React from 'react';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {beatsForScenePage, SceneShell, timingForMotion, useSceneMotion} from './sceneKit';

export const StackScene: React.FC<{scene: Scene}> = ({scene}) => {
  const motion = useSceneMotion(scene);
  const {accent} = motion;
  const beats = beatsForScenePage(scene, motion, 6);

  return (
    <SceneShell scene={scene} motion={motion}>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 18}}>
        {beats.map((beat, index) => {
          const timing = timingForMotion(motion, beat.start_ratio ?? index * 0.12);
          return (
            <div
              key={`${beat.text}-${index}`}
              style={{
                minHeight: 130,
                borderRadius: 8,
                border: `1px solid ${theme.border}`,
                background: index === 0 ? accent : 'rgba(22,27,34,0.78)',
                color: index === 0 ? '#0D1117' : theme.foreground,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                padding: '24px 28px',
                opacity: timing.opacity,
                transform: `translateY(${timing.y}px) scale(${timing.scale})`,
              }}
            >
              <div style={{fontSize: 34, fontWeight: 720, lineHeight: 1.1}}>{beat.text}</div>
              <div
                style={{
                  marginTop: 14,
                  width: '64%',
                  height: 4,
                  borderRadius: 999,
                  background: index === 0 ? 'rgba(13,17,23,0.42)' : accent,
                  opacity: index === 0 ? 1 : 0.38,
                }}
              />
            </div>
          );
        })}
      </div>
    </SceneShell>
  );
};

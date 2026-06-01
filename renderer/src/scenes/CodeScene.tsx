import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../types';
import {accentOf, BeatLine, getBeats, SceneShell} from './sceneKit';

export const CodeScene: React.FC<{scene: Scene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = accentOf(scene);
  const beats = getBeats(scene, 3);
  const code = scene.visual.code || beats.find((beat) => beat.kind === 'code')?.text || 'python app.py';
  const terminalOpacity = interpolate(frame, [4, 14], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const cursorOpacity = interpolate(frame % 28, [0, 14, 28], [1, 0.2, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <SceneShell scene={scene} dense>
      <div
        style={{
          borderRadius: 8,
          background: '#101010',
          color: '#F8FAFC',
          padding: '34px 36px',
          boxShadow: '0 30px 90px rgba(0,0,0,0.18)',
          opacity: terminalOpacity,
        }}
      >
        <div style={{display: 'flex', gap: 12, marginBottom: 30}}>
          <span style={{width: 14, height: 14, borderRadius: 999, background: '#FF5F57'}} />
          <span style={{width: 14, height: 14, borderRadius: 999, background: '#FFBD2E'}} />
          <span style={{width: 14, height: 14, borderRadius: 999, background: '#28C840'}} />
        </div>
        <pre
          style={{
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontSize: 35,
            lineHeight: 1.35,
            fontFamily: 'SFMono-Regular, Consolas, monospace',
          }}
        >
          <span style={{color: accent}}>$ </span>
          {code}
          <span style={{opacity: cursorOpacity}}>_</span>
        </pre>
      </div>
      <div style={{display: 'grid', gap: 24, marginTop: 42}}>
        {beats.slice(0, 2).map((beat, index) => (
          <BeatLine key={`${beat.text}-${index}`} beat={beat} index={index} scene={scene} accent={accent} />
        ))}
      </div>
    </SceneShell>
  );
};

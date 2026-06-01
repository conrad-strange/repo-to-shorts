import React from 'react';
import type {Scene} from '../types';
import {accentOf, BeatLine, getBeats, SceneShell} from './sceneKit';

export const StepsScene: React.FC<{scene: Scene}> = ({scene}) => {
  const accent = accentOf(scene);
  const beats = getBeats(scene, 4);

  return (
    <SceneShell scene={scene}>
      <div
        style={{
          display: 'grid',
          gap: 34,
          borderLeft: `2px solid ${accent}`,
          paddingLeft: 34,
        }}
      >
        {beats.map((beat, index) => (
          <BeatLine key={`${beat.text}-${index}`} beat={beat} index={index} scene={scene} accent={accent} />
        ))}
      </div>
    </SceneShell>
  );
};

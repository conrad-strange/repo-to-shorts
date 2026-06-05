import React from 'react';
import type {Scene} from '../types';
import {BeatLine, beatsForScenePage, SceneShell, useSceneMotion} from './sceneKit';

export const StepsScene: React.FC<{scene: Scene}> = ({scene}) => {
  const motion = useSceneMotion(scene);
  const {accent, timingFrame, timingDuration} = motion;
  const beats = beatsForScenePage(scene, motion, 4);

  return (
    <SceneShell scene={scene} motion={motion}>
      <div
        style={{
          display: 'grid',
          gap: 34,
          borderLeft: `2px solid ${accent}`,
          paddingLeft: 34,
        }}
      >
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
    </SceneShell>
  );
};

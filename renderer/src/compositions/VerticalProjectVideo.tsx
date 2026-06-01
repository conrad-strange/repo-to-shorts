import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {SceneRenderer} from '../scenes/SceneRenderer';
import {SubtitleOverlay} from '../scenes/SubtitleOverlay';
import {theme} from '../styles/theme';
import type {Storyboard} from '../types';

export const VerticalProjectVideo: React.FC<{storyboard: Storyboard; audioSrc?: string}> = ({
  storyboard,
  audioSrc,
}) => {
  const fps = storyboard.fps || 30;

  return (
    <AbsoluteFill style={{backgroundColor: theme.background, color: theme.foreground}}>
      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}
      {storyboard.scenes.map((scene) => (
        <Sequence
          key={scene.id}
          from={Math.round(scene.start * fps)}
          durationInFrames={Math.max(1, Math.round(scene.duration * fps))}
        >
          <SceneRenderer scene={scene} />
          <SubtitleOverlay scene={scene} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

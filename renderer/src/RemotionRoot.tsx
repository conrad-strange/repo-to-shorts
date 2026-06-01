import React from 'react';
import {Composition} from 'remotion';
import {VerticalProjectVideo} from './compositions/VerticalProjectVideo';
import sampleStoryboard from '../../examples/sample-storyboard.json';
import type {Storyboard} from './types';

const defaultStoryboard = sampleStoryboard as Storyboard;

const durationInFrames = (storyboard: Storyboard) =>
  Math.max(
    1,
    Math.ceil(
      storyboard.scenes.reduce((total, scene) => Math.max(total, scene.start + scene.duration), 0) *
        storyboard.fps,
    ),
  );

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="VerticalProjectVideo"
      component={VerticalProjectVideo}
      durationInFrames={durationInFrames(defaultStoryboard)}
      fps={defaultStoryboard.fps}
      width={defaultStoryboard.width}
      height={defaultStoryboard.height}
      defaultProps={{
        storyboard: defaultStoryboard,
        audioSrc: undefined,
      }}
      calculateMetadata={({props}) => {
        const storyboard = props.storyboard as Storyboard;
        return {
          durationInFrames: durationInFrames(storyboard),
          fps: storyboard.fps,
          width: storyboard.width,
          height: storyboard.height,
        };
      }}
    />
  );
};

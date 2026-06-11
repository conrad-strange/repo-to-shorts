import React from 'react';
import {CodeScene} from './CodeScene';
import {CtaScene} from './CtaScene';
import {EvidenceGridScene} from './EvidenceGridScene';
import {FeatureSpotlightScene} from './FeatureSpotlightScene';
import {FlowScene} from './FlowScene';
import {GithubHeroScene} from './GithubHeroScene';
import {HookScene} from './HookScene';
import {PromiseScene} from './PromiseScene';
import {ReadmeFocusScene} from './ReadmeFocusScene';
import {ResultMediaScene} from './ResultMediaScene';
import {StackScene} from './StackScene';
import {StepsScene} from './StepsScene';
import {TextScene} from './TextScene';
import {MotionAccentLayer} from './MotionAccentLayer';
import type {Scene} from '../types';

export const SceneRenderer: React.FC<{scene: Scene}> = ({scene}) => {
  const sceneNode = renderScene(scene);

  return (
    <>
      {sceneNode}
      <MotionAccentLayer scene={scene} />
    </>
  );
};

const renderScene = (scene: Scene) => {
  if (scene.visual.layout === 'hook') {
    return <HookScene scene={scene} />;
  }

  if (scene.visual.layout === 'github_hero') {
    return <GithubHeroScene scene={scene} />;
  }

  if (scene.visual.layout === 'readme_focus') {
    return <ReadmeFocusScene scene={scene} />;
  }

  if (scene.visual.layout === 'flow') {
    return <FlowScene scene={scene} />;
  }

  if (scene.visual.layout === 'architecture_map') {
    return <FlowScene scene={scene} />;
  }

  if (scene.visual.layout === 'feature_spotlight') {
    return <FeatureSpotlightScene scene={scene} />;
  }

  if (scene.visual.layout === 'evidence_grid') {
    return <EvidenceGridScene scene={scene} />;
  }

  if (scene.visual.layout === 'code') {
    return <CodeScene scene={scene} />;
  }

  if (scene.visual.layout === 'result_media') {
    return <ResultMediaScene scene={scene} />;
  }

  if (scene.visual.layout === 'stack') {
    return <StackScene scene={scene} />;
  }

  if (scene.visual.layout === 'steps') {
    return <StepsScene scene={scene} />;
  }

  if (scene.visual.layout === 'cta') {
    return <CtaScene scene={scene} />;
  }

  if (scene.visual.layout === 'title' || scene.visual.layout === 'text') {
    return <PromiseScene scene={scene} />;
  }

  return <TextScene scene={scene} />;
};

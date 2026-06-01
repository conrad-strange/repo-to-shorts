import React from 'react';
import {AbsoluteFill, staticFile} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';

export const EnhancedHtmlScene: React.FC<{scene: Scene}> = ({scene}) => {
  const src = scene.visual.enhanced_html;

  if (!src) {
    return null;
  }

  return (
    <AbsoluteFill>
      <iframe
        title={scene.id}
        src={staticFile(src)}
        style={{
          width: '100%',
          height: '100%',
          border: 0,
          display: 'block',
          background: theme.background,
        }}
      />
    </AbsoluteFill>
  );
};

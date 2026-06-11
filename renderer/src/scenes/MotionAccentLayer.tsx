import {Lottie, type LottieAnimationData} from '@remotion/lottie';
import React, {useEffect, useMemo, useState} from 'react';
import {
  AbsoluteFill,
  Img,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
} from 'remotion';
import {theme} from '../styles/theme';
import type {Scene} from '../types';
import {useSceneMotion} from './sceneKit';
import {motionAssetForScene, type MotionAssetDefinition} from './motionAssets';

export const MotionAccentLayer: React.FC<{scene: Scene}> = ({scene}) => {
  const asset = motionAssetForScene(scene);
  const motion = useSceneMotion(scene);

  if (!asset) {
    return null;
  }

  const localFrame = motion.pageState?.rawPageFrame ?? motion.frame;
  const localDuration = motion.pageState?.pageDuration ?? scene.duration;
  const durationFrames = Math.max(1, Math.round(localDuration * motion.fps));
  const delayRatio = clamp(scene.visual.motion_delay_ratio ?? 0.58, 0.18, 0.84);
  const enterStart = Math.min(durationFrames - 1, Math.max(6, Math.round(durationFrames * delayRatio)));
  const enterEnd = Math.min(durationFrames, enterStart + Math.round(motion.fps * 0.38));
  const exitStart = Math.max(enterEnd + 1, durationFrames - Math.round(motion.fps * 0.42));

  const enter = interpolate(localFrame, [enterStart, enterEnd], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const exit = interpolate(localFrame, [exitStart, durationFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const cycleFrames = Math.max(1, Math.round(motion.fps * (asset.kind === 'svg' ? 4 : 3.6)));
  const cycle = (localFrame % cycleFrames) / cycleFrames;
  const wave = Math.sin(cycle * Math.PI * 2);
  const floatY = wave * (asset.role === 'accent' ? 4 : 3);
  const entranceY = interpolate(enter, [0, 1], [8, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const graphicOpacity = asset.kind === 'svg' ? 0.9 + Math.sin((cycle + 0.22) * Math.PI * 2) * 0.06 : 1;
  const placement = placementFor(scene, asset);
  const opacity = enter * exit * asset.opacity;
  const frameStyle = frameStyleFor(asset);

  if (opacity <= 0.01) {
    return null;
  }

  return (
    <AbsoluteFill style={{pointerEvents: 'none', zIndex: 8}}>
      <div
        style={{
          position: 'absolute',
          ...placement,
          width: frameStyle.width,
          height: frameStyle.height,
          borderRadius: frameStyle.borderRadius,
          border: frameStyle.border,
          background: frameStyle.background,
          boxShadow: frameStyle.boxShadow,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity,
          transform: `translate3d(0, ${floatY + entranceY}px, 0)`,
          overflow: asset.role === 'accent' ? 'hidden' : 'visible',
          mixBlendMode: asset.role === 'hero_background' ? 'screen' : 'normal',
        }}
      >
        {asset.role === 'accent' ? (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: `radial-gradient(circle at 50% 50%, ${motion.accent}33, transparent 68%)`,
            }}
          />
        ) : null}
        <div
          style={{
            position: 'relative',
            zIndex: 1,
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: graphicOpacity,
            filter: asset.kind === 'lottie' ? lottieFilterFor(asset) : undefined,
          }}
        >
          <MotionGraphic asset={asset} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const MotionGraphic: React.FC<{asset: MotionAssetDefinition}> = ({asset}) => {
  if (asset.kind === 'lottie') {
    return <LottieGraphic path={asset.path} asset={asset} />;
  }

  return (
    <Img
      src={staticFile(asset.path)}
      style={{
        width: '62%',
        height: '62%',
        objectFit: 'contain',
        opacity: 0.96,
        filter: 'invert(1)',
      }}
    />
  );
};

const LottieGraphic: React.FC<{path: string; asset: MotionAssetDefinition}> = ({path, asset}) => {
  const [handle] = useState(() => delayRender(`Loading motion asset ${path}`));
  const [animationData, setAnimationData] = useState<LottieAnimationData | null>(null);
  const source = useMemo(() => staticFile(path), [path]);

  useEffect(() => {
    let cancelled = false;
    fetch(source)
      .then((response) => response.json())
      .then((json) => {
        if (!cancelled) {
          setAnimationData(json);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAnimationData(null);
        }
      })
      .finally(() => {
        continueRender(handle);
      });
    return () => {
      cancelled = true;
    };
  }, [handle, source]);

  if (!animationData) {
    return null;
  }

  return (
    <Lottie
      animationData={animationData}
      loop
      renderer="svg"
      style={{
        width: asset.role === 'accent' ? '78%' : '94%',
        height: asset.role === 'accent' ? '78%' : '94%',
      }}
    />
  );
};

const placementFor = (scene: Scene, asset: MotionAssetDefinition): React.CSSProperties => {
  if (asset.role === 'hero_background') {
    if (scene.visual.layout === 'architecture_map' || scene.visual.layout === 'flow') {
      return {right: -110, bottom: 270};
    }
    return {right: -120, bottom: 340};
  }
  if (asset.role === 'side_illustration') {
    if (scene.visual.layout === 'github_hero' || scene.visual.layout === 'hook') {
      return {right: 74, bottom: 342};
    }
    if (scene.visual.layout === 'code') {
      return {right: 66, bottom: 330};
    }
    return {right: 72, bottom: 312};
  }
  const commonRight = {right: 88, bottom: 292};
  if (scene.visual.layout === 'github_hero' || scene.visual.layout === 'hook') {
    return {right: 90, bottom: 360};
  }
  if (scene.visual.layout === 'cta') {
    return {right: 104, top: 330};
  }
  if (scene.visual.layout === 'code') {
    return {right: 92, bottom: 342};
  }
  if (scene.visual.layout === 'architecture_map' || scene.visual.layout === 'flow') {
    return {right: 82, bottom: 302};
  }
  if (scene.visual.layout === 'evidence_grid' || scene.visual.layout === 'readme_focus') {
    return {right: 94, bottom: 318};
  }
  if (asset.size >= 180) {
    return {right: 102, bottom: 330};
  }
  return commonRight;
};

const frameStyleFor = (asset: MotionAssetDefinition) => {
  if (asset.role === 'hero_background') {
    return {
      width: asset.size,
      height: Math.round(asset.size * 0.82),
      borderRadius: 0,
      border: 'none',
      background: 'transparent',
      boxShadow: 'none',
    };
  }
  if (asset.role === 'side_illustration') {
    return {
      width: asset.size,
      height: asset.size,
      borderRadius: 0,
      border: 'none',
      background: 'transparent',
      boxShadow: 'none',
    };
  }
  return {
    width: asset.size,
    height: asset.size,
    borderRadius: 38,
    border: `1px solid ${theme.border}`,
    background: 'rgba(22,27,34,0.46)',
    boxShadow: `0 22px 70px ${theme.shadow}`,
  };
};

const lottieFilterFor = (asset: MotionAssetDefinition) => {
  if (asset.role === 'hero_background') {
    return 'saturate(0.55) brightness(0.72) contrast(0.9) blur(0.2px)';
  }
  if (asset.role === 'side_illustration') {
    return 'saturate(0.68) brightness(0.82) contrast(0.94) drop-shadow(0 18px 44px rgba(0,0,0,0.36))';
  }
  return 'saturate(0.74) brightness(0.88) contrast(0.96)';
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

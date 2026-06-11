import type {MotionAsset, MotionRole, Scene} from '../types';

export type MotionAssetKind = 'svg' | 'lottie';

export interface MotionAssetDefinition {
  kind: MotionAssetKind;
  path: string;
  size: number;
  opacity: number;
  role: MotionRole;
}

const catalog: Record<Exclude<MotionAsset, 'none'>, MotionAssetDefinition> = {
  repo_pulse: {
    kind: 'svg',
    path: 'motion/repo_pulse.svg',
    size: 176,
    opacity: 0.72,
    role: 'accent',
  },
  data_flow: {
    kind: 'svg',
    path: 'motion/data_flow.svg',
    size: 164,
    opacity: 0.68,
    role: 'accent',
  },
  code_scan: {
    kind: 'svg',
    path: 'motion/code_scan.svg',
    size: 152,
    opacity: 0.7,
    role: 'accent',
  },
  evidence_pulse: {
    kind: 'svg',
    path: 'motion/evidence_pulse.svg',
    size: 160,
    opacity: 0.66,
    role: 'accent',
  },
  spark_burst: {
    kind: 'svg',
    path: 'motion/spark_burst.svg',
    size: 188,
    opacity: 0.72,
    role: 'accent',
  },
};

export const motionAssetForScene = (scene: Scene): MotionAssetDefinition | null => {
  if (scene.visual.layout === 'result_media') {
    return null;
  }
  if (scene.visual.motion_asset_path && scene.visual.motion_asset_kind && scene.visual.motion_asset_kind !== 'none') {
    const role = scene.visual.motion_role || 'side_illustration';
    return {
      kind: scene.visual.motion_asset_kind,
      path: scene.visual.motion_asset_path,
      role,
      size: role === 'hero_background' ? 660 : role === 'side_illustration' ? 430 : 176,
      opacity: role === 'hero_background' ? 0.28 : role === 'side_illustration' ? 0.78 : 0.7,
    };
  }
  const asset = scene.visual.motion_asset;
  if (!asset || asset === 'none') {
    return null;
  }
  return catalog[asset] || null;
};

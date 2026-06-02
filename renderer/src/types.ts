export type SceneLayout =
  | 'hook'
  | 'github_hero'
  | 'title'
  | 'text'
  | 'readme_focus'
  | 'feature_spotlight'
  | 'architecture_map'
  | 'evidence_grid'
  | 'code'
  | 'result_media'
  | 'flow'
  | 'stack'
  | 'steps'
  | 'cta';
export type SceneAnimation = 'fade' | 'slide' | 'rise' | 'zoom' | 'none';
export type MicroBeatKind = 'text' | 'metric' | 'code' | 'flow' | 'warning' | 'cta';
export type VisualAssetType = 'github_repo_home' | 'readme_focus' | 'none';
export type VisualFocusTarget = 'repo_name' | 'readme_title' | 'install_command' | 'readme_section' | 'none';

export interface MicroBeat {
  text: string;
  kind: MicroBeatKind;
  emphasis?: string | null;
  start_ratio: number;
}

export interface VisualSpec {
  layout: SceneLayout;
  headline: string;
  bullets: string[];
  code?: string | null;
  diagram_nodes: string[];
  icons: string[];
  accent_color: string;
  animation: SceneAnimation;
  micro_beats?: MicroBeat[];
  caption?: string | null;
  asset_type?: VisualAssetType;
  asset_path?: string | null;
  focus_target?: VisualFocusTarget;
  repo_url?: string | null;
  repo_display_url?: string | null;
  media_type?: 'image' | 'video' | 'none';
  evidence_refs?: string[];
}

export interface CaptionCue {
  start: number;
  end: number;
  text: string;
  keywords: string[];
  source_scene_id: string;
}

export interface Scene {
  id: string;
  type: string;
  start: number;
  duration: number;
  narration: string;
  visual: VisualSpec;
  evidence_keys?: string[];
  evidence_refs?: string[];
  captions?: CaptionCue[];
}

export interface Storyboard {
  title: string;
  aspect_ratio: '9:16';
  fps: number;
  width: number;
  height: number;
  scenes: Scene[];
}

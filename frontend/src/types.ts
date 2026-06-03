export type VideoMode = 'short_30s' | 'standard_60s' | 'technical_90s';
export type RenderProfile = 'preview' | 'final';
export type BrandMode = 'rs' | 'rb';

export interface VisualSpec {
  layout: string;
  headline: string;
  bullets: string[];
  code?: string | null;
  caption?: string | null;
  accent_color?: string;
  evidence_refs?: string[];
  diagram_nodes?: string[];
  icons?: string[];
  animation?: string;
  micro_beats?: unknown[];
  asset_type?: string;
  asset_path?: string | null;
  focus_target?: string;
  repo_url?: string | null;
  repo_display_url?: string | null;
  media_type?: 'image' | 'video' | 'none';
}

export interface Scene {
  id: string;
  type: string;
  start: number;
  duration: number;
  narration: string;
  visual: VisualSpec;
  evidence_refs?: string[];
}

export interface Storyboard {
  title: string;
  aspect_ratio: '9:16';
  fps: number;
  width: number;
  height: number;
  scenes: Scene[];
}

export interface RunFiles {
  video?: string | null;
  preview_grid?: string | null;
  script?: string | null;
  demo_report?: string | null;
  subtitles_srt?: string | null;
  subtitles_vtt?: string | null;
}

export interface RunDetail {
  project_id: string;
  run_id: string;
  project_root: string;
  run_dir: string;
  metadata: Record<string, unknown>;
  repo_summary?: Record<string, unknown> | null;
  script_markdown?: string | null;
  storyboard?: Storyboard | null;
  verification?: Record<string, unknown> | null;
  evaluation?: Record<string, unknown> | null;
  files: RunFiles;
}

export interface ProjectItem {
  id: string;
  path: string;
  runs: string[];
}

export interface WorkflowRequest {
  repo_url: string;
  output_name?: string;
  user_brief?: string;
  out_dir?: string;
  video_mode: VideoMode;
  storytelling_mode?: 'experience_first' | 'technical_explainer';
  render_strategy: string;
  render_profile: RenderProfile;
  brand_mode: BrandMode;
  bomb_circle?: string;
  bomb_again_count?: number;
  tts_voice?: string;
  dry_run: boolean;
  auto_repair: boolean;
  allow_unverified?: boolean;
  remotion_concurrency?: number;
}

export interface JobEvent {
  index?: number;
  type: 'queued' | 'progress' | 'succeeded' | 'failed' | string;
  step?: string;
  message?: string;
  percent?: number;
  result?: RunDetail;
  error?: string;
  status_code?: number;
}

export interface JobDetail {
  job_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | string;
  created_at: number;
  updated_at: number;
  result?: RunDetail | null;
  error?: string | null;
  events: JobEvent[];
  events_url: string;
}

export interface RerenderPayload {
  render_profile: string;
  brand_mode?: BrandMode;
  bomb_circle?: string;
  bomb_again_count?: number;
  tts_voice?: string;
  allow_unverified?: boolean;
  storyboard?: Storyboard;
}

export interface TtsPreviewResponse {
  audio: string;
  voice: string;
  text: string;
  rate: string;
}

export interface UserImageAssetResponse {
  asset_path: string;
  run_asset_path: string;
  bytes: number;
}

export interface UserVideoAssetResponse extends UserImageAssetResponse {
  start: number;
  end: number;
  duration: number;
  clips?: Array<{start: number; end: number; duration: number}>;
}

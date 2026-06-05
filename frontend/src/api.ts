import type {
  JobDetail,
  RerenderPayload,
  RunDetail,
  Storyboard,
  TtsPreviewResponse,
  UserImageAssetResponse,
  UserVideoAssetResponse,
  WorkflowRequest,
} from './types';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {'Content-Type': 'application/json', ...(options?.headers || {})},
    ...options,
  });
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    if (response.status === 405) {
      throw new Error(
        '请求方法不匹配。请刷新页面，或重启 gva ui 后打开 http://127.0.0.1:7860；如果正在使用 Vite dev，请确认后端 API 端口一致。',
      );
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

async function parseErrorDetail(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) return '';
  try {
    const payload = JSON.parse(text) as {detail?: unknown; message?: unknown};
    const detail = payload.detail ?? payload.message;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object' && 'msg' in item) return String((item as {msg: unknown}).msg);
          return '';
        })
        .filter(Boolean)
        .join('；');
    }
  } catch {
    return text;
  }
  return text;
}

export const api = {
  system: () => request<Record<string, unknown>>('/api/system'),
  projects: () => request<{projects: Array<{id: string; path: string; runs: string[]; run_labels?: Record<string, string>}>}>('/api/projects'),
  ttsPreview: (payload: {voice: string; text?: string; rate?: string}) =>
    request<TtsPreviewResponse>('/api/tts/preview', {method: 'POST', body: JSON.stringify(payload)}),
  createJob: (payload: WorkflowRequest) =>
    request<JobDetail>('/api/jobs', {method: 'POST', body: JSON.stringify(payload)}),
  jobDetail: (jobId: string) => request<JobDetail>(`/api/jobs/${jobId}`),
  createProject: (payload: WorkflowRequest) =>
    request<RunDetail>('/api/projects', {method: 'POST', body: JSON.stringify(payload)}),
  runDetail: (projectId: string, runId: string) =>
    request<RunDetail>(`/api/projects/${projectId}/runs/${runId}`),
  saveStoryboard: (projectId: string, runId: string, storyboard: Storyboard, activate = false) =>
    request<{saved: boolean}>(`/api/projects/${projectId}/runs/${runId}/storyboard`, {
      method: 'PUT',
      body: JSON.stringify({storyboard, activate}),
    }),
  uploadUserImage: (projectId: string, runId: string, payload: {filename: string; data_url: string}) =>
    request<UserImageAssetResponse>(`/api/projects/${projectId}/runs/${runId}/assets/user-image`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  uploadUserVideo: (
    projectId: string,
    runId: string,
    payload: {filename: string; file: File; start: number; end: number; clips?: Array<{start: number; end: number}>},
  ) => {
    const params = new URLSearchParams({
      filename: payload.filename,
      start: String(payload.start),
      end: String(payload.end),
    });
    if (payload.clips?.length) {
      params.set('clips', JSON.stringify(payload.clips));
    }
    return requestRaw<UserVideoAssetResponse>(
      `/api/projects/${projectId}/runs/${runId}/assets/user-video?${params.toString()}`,
      {
        method: 'POST',
        headers: {'Content-Type': payload.file.type || 'application/octet-stream'},
        body: payload.file,
      },
    );
  },
  rerender: (projectId: string, runId: string, payload: RerenderPayload) =>
    request<RunDetail>(`/api/projects/${projectId}/runs/${runId}/rerender`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  rerenderJob: (
    projectId: string,
    runId: string,
    payload: RerenderPayload,
  ) =>
    request<JobDetail>('/api/jobs/rerender', {
      method: 'POST',
      body: JSON.stringify({project_id: projectId, run_id: runId, ...payload}),
    }),
};

async function requestRaw<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

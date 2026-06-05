import {type PointerEvent, useEffect, useMemo, useRef, useState} from 'react';
import {api} from './api';
import type {
  BrandMode,
  JobDetail,
  JobEvent,
  ProjectItem,
  RenderProfile,
  RunDetail,
  Scene,
  Storyboard,
  VideoMode,
  VisualPage,
} from './types';

const videoModes: Array<{value: VideoMode; label: string; hint: string}> = [
  {value: 'short_30s', label: '30s', hint: '30-59s'},
  {value: 'standard_60s', label: '60s', hint: '60-89s'},
  {value: 'technical_90s', label: '90s', hint: '90-120s'},
];

const renderProfiles: Array<{value: RenderProfile; label: string; hint: string}> = [
  {value: 'preview', label: '快速预览', hint: '540x960 / 编辑看节奏'},
  {value: 'final', label: '最终版', hint: '1080x1920 / 发布导出'},
];

const ttsVoices = [
  {value: 'zh-CN-XiaoxiaoNeural', label: '晓晓 · 女声温暖', hint: '默认，稳妥清晰'},
  {value: 'zh-CN-YunyangNeural', label: '云扬 · 男声专业', hint: '工程项目感更强'},
  {value: 'zh-CN-YunxiNeural', label: '云希 · 男声活泼', hint: '更短视频化'},
  {value: 'zh-CN-XiaoyiNeural', label: '晓伊 · 女声活泼', hint: '更轻快'},
  {value: 'zh-CN-YunjianNeural', label: '云健 · 男声有力', hint: '冲击感更强'},
];

const defaultShortsVoice = 'zh-CN-XiaoxiaoNeural';
const defaultBombVoice = 'zh-CN-YunxiNeural';

const progressSteps = [
  {key: 'repo', label: '读取仓库', hint: 'Clone / README / 文件扫描'},
  {key: 'evidence', label: '提取证据', hint: 'README / 配置 / 核心代码'},
  {key: 'script', label: '生成讲稿', hint: '中文短视频脚本'},
  {key: 'storyboard', label: '生成分镜', hint: 'Scene / 视觉结构'},
  {key: 'verify', label: '校验修复', hint: 'Verifier / Repair'},
  {key: 'tts', label: '配音字幕', hint: 'TTS / captions'},
  {key: 'render', label: '视频渲染', hint: 'Remotion / MP4'},
] as const;

type ProgressStatus = 'idle' | 'running' | 'done' | 'blocked' | 'error';

interface ProgressState {
  status: ProgressStatus;
  percent: number;
  stepIndex: number;
  message: string;
}

interface VerificationClaimView {
  id: string;
  status: string;
  severity: string;
  text: string;
  reason: string;
}

interface VerificationDetailsSummary {
  supported: VerificationClaimView[];
  attention: VerificationClaimView[];
  total: number;
}

interface ClipRange {
  start: number;
  end: number;
}

export function App() {
  const [repoUrl, setRepoUrl] = useState('https://github.com/conrad-strange/repo-to-shorts');
  const [repoUrlTouched, setRepoUrlTouched] = useState(false);
  const [userBrief, setUserBrief] = useState('');
  const [videoMode, setVideoMode] = useState<VideoMode>('short_30s');
  const [renderProfile, setRenderProfile] = useState<RenderProfile>('preview');
  const [brandMode, setBrandMode] = useState<BrandMode>('rs');
  const [bombCircle, setBombCircle] = useState('科技圈');
  const [bombAgainCount, setBombAgainCount] = useState(1);
  const [ttsVoice, setTtsVoice] = useState('zh-CN-XiaoxiaoNeural');
  const [ttsVoiceTouched, setTtsVoiceTouched] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [system, setSystem] = useState<Record<string, unknown> | null>(null);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState<ProgressState>(() => idleProgress());
  const [draftStatus, setDraftStatus] = useState<'saved' | 'saving' | 'dirty' | 'error'>('saved');
  const [voicePreviewBusy, setVoicePreviewBusy] = useState(false);
  const [addSceneOpen, setAddSceneOpen] = useState(false);
  const [addSceneKind, setAddSceneKind] = useState<'code' | 'image' | 'video'>('code');
  const [addSceneTitle, setAddSceneTitle] = useState('代码 / 结果');
  const [addSceneNarration, setAddSceneNarration] = useState('这里展示项目中的一段关键代码或实际运行结果。');
  const [addSceneCode, setAddSceneCode] = useState("print('hello world')");
  const [addSceneImage, setAddSceneImage] = useState<File | null>(null);
  const [addSceneVideo, setAddSceneVideo] = useState<File | null>(null);
  const [addSceneVideoUrl, setAddSceneVideoUrl] = useState('');
  const [addSceneVideoDuration, setAddSceneVideoDuration] = useState(0);
  const [addSceneVideoStart, setAddSceneVideoStart] = useState(0);
  const [addSceneVideoEnd, setAddSceneVideoEnd] = useState(6);
  const [addSceneVideoClips, setAddSceneVideoClips] = useState<ClipRange[]>([]);
  const [addSceneBusy, setAddSceneBusy] = useState(false);
  const [visualItemsDraft, setVisualItemsDraft] = useState<{sceneId: string; value: string} | null>(null);
  const [visualPageItemsDraft, setVisualPageItemsDraft] = useState<{
    sceneId: string;
    pageIndex: number;
    value: string;
  } | null>(null);
  const jobSourceRef = useRef<EventSource | null>(null);
  const storyboardRef = useRef<Storyboard | null>(null);
  const clipVideoRef = useRef<HTMLVideoElement | null>(null);
  const clipDragTargetRef = useRef<'start' | 'end' | null>(null);

  useEffect(() => {
    api.system().then(setSystem).catch((error) => setMessage(error.message));
    refreshProjects();
  }, []);

  useEffect(() => {
    return () => jobSourceRef.current?.close();
  }, []);

  useEffect(() => {
    if (!addSceneVideo) {
      setAddSceneVideoUrl('');
      setAddSceneVideoDuration(0);
      return;
    }
    const url = URL.createObjectURL(addSceneVideo);
    setAddSceneVideoUrl(url);
    setAddSceneVideoStart(0);
    setAddSceneVideoEnd(6);
    setAddSceneVideoClips([]);
    return () => URL.revokeObjectURL(url);
  }, [addSceneVideo]);

  useEffect(() => {
    if (run?.storyboard) {
      storyboardRef.current = run.storyboard;
      setStoryboard(run.storyboard);
      setSelectedSceneId(run.storyboard.scenes[0]?.id ?? null);
      setDraftStatus('saved');
    }
    const runVoice = run?.metadata.tts_voice;
    if (typeof runVoice === 'string' && runVoice) {
      setTtsVoice(runVoice);
    }
    const runVideoMode = run?.metadata.video_mode;
    if (runVideoMode === 'short_30s' || runVideoMode === 'standard_60s' || runVideoMode === 'technical_90s') {
      setVideoMode(runVideoMode);
    }
    const runBrandMode = run?.metadata.brand_mode;
    if (runBrandMode === 'rs' || runBrandMode === 'rb') {
      setBrandMode(runBrandMode);
    }
    const runBombCircle = run?.metadata.bomb_circle;
    if (typeof runBombCircle === 'string' && runBombCircle) {
      setBombCircle(runBombCircle);
    }
    const runBombAgainCount = Number(run?.metadata.bomb_again_count);
    if (Number.isFinite(runBombAgainCount) && runBombAgainCount >= 1) {
      setBombAgainCount(Math.min(8, Math.max(1, Math.round(runBombAgainCount))));
    }
    const runUserBrief = run?.metadata.user_brief;
    setUserBrief(typeof runUserBrief === 'string' ? runUserBrief : '');
  }, [run]);

  const selectedScene = useMemo(() => {
    return storyboard?.scenes.find((scene) => scene.id === selectedSceneId) ?? storyboard?.scenes[0] ?? null;
  }, [storyboard, selectedSceneId]);
  const selectedCaptionPreview = useMemo(
    () => (selectedScene ? captionPreviewForScene(selectedScene) : []),
    [selectedScene],
  );
  const selectedVisualItems = useMemo(
    () => (selectedScene ? visualItemsForScene(selectedScene) : []),
    [selectedScene],
  );
  const selectedVisualPages = useMemo(
    () => (selectedScene ? visualPagesForScene(selectedScene) : []),
    [selectedScene],
  );
  const selectedVisibleTextPreview = useMemo(
    () => (selectedScene ? visibleTextPreviewForScene(selectedScene, run?.visible_text_manifest) : []),
    [selectedScene, run?.visible_text_manifest],
  );

  useEffect(() => {
    setVisualItemsDraft(null);
    setVisualPageItemsDraft(null);
  }, [selectedSceneId, run?.run_id]);

  async function refreshProjects() {
    try {
      const payload = await api.projects();
      setProjects(payload.projects);
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  function switchBrandMode(mode: BrandMode) {
    setBrandMode(mode);
    if (ttsVoiceTouched) return;
    if (mode === 'rb' && ttsVoice === defaultShortsVoice) {
      setTtsVoice(defaultBombVoice);
    }
    if (mode === 'rs' && ttsVoice === defaultBombVoice) {
      setTtsVoice(defaultShortsVoice);
    }
  }

  async function startWorkflow() {
    setRepoUrlTouched(true);
    if (repoValidation) {
      setProgress(errorProgress(repoValidation));
      setMessage(repoValidation);
      return;
    }
    setBusy(true);
    setProgress(startProgress(0));
    setMessage('开始生成视频...');
    try {
      const result = await api.createProject({
        repo_url: repoUrl,
        user_brief: cleanUserBrief(userBrief) || undefined,
        video_mode: videoMode,
        storytelling_mode: 'experience_first',
        render_strategy: 'remotion-primary',
        render_profile: renderProfile,
        brand_mode: brandMode,
        bomb_circle: bombCircle,
        bomb_again_count: bombAgainCount,
        tts_voice: ttsVoice,
        dry_run: dryRun,
        auto_repair: true,
      });
      setRun(result);
      setProgress(progressFromRun(result));
      setMessage(describeRunState(result).message);
      refreshProjects();
    } catch (error) {
      const errorMessage = (error as Error).message;
      setProgress(errorProgress(errorMessage));
      setMessage(errorMessage);
    } finally {
      setBusy(false);
    }
  }

  async function startWorkflowJob() {
    setRepoUrlTouched(true);
    if (repoValidation) {
      setProgress(errorProgress(repoValidation));
      setMessage(repoValidation);
      return;
    }
    setBusy(true);
    setProgress(startProgress(0));
    setMessage('正在提交后台生成任务...');
    try {
      const job = await api.createJob({
        repo_url: repoUrl,
        user_brief: cleanUserBrief(userBrief) || undefined,
        video_mode: videoMode,
        storytelling_mode: 'experience_first',
        render_strategy: 'remotion-primary',
        render_profile: renderProfile,
        brand_mode: brandMode,
        bomb_circle: bombCircle,
        bomb_again_count: bombAgainCount,
        tts_voice: ttsVoice,
        dry_run: dryRun,
        auto_repair: true,
      });
      subscribeToJob(job);
    } catch (error) {
      const errorMessage = (error as Error).message;
      setProgress(errorProgress(errorMessage));
      setMessage(errorMessage);
      setBusy(false);
    }
  }

  function subscribeToJob(job: JobDetail) {
    jobSourceRef.current?.close();
    setMessage(`后台任务 ${job.job_id} 已启动`);
    const source = new EventSource(job.events_url);
    jobSourceRef.current = source;
    let finished = false;

    const onProgress = (event: Event) => {
      const payload = parseJobEvent(event);
      setProgress(progressFromJobEvent(payload));
      if (payload.message) setMessage(payload.message);
    };

    source.addEventListener('queued', onProgress);
    source.addEventListener('progress', onProgress);
    source.addEventListener('succeeded', async (event) => {
      finished = true;
      const payload = parseJobEvent(event);
      const result = payload.result ?? (await api.jobDetail(job.job_id)).result;
      if (result) {
        setRun(result);
        setProgress(progressFromRun(result));
        setMessage(describeRunState(result).message);
      } else {
        setProgress({status: 'done', percent: 100, stepIndex: progressSteps.length - 1, message: '视频生成完成'});
        setMessage('视频生成完成');
      }
      source.close();
      jobSourceRef.current = null;
      setBusy(false);
      refreshProjects();
    });
    source.addEventListener('failed', (event) => {
      finished = true;
      const payload = parseJobEvent(event);
      const errorMessage = payload.error || payload.message || '后台生成任务失败。';
      setProgress(errorProgress(errorMessage));
      setMessage(errorMessage);
      source.close();
      jobSourceRef.current = null;
      setBusy(false);
    });
    source.onerror = async () => {
      if (finished) return;
      try {
        const detail = await api.jobDetail(job.job_id);
        if (detail.status === 'succeeded' && detail.result) {
          finished = true;
          setRun(detail.result);
          setProgress(progressFromRun(detail.result));
          setMessage(describeRunState(detail.result).message);
          source.close();
          jobSourceRef.current = null;
          setBusy(false);
          refreshProjects();
          return;
        }
        if (detail.status === 'failed') {
          finished = true;
          const errorMessage = detail.error || '后台生成任务失败。';
          setProgress(errorProgress(errorMessage));
          setMessage(errorMessage);
          source.close();
          jobSourceRef.current = null;
          setBusy(false);
          return;
        }
      } catch {
        // Keep the current progress visible; the job may still be running.
      }
      setMessage('进度连接中断，后台任务仍可能在运行。');
    };
  }

  async function loadRun(projectId: string, runId: string) {
    setBusy(true);
    try {
      const result = await api.runDetail(projectId, runId);
      setRun(result);
      setProgress(progressFromRun(result));
      setMessage(describeRunState(result).message);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function autoSaveStoryboardDraft(nextStoryboard = storyboardRef.current ?? storyboard): Promise<boolean> {
    if (!run || !nextStoryboard) return true;
    setDraftStatus('saving');
    try {
      await api.saveStoryboard(run.project_id, run.run_id, nextStoryboard, false);
      setDraftStatus('saved');
      return true;
    } catch (error) {
      setDraftStatus('error');
      setMessage((error as Error).message);
      return false;
    }
  }

  async function selectScene(sceneId: string) {
    if (sceneId === selectedSceneId) return;
    const saved = await autoSaveStoryboardDraft();
    if (!saved) return;
    setSelectedSceneId(sceneId);
  }

  async function rerender() {
    if (!run) return;
    const latestStoryboard = storyboardRef.current ?? storyboard;
    setBusy(true);
    setProgress(startProgress(5));
    setDraftStatus('saving');
    setMessage('正在保存当前编辑并创建新版 run...');
    try {
      const job = await api.rerenderJob(run.project_id, run.run_id, {
        render_profile: renderProfile,
        video_mode: videoMode,
        user_brief: cleanUserBrief(userBrief) || undefined,
        brand_mode: brandMode,
        bomb_circle: bombCircle,
        bomb_again_count: bombAgainCount,
        tts_voice: ttsVoice,
        storyboard: latestStoryboard ?? undefined,
      });
      setDraftStatus('saved');
      subscribeToJob(job);
    } catch (error) {
      const errorMessage = (error as Error).message;
      setProgress(errorProgress(errorMessage));
      setMessage(errorMessage);
      setDraftStatus('error');
      setBusy(false);
    }
  }

  function updateSelectedScene(patch: Partial<Scene>) {
    const currentStoryboard = storyboardRef.current ?? storyboard;
    const currentScene = currentStoryboard?.scenes.find((scene) => scene.id === selectedSceneId) ?? selectedScene;
    if (!currentStoryboard || !currentScene) return;
    const nextStoryboard = {
      ...currentStoryboard,
      scenes: currentStoryboard.scenes.map((scene) =>
        scene.id === currentScene.id ? {...scene, ...patch} : scene,
      ),
    };
    storyboardRef.current = nextStoryboard;
    setDraftStatus('dirty');
    setStoryboard(nextStoryboard);
  }

  function updateSelectedVisual(patch: Partial<Scene['visual']>) {
    if (!selectedScene) return;
    updateSelectedScene({visual: {...selectedScene.visual, ...patch}});
  }

  function updateSelectedVisualItems(items: string[]) {
    if (!selectedScene) return;
    const visual = {...selectedScene.visual};
    if (usesDiagramNodes(selectedScene)) {
      visual.diagram_nodes = items;
    } else if (usesMicroBeats(selectedScene)) {
      visual.micro_beats = items.map((text, index) => {
        const previous = microBeatAt(visual.micro_beats, index);
        return {
          ...previous,
          text,
          kind: previous.kind || 'text',
          start_ratio: typeof previous.start_ratio === 'number' ? previous.start_ratio : index * 0.18,
        };
      });
      visual.bullets = items;
    } else {
      visual.bullets = items;
    }
    updateSelectedScene({visual});
  }

  function updateSelectedVisualPages(pages: VisualPage[]) {
    if (!selectedScene) return;
    updateSelectedScene({visual: {...selectedScene.visual, visual_pages: pages}});
  }

  function updateSelectedVisualPage(index: number, patch: Partial<VisualPage>) {
    const pages = [...selectedVisualPages];
    const current = pages[index];
    if (!current) return;
    pages[index] = {...current, ...patch};
    updateSelectedVisualPages(pages);
  }

  function addVisualPage() {
    if (!selectedScene) return;
    const sourceItems = selectedVisualItems.length
      ? selectedVisualItems
      : ([selectedScene.visual.caption, selectedScene.visual.headline].filter(Boolean) as string[]);
    const page: VisualPage = {
      title: selectedScene.visual.headline || '新画面页',
      caption: selectedScene.visual.caption ?? '',
      items: sourceItems.slice(0, 3),
    };
    updateSelectedVisualPages([...selectedVisualPages, page]);
  }

  function syncFirstVisualPageFromScene() {
    if (!selectedScene || !selectedVisualPages.length) return;
    const pages = [...selectedVisualPages];
    const sourceItems = selectedVisualItems.length
      ? selectedVisualItems
      : ([selectedScene.visual.caption, selectedScene.visual.headline].filter(Boolean) as string[]);
    pages[0] = {
      ...pages[0],
      title: selectedScene.visual.headline || pages[0].title,
      caption: selectedScene.visual.caption ?? pages[0].caption ?? '',
      items: sourceItems.slice(0, 3),
    };
    updateSelectedVisualPages(pages);
  }

  function syncAllVisualPageCaptionsFromScene() {
    if (!selectedScene || !selectedVisualPages.length) return;
    const caption = selectedScene.visual.caption ?? '';
    updateSelectedVisualPages(selectedVisualPages.map((page) => ({...page, caption})));
  }

  function deleteVisualPage(index: number) {
    updateSelectedVisualPages(selectedVisualPages.filter((_, pageIndex) => pageIndex !== index));
  }

  function moveVisualPage(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= selectedVisualPages.length) return;
    const pages = [...selectedVisualPages];
    [pages[index], pages[target]] = [pages[target], pages[index]];
    updateSelectedVisualPages(pages);
  }

  function selectedVisualItemsText(): string {
    if (selectedScene && visualItemsDraft?.sceneId === selectedScene.id) {
      return visualItemsDraft.value;
    }
    return selectedVisualItems.join('\n');
  }

  function beginVisualItemsEdit() {
    if (!selectedScene) return;
    setVisualItemsDraft({sceneId: selectedScene.id, value: selectedVisualItems.join('\n')});
  }

  function changeVisualItemsText(value: string) {
    if (!selectedScene) return;
    setVisualItemsDraft({sceneId: selectedScene.id, value});
    updateSelectedVisualItems(textAreaLines(value));
  }

  function endVisualItemsEdit() {
    setVisualItemsDraft(null);
  }

  function visualPageItemsText(pageIndex: number, page: VisualPage): string {
    if (
      selectedScene &&
      visualPageItemsDraft?.sceneId === selectedScene.id &&
      visualPageItemsDraft.pageIndex === pageIndex
    ) {
      return visualPageItemsDraft.value;
    }
    return (page.items ?? []).join('\n');
  }

  function beginVisualPageItemsEdit(pageIndex: number, page: VisualPage) {
    if (!selectedScene) return;
    setVisualPageItemsDraft({sceneId: selectedScene.id, pageIndex, value: (page.items ?? []).join('\n')});
  }

  function changeVisualPageItemsText(pageIndex: number, value: string) {
    if (!selectedScene) return;
    setVisualPageItemsDraft({sceneId: selectedScene.id, pageIndex, value});
    updateSelectedVisualPage(pageIndex, {items: textAreaLines(value)});
  }

  function endVisualPageItemsEdit() {
    setVisualPageItemsDraft(null);
  }

  async function addCustomScene() {
    const currentStoryboard = storyboardRef.current ?? storyboard;
    if (!run || !currentStoryboard || !selectedScene) return;
    setAddSceneBusy(true);
    try {
      let assetPath: string | null = null;
      let mediaDuration: number | undefined;
      if (addSceneKind === 'image') {
        if (!addSceneImage) {
          setMessage('请先选择一张结果截图。');
          return;
        }
        const dataUrl = await readFileAsDataUrl(addSceneImage);
        const uploaded = await api.uploadUserImage(run.project_id, run.run_id, {
          filename: addSceneImage.name,
          data_url: dataUrl,
        });
        assetPath = uploaded.asset_path;
      }
      if (addSceneKind === 'video') {
        if (!addSceneVideo) {
          setMessage('请先选择一段录屏视频。');
          return;
        }
        if (addSceneVideoEnd <= addSceneVideoStart) {
          setMessage('视频结束时间必须大于开始时间。');
          return;
        }
        const uploaded = await api.uploadUserVideo(run.project_id, run.run_id, {
          filename: addSceneVideo.name,
          file: addSceneVideo,
          start: addSceneVideoStart,
          end: addSceneVideoEnd,
          clips: addSceneVideoClips.length ? addSceneVideoClips : undefined,
        });
        assetPath = uploaded.asset_path;
        mediaDuration = uploaded.duration;
      }
      const scene = createCustomScene({
        kind: addSceneKind,
        title: addSceneTitle,
        narration: addSceneNarration,
        code: addSceneCode,
        assetPath,
        mediaDuration,
      });
      const nextStoryboard = insertSceneAfter(currentStoryboard, recommendedInsertAfterSceneId(currentStoryboard), scene);
      storyboardRef.current = nextStoryboard;
      setStoryboard(nextStoryboard);
      setSelectedSceneId(scene.id);
      setDraftStatus('dirty');
      setAddSceneOpen(false);
      setMessage('已新增画面，点击“生成新版”会进入新的 run。');
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setAddSceneBusy(false);
    }
  }

  function handleClipLoaded() {
    const duration = Number.isFinite(clipVideoRef.current?.duration) ? clipVideoRef.current?.duration ?? 0 : 0;
    const safeDuration = Math.max(0, duration);
    setAddSceneVideoDuration(safeDuration);
    setAddSceneVideoStart(0);
    setAddSceneVideoEnd(Math.min(6, Math.max(2, safeDuration || 6)));
  }

  function handleClipPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (!addSceneVideoDuration) return;
    const seconds = secondsFromPointer(event, addSceneVideoDuration);
    clipDragTargetRef.current = Math.abs(seconds - addSceneVideoStart) <= Math.abs(seconds - addSceneVideoEnd) ? 'start' : 'end';
    event.currentTarget.setPointerCapture(event.pointerId);
    updateClipPoint(clipDragTargetRef.current, seconds);
  }

  function handleClipPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!clipDragTargetRef.current || !addSceneVideoDuration) return;
    updateClipPoint(clipDragTargetRef.current, secondsFromPointer(event, addSceneVideoDuration));
  }

  function handleClipPointerUp(event: PointerEvent<HTMLDivElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    clipDragTargetRef.current = null;
  }

  function updateClipPoint(target: 'start' | 'end', value: number) {
    const minClip = 2;
    const maxClip = 12;
    const duration = addSceneVideoDuration || Math.max(addSceneVideoEnd, 6);
    if (target === 'start') {
      const lower = Math.max(0, addSceneVideoEnd - maxClip);
      const upper = Math.max(0, addSceneVideoEnd - minClip);
      const next = roundOne(clampNumber(value, lower, upper));
      setAddSceneVideoStart(next);
      if (clipVideoRef.current) clipVideoRef.current.currentTime = next;
      return;
    }
    const lower = Math.min(duration, addSceneVideoStart + minClip);
    const upper = Math.min(duration, addSceneVideoStart + maxClip);
    const next = roundOne(clampNumber(value, lower, upper));
    setAddSceneVideoEnd(next);
    if (clipVideoRef.current) clipVideoRef.current.currentTime = Math.max(0, next - 0.4);
  }

  function addCurrentVideoClip() {
    const nextClip = {start: roundOne(addSceneVideoStart), end: roundOne(addSceneVideoEnd)};
    if (nextClip.end - nextClip.start < 2) {
      setMessage('每个视频片段至少需要 2 秒。');
      return;
    }
    const nextClips = [...addSceneVideoClips, nextClip].sort((left, right) => left.start - right.start);
    if (nextClips.length > 6) {
      setMessage('初版最多拼接 6 个片段。');
      return;
    }
    if (totalClipDuration(nextClips) > 24) {
      setMessage('多片段总时长请控制在 24 秒以内。');
      return;
    }
    setAddSceneVideoClips(nextClips);
  }

  function removeVideoClip(index: number) {
    setAddSceneVideoClips((clips) => clips.filter((_, clipIndex) => clipIndex !== index));
  }

  async function previewVoice() {
    setVoicePreviewBusy(true);
    try {
      const result = await api.ttsPreview({
        voice: ttsVoice,
        text: '今天来介绍一个 GitHub 项目。',
      });
      await new Audio(result.audio).play();
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setVoicePreviewBusy(false);
    }
  }

  const activeRunVideo = run?.files.video ?? undefined;
  const previewGrid = run?.files.preview_grid ?? undefined;
  const outputHint = buildOutputHint(run, activeRunVideo);
  const runState = describeRunState(run);
  const verificationSummary = summarizeVerification(run?.verification ?? null);
  const verificationDetails = summarizeVerificationDetails(run?.verification ?? null);
  const systemSummary = summarizeSystem(system);
  const headerMessage = progress.status === 'running' ? progress.message : message || 'Ready';
  const repoValidation = validateRepoUrl(repoUrl);

  const bombHookPreview = buildBombHook(bombCircle, bombAgainCount);

  return (
    <main className={`app-shell ${brandMode === 'rb' ? 'theme-bomb' : 'theme-shorts'}`}>
      <aside className="left-rail">
        <div className={`brand-switch ${brandMode === 'rb' ? 'is-bomb' : 'is-shorts'}`}>
          <button
            type="button"
            className={`brand-option rs ${brandMode === 'rs' ? 'active' : ''}`}
            onClick={() => switchBrandMode('rs')}
            aria-pressed={brandMode === 'rs'}
          >
            <span className="brand-mark r2s" aria-hidden="true" />
            <strong>R2S</strong>
            <small>Repo to Shorts</small>
          </button>
          <button
            type="button"
            className={`brand-option rb ${brandMode === 'rb' ? 'active' : ''}`}
            onClick={() => switchBrandMode('rb')}
            aria-pressed={brandMode === 'rb'}
          >
            <span className="brand-mark bomb">R2B</span>
            <strong>R2B</strong>
            <small>Repo to Bombs</small>
            <span className="hazard-icon" aria-hidden="true" />
          </button>
        </div>

        <section className="panel">
          <div className="section-title">输入 GitHub 仓库</div>
          <label>
            GitHub URL
            <input
              value={repoUrl}
              onChange={(event) => {
                setRepoUrlTouched(true);
                setRepoUrl(event.target.value);
              }}
              aria-invalid={Boolean(repoUrlTouched && repoValidation)}
              placeholder="https://github.com/owner/repo"
            />
            {repoUrlTouched && repoValidation ? <span className="field-error">{repoValidation}</span> : null}
          </label>
          <label>
            想突出什么？
            <textarea
              className="brief-input"
              value={userBrief}
              onChange={(event) => setUserBrief(event.target.value)}
              placeholder="比如：更适合短视频；上手简单；突出真实结果。"
              maxLength={500}
              rows={briefRows(userBrief)}
            />
            <span className="muted-copy">
              生成新视频时会优先影响讲法和侧重点；选择历史 run 后生成新版，会使用当前分镜编辑和左侧模式。
            </span>
            <div className="brief-chips" aria-label="快速添加侧重点">
              {['真实使用体验', '上手简单', '技术流程', '开源推广', '更适合短视频'].map((chip) => (
                <button key={chip} type="button" onClick={() => setUserBrief(appendBriefChip(userBrief, chip))}>
                  {chip}
                </button>
              ))}
            </div>
          </label>
        </section>

        <section className="panel compact">
          <div className="section-title">视频模式</div>
          <div className="segmented">
            {videoModes.map((mode) => (
              <button
                key={mode.value}
                className={videoMode === mode.value ? 'active' : ''}
                onClick={() => setVideoMode(mode.value)}
                title={mode.hint}
              >
                {mode.label}
              </button>
            ))}
          </div>
          <div className="section-title muted">TTS 音色</div>
          <div className="voice-row">
            <select
              value={ttsVoice}
              onChange={(event) => {
                setTtsVoiceTouched(true);
                setTtsVoice(event.target.value);
              }}
            >
              {ttsVoices.map((voice) => (
                <option key={voice.value} value={voice.value}>
                  {voice.label}
                </option>
              ))}
            </select>
            <button type="button" onClick={previewVoice} disabled={voicePreviewBusy}>
              {voicePreviewBusy ? '试听中' : '试听'}
            </button>
          </div>
          <p className="muted-copy voice-hint">
            {ttsVoices.find((voice) => voice.value === ttsVoice)?.hint ?? ttsVoice}
          </p>
          <div className="section-title muted">渲染速度</div>
          <div className="stacked-options">
            {renderProfiles.map((profile) => (
              <button
                key={profile.value}
                className={renderProfile === profile.value ? 'option active' : 'option'}
                onClick={() => setRenderProfile(profile.value)}
              >
                <span>{profile.label}</span>
                <small>{profile.hint}</small>
              </button>
            ))}
          </div>
          <label className="toggle">
            <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
            Dry run
            <InfoTip text="只生成脚本和分镜，不渲染视频。" />
          </label>
          <button className="primary" disabled={busy || Boolean(repoValidation)} onClick={startWorkflowJob}>
            {busy ? '运行中...' : '生成视频'}
          </button>
        </section>

        <section className="panel progress-panel">
          <div className="section-title">生成进度</div>
          <div className="progress-head">
            <span>{progress.message}</span>
            <strong>{Math.round(progress.percent)}%</strong>
          </div>
          <div className="progress-track" aria-label="生成进度">
            <div className={`progress-fill ${progress.status}`} style={{width: `${progress.percent}%`}} />
          </div>
          <div className="progress-steps">
            {progressSteps.map((step, index) => (
              <div key={step.key} className={`progress-step ${progressStepClass(progress, index)}`}>
                <span>{index + 1}</span>
                <div>
                  <strong>{step.label}</strong>
                  <small>{step.hint}</small>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="section-title">历史 Run</div>
          <div className="run-list">
            {projects.flatMap((project) =>
              project.runs.map((runId) => (
                <button key={`${project.id}-${runId}`} onClick={() => loadRun(project.id, runId)}>
                  <span>{project.id}</span>
                  <strong>{project.run_labels?.[runId] ?? runId}</strong>
                </button>
              )),
            )}
          </div>
        </section>
      </aside>

      <section className="stage">
        <header className="stage-header">
          <div>
            <p className="eyebrow">Video Preview</p>
            <h2>{storyboard?.title ?? '等待生成'}</h2>
            <p className="output-location" title={outputHint.path}>
              <span>{outputHint.label}</span>
              {outputHint.path}
            </p>
          </div>
          <div className="status-pill">{headerMessage}</div>
        </header>

        <div className="preview-layout">
          <div className="phone-frame">
            {activeRunVideo ? (
              <video src={activeRunVideo} controls />
            ) : previewGrid ? (
              <img src={previewGrid} alt="preview grid" />
            ) : (
              <div className="empty-preview">
                <span>{runState.shortLabel}</span>
                <p>{runState.detail}</p>
              </div>
            )}
          </div>

          <div className="storyboard-strip">
            <div className="section-title">分镜预览</div>
            {storyboard?.scenes.map((scene, index) => (
              <button
                key={scene.id}
                className={selectedScene?.id === scene.id ? 'scene-card active' : 'scene-card'}
                onClick={() => selectScene(scene.id)}
              >
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{scene.visual.headline || scene.type}</strong>
                  <small>
                    {scene.visual.layout} / {scene.duration.toFixed(1)}s
                  </small>
                </div>
              </button>
            )) ?? <p className="muted-copy">还没有 storyboard。</p>}
          </div>
        </div>
      </section>

      <aside className="right-rail">
        {brandMode === 'rb' ? (
          <section className="panel bomb-editor">
            <div className="bomb-editor-head">
              <div>
                <div className="section-title">Repo to Bombs</div>
                <p className="muted-copy">只改开场包装，项目事实仍按证据校验。</p>
              </div>
              <span className="bomb-badge">
                <span className="hazard-icon" aria-hidden="true" />
              </span>
            </div>
            <label>
              什么圈
              <input
                value={bombCircle}
                onChange={(event) => setBombCircle(cleanBombCircleInput(event.target.value))}
                placeholder="科技圈"
              />
            </label>
            <label>
              “又”字数量
              <input
                type="number"
                min="1"
                max="8"
                step="1"
                value={bombAgainCount}
                onChange={(event) => setBombAgainCount(clampAgainCount(Number(event.target.value)))}
              />
            </label>
            <div className="bomb-hook-preview">
              <small>开场固定为</small>
              <strong>{bombHookPreview}</strong>
              <small>默认 Yunxi 活泼音色，后端语速 +38%，开场约 3 秒。</small>
            </div>
          </section>
        ) : null}

        <section className="panel editor-panel">
          <div className="section-title">当前 Scene</div>
          {selectedScene ? (
            <>
              <div className="scene-intent-box">
                <label>
                  本次意图
                  <textarea
                    className="intent-input"
                    value={userBrief}
                    onChange={(event) => setUserBrief(event.target.value)}
                    placeholder="比如：更适合短视频；上手简单；突出真实结果。"
                    maxLength={500}
                    rows={briefRows(userBrief)}
                  />
                </label>
                <p>生成新视频会参与脚本和分镜；生成新版请直接改下面的画面和旁白字段。</p>
              </div>
              <label>
                标题
                <input
                  value={selectedScene.visual.headline}
                  onChange={(event) => updateSelectedVisual({headline: event.target.value})}
                />
              </label>
              <label>
                画面短句
                <input
                  value={selectedScene.visual.caption ?? ''}
                  onChange={(event) => updateSelectedVisual({caption: event.target.value})}
                />
              </label>
              <label>
                时长
                <input
                  type="number"
                  min="1"
                  step="0.25"
                  value={selectedScene.duration}
                  onChange={(event) => updateSelectedScene({duration: Number(event.target.value)})}
                />
              </label>
              <label>
                {visualItemsLabel(selectedScene)}
                <textarea
                  value={selectedVisualItemsText()}
                  onFocus={beginVisualItemsEdit}
                  onChange={(event) => changeVisualItemsText(event.target.value)}
                  onBlur={endVisualItemsEdit}
                />
                <span className="muted-copy voice-hint">{visualItemsHint(selectedScene)}</span>
              </label>
              <div className="visual-pages-editor">
                <div className="label-with-tip">
                  <span>视觉分页</span>
                  <InfoTip text="长旁白会在同一幕内切换这些画面页；存在分页时，视频主要使用这里的标题、短句和条目。" />
                </div>
                {selectedVisualPages.length ? (
                  <p className="muted-copy voice-hint">当前视频主要使用视觉分页文字；上方标题、短句和关键词作为兜底。</p>
                ) : (
                  <p className="muted-copy voice-hint">暂无分页。生成新版时后端会自动补分页，也可以先手动新增。</p>
                )}
                {selectedVisualPages.length ? (
                  <div className="visual-page-sync-actions">
                    <button type="button" onClick={syncFirstVisualPageFromScene}>
                      同步第一页
                    </button>
                    <button type="button" onClick={syncAllVisualPageCaptionsFromScene}>
                      同步全部短句
                    </button>
                  </div>
                ) : null}
                <div className="visual-page-list">
                  {selectedVisualPages.map((page, index) => (
                    <div key={`visual-page-${index}`} className="visual-page-card">
                      <div className="visual-page-head">
                        <strong>{String(index + 1).padStart(2, '0')}</strong>
                        <div className="visual-page-actions">
                          <button type="button" onClick={() => moveVisualPage(index, -1)} disabled={index === 0}>
                            ↑
                          </button>
                          <button
                            type="button"
                            onClick={() => moveVisualPage(index, 1)}
                            disabled={index === selectedVisualPages.length - 1}
                          >
                            ↓
                          </button>
                          <button type="button" onClick={() => deleteVisualPage(index)}>
                            删除
                          </button>
                        </div>
                      </div>
                      <label>
                        页标题
                        <input
                          value={page.title}
                          onChange={(event) => updateSelectedVisualPage(index, {title: event.target.value})}
                        />
                      </label>
                      <label>
                        页短句
                        <input
                          value={page.caption ?? ''}
                          onChange={(event) => updateSelectedVisualPage(index, {caption: event.target.value})}
                        />
                      </label>
                      <label>
                        页条目
                        <textarea
                          value={visualPageItemsText(index, page)}
                          onFocus={() => beginVisualPageItemsEdit(index, page)}
                          onChange={(event) => changeVisualPageItemsText(index, event.target.value)}
                          onBlur={endVisualPageItemsEdit}
                        />
                      </label>
                    </div>
                  ))}
                </div>
                <button type="button" className="secondary-action" onClick={addVisualPage}>
                  + 新增视觉页
                </button>
              </div>
              <label>
                旁白
                <textarea
                  className="large"
                  value={selectedScene.narration}
                  onChange={(event) => updateSelectedScene({narration: event.target.value})}
                />
              </label>
              <div className="caption-preview-box">
                <div className="label-with-tip">
                  <span>底部字幕预览</span>
                  <InfoTip text="视频底部字幕根据旁白自动生成；画面短句只影响画面里的小文案。" />
                </div>
                {selectedCaptionPreview.length ? (
                  <div className="caption-cue-list">
                    {selectedCaptionPreview.map((cue, index) => (
                      <div key={`${cue.start}-${cue.end}-${index}`} className="caption-cue-row">
                        <span>
                          {formatSeconds(cue.start)}-{formatSeconds(cue.end)}
                        </span>
                        <strong>{cue.text}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="muted-copy">暂无底部字幕。填写旁白后，生成视频时会自动切分。</p>
                )}
              </div>
              <div className="scene-tool-head">
                <button type="button" onClick={() => setAddSceneOpen((value) => !value)}>
                  + 新增代码 / 结果画面
                </button>
                <InfoTip text="建议放在项目价值、核心流程或使用方式之后；不要放在开场，也别放到结尾才展示。" />
              </div>
              {addSceneOpen ? (
                <div className="add-scene-panel">
                  <p className="muted-copy voice-hint">{recommendedInsertCopy(storyboard)}</p>
                  <div className="segmented">
                    <button
                      type="button"
                      className={addSceneKind === 'code' ? 'active' : ''}
                      onClick={() => setAddSceneKind('code')}
                    >
                      终端代码
                    </button>
                    <button
                      type="button"
                      className={addSceneKind === 'image' ? 'active' : ''}
                      onClick={() => setAddSceneKind('image')}
                    >
                      结果截图
                    </button>
                    <button
                      type="button"
                      className={addSceneKind === 'video' ? 'active' : ''}
                      onClick={() => setAddSceneKind('video')}
                    >
                      短视频
                    </button>
                  </div>
                  <label>
                    标题
                    <input value={addSceneTitle} onChange={(event) => setAddSceneTitle(event.target.value)} />
                  </label>
                  <label>
                    旁白
                    <textarea value={addSceneNarration} onChange={(event) => setAddSceneNarration(event.target.value)} />
                  </label>
                  {addSceneKind === 'code' ? (
                    <label>
                      代码 / 终端输出
                      <textarea
                        className="large"
                        value={addSceneCode}
                        onChange={(event) => setAddSceneCode(event.target.value)}
                      />
                    </label>
                  ) : null}
                  {addSceneKind === 'image' ? (
                    <label>
                      结果截图
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        onChange={(event) => setAddSceneImage(event.target.files?.[0] ?? null)}
                      />
                      <span className="muted-copy voice-hint">会保存到当前 run，并尽量压缩到最长边 1280。</span>
                    </label>
                  ) : null}
                  {addSceneKind === 'video' ? (
                    <div className="video-clip-fields">
                      <label>
                        录屏视频
                        <input
                          type="file"
                          accept="video/mp4,video/webm,video/quicktime,video/x-matroska"
                          onChange={(event) => setAddSceneVideo(event.target.files?.[0] ?? null)}
                        />
                        <span className="muted-copy voice-hint">上传长录屏后，拖动下方开始/结束针选择 2-12 秒片段。</span>
                      </label>
                      {addSceneVideoUrl ? (
                        <div className="clip-preview">
                          <video
                            ref={clipVideoRef}
                            src={addSceneVideoUrl}
                            controls
                            muted
                            className="clip-video"
                            onLoadedMetadata={handleClipLoaded}
                          />
                          <div
                            className="clip-timeline"
                            role="slider"
                            aria-label="选择视频片段"
                            aria-valuemin={0}
                            aria-valuemax={roundOne(addSceneVideoDuration)}
                            aria-valuetext={`${formatClipTime(addSceneVideoStart)} 到 ${formatClipTime(addSceneVideoEnd)}`}
                            onPointerDown={handleClipPointerDown}
                            onPointerMove={handleClipPointerMove}
                            onPointerUp={handleClipPointerUp}
                            onPointerCancel={handleClipPointerUp}
                          >
                            <div className="clip-track" />
                            <div
                              className="clip-selection"
                              style={{
                                left: `${clipPercent(addSceneVideoStart, addSceneVideoDuration)}%`,
                                width: `${clipPercent(addSceneVideoEnd - addSceneVideoStart, addSceneVideoDuration)}%`,
                              }}
                            />
                            <div
                              className="clip-pin start"
                              style={{left: `${clipPercent(addSceneVideoStart, addSceneVideoDuration)}%`}}
                            >
                              开始
                            </div>
                            <div
                              className="clip-pin end"
                              style={{left: `${clipPercent(addSceneVideoEnd, addSceneVideoDuration)}%`}}
                            >
                              结束
                            </div>
                          </div>
                          <div className="clip-meta">
                            <span>{formatClipTime(addSceneVideoStart)}</span>
                            <strong>{roundOne(addSceneVideoEnd - addSceneVideoStart)}s</strong>
                            <span>{formatClipTime(addSceneVideoEnd)}</span>
                          </div>
                          <button type="button" className="secondary-action" onClick={addCurrentVideoClip}>
                            + 添加当前片段
                          </button>
                          <div className="clip-list">
                            {addSceneVideoClips.length ? (
                              <>
                                <div className="clip-list-head">
                                  <span>拼接片段</span>
                                  <strong>{roundOne(totalClipDuration(addSceneVideoClips))}s</strong>
                                </div>
                                {addSceneVideoClips.map((clip, index) => (
                                  <div key={`${clip.start}-${clip.end}-${index}`} className="clip-list-item">
                                    <span>{String(index + 1).padStart(2, '0')}</span>
                                    <strong>
                                      {formatClipTime(clip.start)} - {formatClipTime(clip.end)}
                                    </strong>
                                    <button type="button" onClick={() => removeVideoClip(index)}>
                                      删除
                                    </button>
                                  </div>
                                ))}
                              </>
                            ) : (
                              <p className="muted-copy voice-hint">未添加片段时，会直接使用当前双针选择。</p>
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <button type="button" className="primary" onClick={addCustomScene} disabled={addSceneBusy}>
                    {addSceneBusy ? '添加中...' : '添加到建议位置'}
                  </button>
                </div>
              ) : null}
              <div className="button-row">
                <span className={`draft-status ${draftStatus}`} data-label={draftStatusLabel(draftStatus)}>
                  保存分镜
                </span>
                <button className="primary" onClick={rerender} disabled={busy}>
                  生成新版
                </button>
              </div>
            </>
          ) : (
            <p className="muted-copy">选择一个 scene 开始编辑。</p>
          )}
        </section>

        {selectedScene ? (
          <details className="panel visible-text-preview-box visible-text-dropdown">
            <summary>
              <span className="visible-text-summary-title">
                <span className="visible-text-chevron">›</span>
                本幕实际显示文字
              </span>
              <span className="visible-text-summary-meta">{selectedVisibleTextPreview.length} 条</span>
            </summary>
            <div className="visible-text-dropdown-body">
              <p className="muted-copy voice-hint">这里不包含底部字幕；底部字幕只来自旁白。</p>
              {selectedVisibleTextPreview.length ? (
                <div className="visible-text-list">
                  {selectedVisibleTextPreview.map((entry, index) => (
                    <div key={`${entry.source}-${entry.text}-${index}`} className="visible-text-row">
                      <span>{entry.source}</span>
                      <strong>{entry.text}</strong>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted-copy voice-hint">当前没有额外画面文字；只会显示模板安全占位和底部字幕。</p>
              )}
            </div>
          </details>
        ) : null}

        <section className="panel">
          <div className="section-title">TTS / 校验</div>
          <dl className="kv">
            <dt>模式</dt>
            <dd>{String(run?.metadata.video_mode ?? videoMode)}</dd>
            <dt>渲染</dt>
            <dd>{String(run?.metadata.render_profile ?? renderProfile)}</dd>
            <dt>音色</dt>
            <dd>{String(run?.metadata.tts_voice ?? ttsVoice)}</dd>
            <dt>Verifier</dt>
            <dd>{verificationSummary.passedLabel}</dd>
            <dt>评分</dt>
            <dd className="value-with-tip">
              {String(run?.metadata.evaluation_score ?? '-')}
              <InfoTip text="内部健康分：按产物、节奏、字幕和9:16规则扣分。" />
            </dd>
          </dl>
          <div className="summary-card">
            <div className={verificationSummary.passed ? 'summary-status ok' : 'summary-status warn'}>
              {verificationSummary.passedLabel}
            </div>
            <div className="summary-grid">
              <span>{verificationSummary.supportedCount} 条 supported</span>
              <span>{verificationSummary.highRiskCount} 条需关注</span>
            </div>
            {run?.verification ? (
              <details className="details-block">
                <summary>查看详细证据</summary>
                <VerificationDetails details={verificationDetails} />
              </details>
            ) : (
              <p className="muted-copy">生成后显示校验结果。</p>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="section-title">系统状态</div>
          <div className="system-list">
            {systemSummary.map((item) => (
              <div key={item.label} className="system-row">
                <span>{item.label}</span>
                <strong className={item.ok ? 'ok-text' : item.optional ? 'muted-text' : 'warn-text'}>{item.value}</strong>
              </div>
            ))}
          </div>
          {system ? (
            <details className="details-block">
              <summary>查看环境详情</summary>
              <pre className="report compact small">{JSON.stringify(system, null, 2)}</pre>
            </details>
          ) : null}
        </section>
      </aside>
    </main>
  );
}

function InfoTip({text}: {text: string}) {
  return (
    <span className="info-tip" data-tooltip={text} aria-label={text} tabIndex={0}>
      !
    </span>
  );
}

function VerificationDetails({details}: {details: VerificationDetailsSummary}) {
  if (details.total === 0) {
    return <p className="muted-copy">还没有可展示的校验证据。</p>;
  }
  return (
    <div className="verification-list">
      <VerificationGroup title="需关注" count={details.attention.length} claims={details.attention} />
      <VerificationGroup title="Supported" count={details.supported.length} claims={details.supported} />
    </div>
  );
}

function VerificationGroup({
  title,
  count,
  claims,
}: {
  title: string;
  count: number;
  claims: VerificationClaimView[];
}) {
  return (
    <div className="verification-group">
      <div className="verification-group-title">
        <strong>{title}</strong>
        <span>{count} 条</span>
      </div>
      {claims.length ? (
        claims.slice(0, 6).map((claim) => <VerificationClaimCard key={claim.id} claim={claim} />)
      ) : (
        <p className="muted-copy">没有相关条目。</p>
      )}
    </div>
  );
}

function VerificationClaimCard({claim}: {claim: VerificationClaimView}) {
  return (
    <div className={`verification-claim ${claim.status}`}>
      <div className="verification-claim-head">
        <span>{claim.status}</span>
        <small>{claim.severity}</small>
      </div>
      <p>{claim.text}</p>
      <small>{claim.reason}</small>
    </div>
  );
}

function buildOutputHint(run: RunDetail | null, videoUrl?: string) {
  if (!run) {
    return {label: '输出', path: '生成后显示本地视频路径'};
  }
  if (videoUrl) {
    return {
      label: '视频',
      path: joinRunPath(run.run_dir, artifactPathFromUrl(videoUrl, 'video.mp4')),
    };
  }
  return {label: '输出目录', path: run.run_dir};
}

function artifactPathFromUrl(url: string, fallback: string) {
  const marker = '/files/';
  const index = url.indexOf(marker);
  if (index < 0) return fallback;
  return decodeURIComponent(url.slice(index + marker.length)).replace(/\//g, '\\');
}

function joinRunPath(runDir: string, artifactPath: string) {
  const separator = runDir.includes('\\') ? '\\' : '/';
  const cleanRunDir = runDir.replace(/[\\/]+$/, '');
  const cleanArtifact = artifactPath.replace(/^[\\/]+/, '');
  return `${cleanRunDir}${separator}${cleanArtifact}`;
}

function createCustomScene(options: {
  kind: 'code' | 'image' | 'video';
  title: string;
  narration: string;
  code: string;
  assetPath: string | null;
  mediaDuration?: number;
}): Scene {
  const id = `user-${options.kind}-${Date.now().toString(36)}`;
  const title = options.title.trim() || (options.kind === 'code' ? '代码片段' : '真实结果');
  const sceneDuration =
    options.kind === 'video'
      ? clampNumber(roundOne((options.mediaDuration || 6) + 0.4), 3, 24)
      : options.kind === 'code'
        ? 4.5
        : 5;
  return {
    id,
    type: options.kind === 'code' ? 'code' : 'result_media',
    start: 0,
    duration: sceneDuration,
    narration: options.narration.trim() || '这里展示项目中的一段真实操作、关键代码或实际运行结果。',
    visual: {
      layout: options.kind === 'code' ? 'code' : 'result_media',
      headline: title,
      caption: options.kind === 'code' ? 'Terminal output' : options.kind === 'video' ? 'Demo clip' : 'Result preview',
      bullets: [title],
      code: options.kind === 'code' ? compactCodeSnippet(options.code) : null,
      asset_path: options.assetPath,
      asset_type: 'none',
      focus_target: 'none',
      media_type: options.kind === 'video' ? 'video' : options.kind === 'image' ? 'image' : 'none',
      animation: 'rise',
      motion_asset: 'none',
      motion_delay_ratio: 0.48,
    },
  };
}

function recommendedInsertAfterSceneId(storyboard: Storyboard): string {
  if (storyboard.scenes.length >= 5) return storyboard.scenes[2].id;
  if (storyboard.scenes.length >= 3) return storyboard.scenes[1].id;
  return storyboard.scenes[0]?.id ?? '';
}

function recommendedInsertCopy(storyboard: Storyboard | null): string {
  if (!storyboard?.scenes.length) return '建议：生成分镜后，把真实使用画面放在开场之后、结尾之前。';
  const index = storyboard.scenes.findIndex((scene) => scene.id === recommendedInsertAfterSceneId(storyboard));
  return `建议插入位置：第 ${Math.max(1, index + 1)} 幕之后，避开开场和结尾。`;
}

function insertSceneAfter(storyboard: Storyboard, sceneId: string, newScene: Scene): Storyboard {
  const index = storyboard.scenes.findIndex((scene) => scene.id === sceneId);
  const insertAt = index >= 0 ? index + 1 : Math.max(1, storyboard.scenes.length - 1);
  const scenes = [...storyboard.scenes.slice(0, insertAt), newScene, ...storyboard.scenes.slice(insertAt)];
  let current = 0;
  return {
    ...storyboard,
    scenes: scenes.map((scene) => {
      const next = {...scene, start: Number(current.toFixed(2))};
      current += scene.duration;
      return next;
    }),
  };
}

function compactCodeSnippet(value: string) {
  const lines = value.split(/\r?\n/).slice(0, 8).map((line) => line.slice(0, 80));
  return lines.join('\n').trim() || "print('hello world')";
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('图片读取失败。'));
    reader.readAsDataURL(file);
  });
}

function secondsFromPointer(event: PointerEvent<HTMLDivElement>, duration: number): number {
  const rect = event.currentTarget.getBoundingClientRect();
  if (!rect.width) return 0;
  const ratio = (event.clientX - rect.left) / rect.width;
  return clampNumber(ratio * duration, 0, duration);
}

function clipPercent(value: number, duration: number): number {
  if (!duration) return 0;
  return clampNumber((value / duration) * 100, 0, 100);
}

function totalClipDuration(clips: ClipRange[]): number {
  return clips.reduce((total, clip) => total + Math.max(0, clip.end - clip.start), 0);
}

function formatClipTime(seconds: number): string {
  const safe = Math.max(0, seconds || 0);
  const minutes = Math.floor(safe / 60);
  const rest = Math.floor(safe % 60);
  const tenth = Math.floor((safe % 1) * 10);
  return `${minutes}:${String(rest).padStart(2, '0')}.${tenth}`;
}

function clampNumber(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

function roundOne(value: number): number {
  return Math.round((value || 0) * 10) / 10;
}

function parseJobEvent(event: Event): JobEvent {
  try {
    const data = event instanceof MessageEvent ? event.data : '{}';
    return JSON.parse(data) as JobEvent;
  } catch {
    return {type: event.type, message: '无法解析进度事件。'};
  }
}

function progressFromJobEvent(event: JobEvent): ProgressState {
  const stepIndex = stepIndexFromStepKey(event.step) ?? stepIndexFromPercent(event.percent ?? 0);
  return {
    status: event.type === 'failed' ? 'error' : 'running',
    percent: Math.max(0, Math.min(100, event.percent ?? progressPercentForStep(stepIndex))),
    stepIndex,
    message: event.message || progressSteps[stepIndex]?.hint || '生成中...',
  };
}

function stepIndexFromStepKey(step?: string): number | null {
  if (!step) return null;
  const normalized = step.toLowerCase();
  const index = progressSteps.findIndex((item) => item.key === normalized);
  if (index >= 0) return index;
  if (normalized.includes('queued') || normalized.includes('repo')) return 0;
  if (normalized.includes('evidence') || normalized.includes('insight')) return 1;
  if (normalized.includes('script')) return 2;
  if (normalized.includes('storyboard') || normalized.includes('visual')) return 3;
  if (normalized.includes('verify') || normalized.includes('repair')) return 4;
  if (normalized.includes('tts') || normalized.includes('caption')) return 5;
  if (normalized.includes('render') || normalized.includes('done')) return 6;
  return null;
}

function draftStatusLabel(status: 'saved' | 'saving' | 'dirty' | 'error'): string {
  if (status === 'saving') return '自动保存中';
  if (status === 'dirty') return '草稿未保存';
  if (status === 'error') return '保存失败';
  return '草稿已保存';
}

function describeRunState(run: RunDetail | null): {message: string; shortLabel: string; detail: string} {
  if (!run) {
    return {
      message: 'Ready',
      shortLabel: '9:16',
      detail: '生成后会显示手机视频预览',
    };
  }
  const label = runDisplayLabel(run);
  if (run.files.video) {
    return {
      message: `Run ${label} rendered`,
      shortLabel: 'MP4',
      detail: '视频已生成，可以在手机预览区播放',
    };
  }
  const nextStep = String(run.metadata.next_step ?? '');
  const reason = String(run.metadata.next_step_requires ?? '');
  if (nextStep || reason) {
    return {
      message: `Run ${label} stopped at ${nextStep || 'workflow'}`,
      shortLabel: nextStep || 'STOP',
      detail: reason || '当前 run 还没有生成 video.mp4',
    };
  }
  return {
    message: `Run ${label} has no video yet`,
    shortLabel: 'NO MP4',
    detail: '当前 run 还没有生成 video.mp4',
  };
}

function runDisplayLabel(run: RunDetail): string {
  if (run.run_label) return run.run_label;
  if (run.run_id.includes('+')) return run.run_id;
  const suffix = videoModeSuffix(run.metadata.video_mode);
  return suffix ? `${run.run_id}+${suffix}` : run.run_id;
}

function videoModeSuffix(videoMode: unknown): string | null {
  if (videoMode === 'short_30s') return '30s';
  if (videoMode === 'standard_60s') return '60s';
  if (videoMode === 'technical_90s') return '90s';
  return null;
}

function idleProgress(): ProgressState {
  return {
    status: 'idle',
    percent: 0,
    stepIndex: 0,
    message: '等待生成',
  };
}

function startProgress(startStepIndex: number): ProgressState {
  const safeIndex = Math.max(0, Math.min(progressSteps.length - 1, startStepIndex));
  return {
    status: 'running',
    percent: Math.max(3, progressPercentForStep(safeIndex)),
    stepIndex: safeIndex,
    message: progressSteps[safeIndex].hint,
  };
}

function progressFromRun(run: RunDetail): ProgressState {
  const runState = describeRunState(run);
  if (run.files.video) {
    return {
      status: 'done',
      percent: 100,
      stepIndex: progressSteps.length - 1,
      message: '视频已生成',
    };
  }

  const nextStep = String(run.metadata.next_step ?? '');
  const blockedIndex = stepIndexFromNextStep(nextStep);
  return {
    status: nextStep ? 'blocked' : 'idle',
    percent: nextStep ? Math.max(8, progressPercentForStep(blockedIndex)) : 0,
    stepIndex: blockedIndex,
    message: runState.detail,
  };
}

function errorProgress(message: string): ProgressState {
  return {
    status: 'error',
    percent: 100,
    stepIndex: 0,
    message,
  };
}

function progressStepClass(progress: ProgressState, index: number): string {
  if (progress.status === 'done') return 'done';
  if (progress.status === 'error' && index === progress.stepIndex) return 'error';
  if (progress.status === 'blocked' && index === progress.stepIndex) return 'blocked';
  if (index < progress.stepIndex) return 'done';
  if (index === progress.stepIndex && progress.status === 'running') return 'current';
  return 'pending';
}

function stepIndexFromPercent(percent: number): number {
  const bucket = Math.floor((Math.max(0, Math.min(99, percent)) / 100) * progressSteps.length);
  return Math.max(0, Math.min(progressSteps.length - 1, bucket));
}

function progressPercentForStep(stepIndex: number): number {
  return Math.round((Math.max(0, stepIndex) / progressSteps.length) * 100);
}

function progressIncrement(percent: number): number {
  if (percent < 20) return 6;
  if (percent < 50) return 4;
  if (percent < 75) return 2.5;
  return 1.2;
}

function stepIndexFromNextStep(nextStep: string): number {
  const normalized = nextStep.toLowerCase();
  if (normalized.includes('verification')) return 4;
  if (normalized.includes('tts')) return 5;
  if (normalized.includes('render')) return 6;
  if (normalized.includes('storyboard')) return 3;
  if (normalized.includes('script')) return 2;
  if (normalized.includes('insight') || normalized.includes('evidence')) return 1;
  return 0;
}

function validateRepoUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '请输入 GitHub 仓库链接。';
  if (/\s/.test(trimmed)) return '仓库链接不能包含空格。';
  if (/[<>{}[\]|\\^`"'，。；：]/.test(trimmed)) return '仓库链接包含非法字符，请粘贴完整 GitHub URL。';
  if (!/^https:\/\/github\.com\//i.test(trimmed)) {
    return '请输入以 https://github.com/ 开头的公开仓库链接。';
  }
  if (!/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?\/?$/i.test(trimmed)) {
    return '链接格式应为 https://github.com/owner/repo。';
  }
  return '';
}

function briefRows(value: string): number {
  const lineCount = value.split(/\r?\n/).length;
  const visualLength = Array.from(value).length;
  return Math.round(clampNumber(Math.max(2, lineCount + Math.floor(visualLength / 42)), 2, 5));
}

function visualItemsForScene(scene: Scene): string[] {
  const diagramNodes = scene.visual.diagram_nodes ?? [];
  const bullets = scene.visual.bullets ?? [];
  if (usesDiagramNodes(scene) && diagramNodes.length) return diagramNodes;
  if (usesMicroBeats(scene)) {
    const beats = microBeatTexts(scene.visual.micro_beats);
    if (beats.length) return beats;
  }
  if (bullets.length) return bullets;
  if (diagramNodes.length) return diagramNodes;
  return [];
}

function visualPagesForScene(scene: Scene): VisualPage[] {
  return (scene.visual.visual_pages ?? [])
    .map((page) => ({
      title: String(page.title ?? ''),
      caption: page.caption ?? '',
      items: Array.isArray(page.items) ? page.items.map((item) => String(item)).filter(Boolean) : [],
    }))
    .filter((page) => page.title.trim() || page.caption?.trim() || page.items.length);
}

function visibleTextPreviewForScene(
  scene: Scene,
  manifest?: RunDetail['visible_text_manifest'] | null,
): Array<{source: string; text: string}> {
  const manifestScene = manifest?.scenes?.find((item) => item.scene_id === scene.id);
  if (manifestScene) {
    return manifestScene.entries
      .filter((entry) => entry.text?.trim() && !entry.allowed_from_narration)
      .map((entry) => ({source: visibleTextSourceLabel(entry.source), text: entry.text.trim()}));
  }

  const pages = visualPagesForScene(scene);
  const entries: Array<{source: string; text: string}> = [];
  const add = (source: string, text: unknown) => {
    const value = String(text ?? '').trim();
    if (!value) return;
    entries.push({source, text: value});
  };

  if (pages.length) {
    pages.forEach((page, pageIndex) => {
      const label = `视觉页 ${String(pageIndex + 1).padStart(2, '0')}`;
      add(`${label} 标题`, page.title);
      add(`${label} 短句`, page.caption);
      page.items.forEach((item, itemIndex) => add(`${label} 条目 ${itemIndex + 1}`, item));
    });
  } else {
    add('标题', scene.visual.headline);
    add('画面短句', scene.visual.caption);
    visualItemsForScene(scene).forEach((item, index) => add(`${visualItemsLabel(scene)} ${index + 1}`, item));
    add('代码/结果', scene.visual.code);
  }

  const seen = new Set<string>();
  return entries.filter((entry) => {
    const key = `${entry.source}:${entry.text}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function visibleTextSourceLabel(source: string): string {
  const pageMatch = source.match(/^visual\.visual_pages\[(\d+)]\.(title|caption|items\[(\d+)])$/);
  if (pageMatch) {
    const page = `视觉页 ${String(Number(pageMatch[1]) + 1).padStart(2, '0')}`;
    if (pageMatch[2] === 'title') return `${page} 标题`;
    if (pageMatch[2] === 'caption') return `${page} 短句`;
    return `${page} 条目 ${Number(pageMatch[3]) + 1}`;
  }
  const beatMatch = source.match(/^visual\.micro_beats\[(\d+)]\.(text|emphasis)$/);
  if (beatMatch) {
    return beatMatch[2] === 'emphasis' ? `画面标签 ${Number(beatMatch[1]) + 1} 补充` : `画面标签 ${Number(beatMatch[1]) + 1}`;
  }
  const bulletMatch = source.match(/^visual\.bullets\[(\d+)]$/);
  if (bulletMatch) return `画面关键词 ${Number(bulletMatch[1]) + 1}`;
  const nodeMatch = source.match(/^visual\.diagram_nodes\[(\d+)]$/);
  if (nodeMatch) return `流程节点 ${Number(nodeMatch[1]) + 1}`;
  if (source === 'visual.headline') return '标题';
  if (source === 'visual.caption') return '画面短句';
  if (source === 'visual.code') return '代码/结果';
  return source.replace(/^visual\./, '');
}

function textAreaLines(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function visualItemsLabel(scene: Scene): string {
  if (usesDiagramNodes(scene)) return '画面流程节点';
  if (usesMicroBeats(scene)) return '画面标签';
  return '画面关键词';
}

function visualItemsHint(scene: Scene): string {
  if (scene.visual.layout === 'github_hero') return '对应仓库卡片右侧的小标签，例如“真实仓库 / 证据校验”。';
  if (usesDiagramNodes(scene)) return '对应流程图节点，可写成“标题：一句说明”。';
  if (usesMicroBeats(scene)) return '对应画面中的亮点卡片或证据卡片。';
  return '对应画面上的短关键词，完整解释放在旁白和底部字幕里。';
}

function usesDiagramNodes(scene: Scene): boolean {
  return ['architecture_map', 'flow'].includes(scene.visual.layout);
}

function usesMicroBeats(scene: Scene): boolean {
  if ((scene.visual.micro_beats ?? []).length > 0) return true;
  return ['github_hero', 'feature_spotlight', 'evidence_grid'].includes(scene.visual.layout);
}

type EditableMicroBeat = {
  text?: string;
  kind?: string;
  emphasis?: string | null;
  start_ratio?: number;
};

function microBeatAt(value: unknown[] | undefined, index: number): EditableMicroBeat {
  const candidate = value?.[index];
  return candidate && typeof candidate === 'object' ? (candidate as EditableMicroBeat) : {};
}

function microBeatTexts(value: unknown[] | undefined): string[] {
  return (value ?? [])
    .map((item) => (item && typeof item === 'object' && 'text' in item ? String((item as {text?: unknown}).text ?? '') : ''))
    .map((text) => text.trim())
    .filter(Boolean);
}

function captionPreviewForScene(scene: Scene): Array<{start: number; end: number; text: string}> {
  const existing = scene.captions || [];
  if (existing.length) {
    return existing
      .filter((cue) => cue.text?.trim())
      .map((cue) => ({start: cue.start, end: cue.end, text: cue.text.trim()}));
  }
  const parts = splitCaptionPreview(scene.narration);
  if (!parts.length) return [];
  const duration = Math.max(0.6, Number(scene.duration) || 3);
  const weightTotal = parts.reduce((sum, part) => sum + Math.max(part.length, 6), 0);
  let cursor = 0;
  return parts.map((part, index) => {
    const start = cursor;
    const end =
      index === parts.length - 1
        ? duration
        : Math.min(duration, cursor + Math.max(0.75, (duration * Math.max(part.length, 6)) / weightTotal));
    cursor = end;
    return {start: roundOne(start), end: roundOne(end), text: part};
  });
}

function splitCaptionPreview(text: string): string[] {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) return [];
  const rough = cleaned.split(/(?<=[。！？!?；;])/).filter(Boolean);
  const parts = rough.flatMap((part) => wrapCaptionPreview(part.trim(), 34));
  return parts.slice(0, 8);
}

function wrapCaptionPreview(text: string, maxLength: number): string[] {
  const tokens = text.match(/[A-Za-z0-9][A-Za-z0-9_+#./:-]*|\s+|./g) || [];
  const lines: string[] = [];
  let current = '';
  for (const token of tokens) {
    if (/^\s+$/.test(token)) {
      if (current && !current.endsWith(' ')) current += ' ';
      continue;
    }
    if ((current + token).trim().length <= maxLength) {
      current += token;
      continue;
    }
    if (current.trim()) lines.push(current.trim());
    current = token.length > maxLength ? token.slice(0, maxLength) : token;
  }
  if (current.trim()) lines.push(current.trim());
  return lines;
}

function formatSeconds(value: number): string {
  return `${Math.max(0, value).toFixed(1)}s`;
}

function cleanUserBrief(value: string): string {
  return value.replace(/[<>{}[\]|\\^`]/g, '').replace(/\s+/g, ' ').trim().slice(0, 500);
}

function appendBriefChip(current: string, chip: string): string {
  const cleaned = cleanUserBrief(current);
  if (!cleaned) return chip;
  if (cleaned.includes(chip)) return cleaned;
  return `${cleaned}；${chip}`;
}

function buildBombHook(circle: string, againCount: number): string {
  return `${normalizeBombCircle(circle)}今天${'又'.repeat(clampAgainCount(againCount))}炸了！`;
}

function normalizeBombCircle(value: string): string {
  const cleaned = cleanBombCircleInput(value).trim() || '科技圈';
  return cleaned.endsWith('圈') ? cleaned : `${cleaned}圈`;
}

function cleanBombCircleInput(value: string): string {
  return value.replace(/[<>{}[\]|\\^`"'，。；：\s]/g, '').slice(0, 10);
}

function clampAgainCount(value: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.max(1, Math.min(8, Math.round(value)));
}

function summarizeVerification(verification: Record<string, unknown> | null): {
  passed: boolean;
  passedLabel: string;
  supportedCount: number;
  highRiskCount: number;
} {
  if (!verification) {
    return {passed: false, passedLabel: '等待校验', supportedCount: 0, highRiskCount: 0};
  }

  const claims = Array.isArray(verification.claims) ? (verification.claims as Array<Record<string, unknown>>) : [];
  const scriptClaims = claims.filter((claim) => claim.source === 'script');
  const primaryClaims = scriptClaims.length ? scriptClaims : claims;
  const supportedCount = primaryClaims.filter((claim) => claim.status === 'supported').length;
  const highRiskCount = claims.filter(
    (claim) => claim.severity === 'high' && (claim.status === 'unsupported' || claim.status === 'weak'),
  ).length;
  const passed = Boolean(verification.passed);
  return {
    passed,
    passedLabel: passed ? '校验通过' : '有校验提示',
    supportedCount,
    highRiskCount,
  };
}

function summarizeVerificationDetails(verification: Record<string, unknown> | null): VerificationDetailsSummary {
  if (!verification) {
    return {supported: [], attention: [], total: 0};
  }
  const claims = Array.isArray(verification.claims) ? (verification.claims as Array<Record<string, unknown>>) : [];
  const normalized = claims.map((claim, index) => ({
    id: String(claim.id ?? `claim-${index + 1}`),
    status: String(claim.status ?? 'unknown'),
    severity: String(claim.severity ?? 'low'),
    text: compactText(String(claim.text ?? ''), 92),
    reason: compactText(String(claim.reason ?? '暂无原因说明。'), 110),
  }));
  return {
    supported: normalized.filter((claim) => claim.status === 'supported'),
    attention: normalized.filter((claim) => claim.status !== 'supported'),
    total: normalized.length,
  };
}

function compactText(value: string, maxLength: number): string {
  const cleaned = value.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= maxLength) return cleaned;
  return `${cleaned.slice(0, Math.max(0, maxLength - 1))}…`;
}

function summarizeSystem(system: Record<string, unknown> | null): Array<{
  label: string;
  value: string;
  ok: boolean;
  optional?: boolean;
}> {
  if (!system) {
    return [
      {label: 'Node', value: '检测中', ok: false, optional: true},
      {label: 'FFmpeg', value: '检测中', ok: false, optional: true},
      {label: 'Browser', value: '检测中', ok: false, optional: true},
      {label: 'Renderer', value: '检测中', ok: false, optional: true},
    ];
  }

  const node = system.node as Record<string, unknown> | undefined;
  const candidates = Array.isArray(node?.candidates) ? (node?.candidates as Array<Record<string, unknown>>) : [];
  const nodeOk = candidates.some((candidate) => candidate.ok_for_vite === true);
  const tools = (system.tools as Record<string, unknown> | undefined) ?? {};
  const ffmpeg = tools.ffmpeg_exe as Record<string, unknown> | undefined;
  const browser = tools.browser_exe as Record<string, unknown> | undefined;
  const chrome = (browser?.exists ? browser : tools.chrome_exe) as Record<string, unknown> | undefined;
  const rendererDir = tools.renderer_dir;

  return [
    {label: 'Node', value: nodeOk ? 'OK' : '异常', ok: nodeOk},
    {label: 'FFmpeg', value: ffmpeg?.exists ? 'OK' : '未配置', ok: Boolean(ffmpeg?.exists)},
    {
      label: 'Browser',
      value: chrome?.exists ? 'OK' : '未配置',
      ok: Boolean(chrome?.exists),
      optional: !chrome?.exists,
    },
    {label: 'Renderer', value: rendererDir ? 'OK' : '异常', ok: Boolean(rendererDir)},
  ];
}

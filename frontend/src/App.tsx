import {useEffect, useMemo, useRef, useState} from 'react';
import {api} from './api';
import type {BrandMode, JobDetail, JobEvent, ProjectItem, RenderProfile, RunDetail, Scene, Storyboard, VideoMode} from './types';

const videoModes: Array<{value: VideoMode; label: string; hint: string}> = [
  {value: 'short_30s', label: '30s', hint: '痛点、价值、CTA'},
  {value: 'standard_60s', label: '60s', hint: '增加流程和用法'},
  {value: 'technical_90s', label: '90s', hint: '加入代码细节'},
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

export function App() {
  const [repoUrl, setRepoUrl] = useState('https://github.com/conrad-strange/repo-to-shorts');
  const [repoUrlTouched, setRepoUrlTouched] = useState(false);
  const [outputName, setOutputName] = useState('conrad-strange-repo-to-shorts');
  const [outputNameTouched, setOutputNameTouched] = useState(false);
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
  const [addSceneKind, setAddSceneKind] = useState<'code' | 'image'>('code');
  const [addSceneTitle, setAddSceneTitle] = useState('代码 / 结果');
  const [addSceneNarration, setAddSceneNarration] = useState('这里展示项目中的一段关键代码或实际运行结果。');
  const [addSceneCode, setAddSceneCode] = useState("print('hello world')");
  const [addSceneImage, setAddSceneImage] = useState<File | null>(null);
  const [addSceneBusy, setAddSceneBusy] = useState(false);
  const jobSourceRef = useRef<EventSource | null>(null);
  const storyboardRef = useRef<Storyboard | null>(null);

  useEffect(() => {
    api.system().then(setSystem).catch((error) => setMessage(error.message));
    refreshProjects();
  }, []);

  useEffect(() => {
    return () => jobSourceRef.current?.close();
  }, []);

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
  }, [run]);

  useEffect(() => {
    if (outputNameTouched) return;
    const inferred = inferOutputName(repoUrl);
    if (inferred) {
      setOutputName(inferred);
    }
  }, [repoUrl, outputNameTouched]);

  const selectedScene = useMemo(() => {
    return storyboard?.scenes.find((scene) => scene.id === selectedSceneId) ?? storyboard?.scenes[0] ?? null;
  }, [storyboard, selectedSceneId]);

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
    if (outputNameValidation) {
      setProgress(errorProgress(outputNameValidation));
      setMessage(outputNameValidation);
      return;
    }
    setBusy(true);
    setProgress(startProgress(0));
    setMessage('开始生成视频...');
    try {
      const result = await api.createProject({
        repo_url: repoUrl,
        output_name: outputName || undefined,
        video_mode: videoMode,
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
    if (outputNameValidation) {
      setProgress(errorProgress(outputNameValidation));
      setMessage(outputNameValidation);
      return;
    }
    setBusy(true);
    setProgress(startProgress(0));
    setMessage('正在提交后台生成任务...');
    try {
      const job = await api.createJob({
        repo_url: repoUrl,
        output_name: outputName || undefined,
        video_mode: videoMode,
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

  async function addCustomScene() {
    const currentStoryboard = storyboardRef.current ?? storyboard;
    if (!run || !currentStoryboard || !selectedScene) return;
    setAddSceneBusy(true);
    try {
      let assetPath: string | null = null;
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
      const scene = createCustomScene({
        kind: addSceneKind,
        title: addSceneTitle,
        narration: addSceneNarration,
        code: addSceneCode,
        assetPath,
      });
      const nextStoryboard = insertSceneAfter(currentStoryboard, selectedScene.id, scene);
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
  const outputNameValidation = validateOutputName(outputName);

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
            输出名
            <input
              value={outputName}
              onChange={(event) => {
                setOutputNameTouched(true);
                setOutputName(event.target.value);
              }}
              aria-invalid={Boolean(outputNameValidation)}
            />
            {outputNameValidation ? <span className="field-error">{outputNameValidation}</span> : null}
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
          <button className="primary" disabled={busy || Boolean(repoValidation) || Boolean(outputNameValidation)} onClick={startWorkflowJob}>
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
                  <strong>{runId}</strong>
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
              <label>
                标题
                <input
                  value={selectedScene.visual.headline}
                  onChange={(event) => updateSelectedVisual({headline: event.target.value})}
                />
              </label>
              <label>
                短字幕
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
                画面关键词
                <textarea
                  value={selectedScene.visual.bullets.join('\n')}
                  onChange={(event) =>
                    updateSelectedVisual({
                      bullets: event.target.value
                        .split('\n')
                        .map((line) => line.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </label>
              <label>
                旁白
                <textarea
                  className="large"
                  value={selectedScene.narration}
                  onChange={(event) => updateSelectedScene({narration: event.target.value})}
                />
              </label>
              <div className="scene-tool-head">
                <button type="button" onClick={() => setAddSceneOpen((value) => !value)}>
                  + 新增代码 / 结果画面
                </button>
                <InfoTip text="建议放在项目价值、核心流程或使用方式之后；不要放在开场，也别放到结尾才展示。" />
              </div>
              {addSceneOpen ? (
                <div className="add-scene-panel">
                  <div className="segmented two">
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
                  ) : (
                    <label>
                      结果截图
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        onChange={(event) => setAddSceneImage(event.target.files?.[0] ?? null)}
                      />
                      <span className="muted-copy voice-hint">会保存到当前 run，并尽量压缩到最长边 1280。</span>
                    </label>
                  )}
                  <button type="button" className="primary" onClick={addCustomScene} disabled={addSceneBusy}>
                    {addSceneBusy ? '添加中...' : '添加到当前 scene 后面'}
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
  kind: 'code' | 'image';
  title: string;
  narration: string;
  code: string;
  assetPath: string | null;
}): Scene {
  const id = `user-${options.kind}-${Date.now().toString(36)}`;
  const title = options.title.trim() || (options.kind === 'code' ? '代码片段' : '结果画面');
  return {
    id,
    type: options.kind === 'code' ? 'code' : 'result_media',
    start: 0,
    duration: options.kind === 'code' ? 4.5 : 5,
    narration: options.narration.trim() || '这里展示项目中的一段关键代码或实际运行结果。',
    visual: {
      layout: options.kind === 'code' ? 'code' : 'result_media',
      headline: title,
      caption: options.kind === 'code' ? 'Terminal output' : 'Result preview',
      bullets: [title],
      code: options.kind === 'code' ? compactCodeSnippet(options.code) : null,
      asset_path: options.assetPath,
      asset_type: 'none',
      focus_target: 'none',
      media_type: options.kind === 'image' ? 'image' : 'none',
      animation: 'rise',
    },
  };
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
  if (run.files.video) {
    return {
      message: `Run ${run.run_id} rendered`,
      shortLabel: 'MP4',
      detail: '视频已生成，可以在手机预览区播放',
    };
  }
  const nextStep = String(run.metadata.next_step ?? '');
  const reason = String(run.metadata.next_step_requires ?? '');
  if (nextStep || reason) {
    return {
      message: `Run ${run.run_id} stopped at ${nextStep || 'workflow'}`,
      shortLabel: nextStep || 'STOP',
      detail: reason || '当前 run 还没有生成 video.mp4',
    };
  }
  return {
    message: `Run ${run.run_id} has no video yet`,
    shortLabel: 'NO MP4',
    detail: '当前 run 还没有生成 video.mp4',
  };
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

function validateOutputName(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '输出名不能为空。';
  if (!/^[A-Za-z0-9._-]+$/.test(trimmed)) {
    return '输出名只能包含字母、数字、点、下划线和短横线。';
  }
  return '';
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

function inferOutputName(repoUrl: string): string {
  const match = repoUrl.trim().match(/^https:\/\/github\.com\/([^/\s]+)\/([^/\s#?]+?)(?:\.git)?(?:[/?#].*)?$/i);
  if (!match) return '';
  const owner = sanitizeName(match[1]);
  const repo = sanitizeName(match[2]);
  return owner && repo ? `${owner}-${repo}` : repo || owner;
}

function sanitizeName(value: string): string {
  return value.replace(/\.git$/i, '').replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
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
      {label: 'Chrome', value: '检测中', ok: false, optional: true},
      {label: 'Renderer', value: '检测中', ok: false, optional: true},
    ];
  }

  const node = system.node as Record<string, unknown> | undefined;
  const candidates = Array.isArray(node?.candidates) ? (node?.candidates as Array<Record<string, unknown>>) : [];
  const nodeOk = candidates.some((candidate) => candidate.ok_for_vite === true);
  const tools = (system.tools as Record<string, unknown> | undefined) ?? {};
  const ffmpeg = tools.ffmpeg_exe as Record<string, unknown> | undefined;
  const chrome = tools.chrome_exe as Record<string, unknown> | undefined;
  const rendererDir = tools.renderer_dir;

  return [
    {label: 'Node', value: nodeOk ? 'OK' : '异常', ok: nodeOk},
    {label: 'FFmpeg', value: ffmpeg?.exists ? 'OK' : '未配置', ok: Boolean(ffmpeg?.exists)},
    {
      label: 'Chrome',
      value: chrome?.exists ? 'OK' : '未配置',
      ok: Boolean(chrome?.exists),
      optional: !chrome?.exists,
    },
    {label: 'Renderer', value: rendererDir ? 'OK' : '异常', ok: Boolean(rendererDir)},
  ];
}

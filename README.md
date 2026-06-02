<h1 align="center">Repo to Shorts</h1>

<p align="center">
  把公开 GitHub 仓库自动生成中文 9:16 竖屏项目讲解短视频。
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Remotion" src="https://img.shields.io/badge/Remotion-4.x-000000?style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Web_UI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="Video" src="https://img.shields.io/badge/Video-9%3A16_MP4-58A6FF?style=flat-square">
</p>

---

## 简介

Repo to Shorts 是一个面向开源开发者的 AI 工程项目：输入一个公开 GitHub 仓库，系统会分析 README、目录结构、配置文件和核心代码，生成中文讲解稿、分镜、TTS 配音，并用 Remotion 渲染成适合手机平台发布的竖屏 MP4。

它不是通用 AI 视频生成器，也不依赖 Sora / Veo / 可灵这类视频大模型。当前主线是 **LLM 内容生成 + 证据校验 + 程序化视频渲染**，优先保证文字准确、画面可控、结果可复现。

## 当前能力

<table>
  <tr>
    <td><strong>输入</strong></td>
    <td>公开 GitHub 仓库 URL</td>
  </tr>
  <tr>
    <td><strong>内容生成</strong></td>
    <td>项目理解、中文讲解稿、storyboard、字幕 cue</td>
  </tr>
  <tr>
    <td><strong>可靠性</strong></td>
    <td>基于 README / 配置 / 代码证据的 Verifier 与轻量 Repair Agent</td>
  </tr>
  <tr>
    <td><strong>视频渲染</strong></td>
    <td>Remotion 9:16 竖屏视频，支持 preview / final 两档渲染</td>
  </tr>
  <tr>
    <td><strong>调试界面</strong></td>
    <td>FastAPI 托管 React UI，支持分镜编辑、TTS 音色选择、生成新版</td>
  </tr>
</table>

## 技术栈

```text
GitHub URL
  -> Repo Reader
  -> Evidence Index
  -> Project Understanding Agent
  -> Script Writer Agent
  -> Storyboard Agent
  -> Verifier / Repair Agent
  -> Edge TTS + Captions
  -> Remotion Renderer
  -> 9:16 MP4
```

- Backend：Python、Typer、FastAPI、Pydantic、GitPython
- LLM：默认 DeepSeek OpenAI-compatible API
- TTS：Edge TTS，默认不需要 API key
- Renderer：Remotion、FFmpeg
- Web UI：React + Vite，由 FastAPI 统一托管

## 快速开始

### 1. 安装 Python 依赖

```powershell
conda create -n repo-video-agent python=3.11 -y
conda activate repo-video-agent
pip install -r requirements.txt
pip install -e backend
```

### 2. 安装前端和渲染依赖

```powershell
cd renderer
npm install
cd ..

cd frontend
npm install
npm run build
cd ..
```

> Vite 需要 Node.js 20.19+ 或 22.12+。如果系统 Node 版本较低，可以在 `.env` 中配置项目自带或本地安装的 `NODE_EXE` / `NPM_CMD`。

### 3. 配置环境变量

```powershell
copy .env.example .env
```

至少填写：

```text
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL_REASONING=deepseek-v4-pro
DEEPSEEK_MODEL_GENERATION=deepseek-v4-flash

NODE_EXE=D:\path\to\node.exe
NPM_CMD=D:\path\to\npm.cmd
FFMPEG_EXE=D:\path\to\ffmpeg.exe
CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe
```

## 使用方式

### Web UI

```powershell
conda activate repo-video-agent
gva ui
```

默认打开：

```text
http://127.0.0.1:7860
```

网页端默认生成 `short_30s`、`preview` 版本，适合快速编辑。确认分镜后可切换到 `final` 输出 1080x1920 MP4。

### CLI

```powershell
conda run -n repo-video-agent gva render `
  --repo https://github.com/conrad-strange/rag-demo `
  --out outputs/rag-demo `
  --video-mode short_30s `
  --render-profile final `
  --no-dry-run
```

## 输出结构

每次生成都会创建独立 run：

```text
outputs/<project>/runs/0001/
  repo-summary.json
  repo-evidence-index.json
  project-insight.json
  video-script.json
  script.md
  storyboard.json
  storyboard.final.json
  storyboard-timed.json
  verification-report.json
  evaluation-report.json
  subtitles.srt
  subtitles.vtt
  demo_report.md
  audio/
  assets/
  preview_frames/
  video.mp4
```

最终视频位置：

```text
outputs/<project>/runs/<run_id>/video.mp4
```

## 项目结构

```text
backend/      Python workflow、agents、models、CLI、FastAPI API
frontend/     React/Vite 三栏式编辑与预览界面
renderer/     Remotion 竖屏视频模板
docs/         架构、输出产物、Web UI 规划
examples/     示例 storyboard
outputs/      本地生成结果，默认不提交
scripts/      本地工具安装脚本
```

## 当前限制

- 仅支持 9:16 竖屏视频。
- Web UI 只支持公开 GitHub 仓库 URL。
- 当前不自动运行用户项目截图，避免依赖安装、端口、数据库和 API key 让 MVP 不稳定。
- Verifier 是辅助校验，不保证完全替代人工审查；发布前建议查看 `verification-report.md` 和最终视频。

## Roadmap

- 更丰富的 scene 模板：README 滚动、代码聚焦、架构图、结果画面。
- 更精确的字幕 timing：接入支持 word boundary 的 TTS。
- 更强的证据链：claim 级定位、自动降级改写。
- 更完整的 Web 编辑体验：任务历史、渲染队列、失败恢复和下载页。

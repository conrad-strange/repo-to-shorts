# GitHub Video Agent

面向 GitHub 项目的多 Agent 中文讲解视频生成器。

它不是通用 AI 视频生成器，而是把一个真实代码仓库自动转成适合手机平台发布的 9:16 中文项目讲解视频：读取仓库、理解项目、生成讲稿和分镜、用 TTS 配音，最后通过 Remotion 稳定渲染成 MP4。

## 当前能力

- 支持 GitHub 仓库 URL 或本地项目路径输入。
- 自动扫描 README、目录结构、配置文件、入口文件和核心代码片段。
- 使用 DeepSeek/OpenAI 兼容接口生成项目理解、中文讲稿和 storyboard。
- 生成真实 GitHub 仓库开场截图、README 证据画面、流程图、技术栈卡片和字幕节拍。
- 使用 Edge TTS 生成中文配音，并按音频时长调整 scene timing。
- 使用 Remotion 输出 1080x1920、9:16 MP4。
- 内置 Verifier Agent，检查视频文案是否有仓库证据支持，避免胡说。
- 每次生成独立 run，并保留 `videos/latest/video.mp4` 作为最新视频快捷入口。

## 工作流

```text
GitHub Repo / Local Project
  -> Repo Reader
  -> Evidence Index
  -> Project Understanding Agent
  -> Script Writer Agent
  -> Storyboard Agent
  -> Verifier Agent
  -> TTS Timing + Captions
  -> Remotion Renderer
  -> 9:16 MP4
```

## 项目结构

```text
backend/       Python CLI、workflow、agents、Pydantic models
renderer/      Remotion 竖屏视频渲染器
docs/          架构、MVP 状态、提示词和本地工具说明
examples/      示例 storyboard
outputs/       生成结果，默认被 git 忽略
scripts/       本地工具安装脚本
requirements.txt
README.md
```

## 环境准备

推荐使用 Conda 管理 Python 环境，Node.js 和 FFmpeg 可以使用系统安装，也可以放到 `.tools/` 后在 `.env` 中配置路径。

```powershell
conda create -n repo-video-agent python=3.11 -y
conda activate repo-video-agent
pip install -r requirements.txt
pip install -e backend
```

安装 Remotion 依赖：

```powershell
cd renderer
npm install
cd ..
```

复制环境变量模板：

```powershell
copy .env.example .env
```

至少需要配置：

```text
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL_REASONING=deepseek-v4-pro
DEEPSEEK_MODEL_GENERATION=deepseek-v4-flash

TTS_PROVIDER=edge
TTS_RATE=+25%

NODE_EXE=D:\path\to\node.exe
NPM_CMD=D:\path\to\npm.cmd
FFMPEG_EXE=D:\path\to\ffmpeg.exe
CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe
```

说明：

- Edge TTS 不需要 API key。
- Chrome 用于生成真实 GitHub 仓库截图；未配置时会降级为文字开场。
- `deepseek-v4-flash` 适合脚本和分镜生成，`deepseek-v4-pro` 适合 verifier 和复杂理解。

## 快速开始

从 GitHub URL 生成视频：

```powershell
conda run -n repo-video-agent gva render --repo https://github.com/conrad-strange/rag-demo --out outputs/rag-demo --no-dry-run
```

从本地项目生成视频：

```powershell
conda run -n repo-video-agent gva render --path D:\path\to\project --out outputs/my-project --no-dry-run
```

查看历史生成版本：

```powershell
conda run -n repo-video-agent gva runs --out outputs/rag-demo
```

重新评估最新版本：

```powershell
conda run -n repo-video-agent gva eval --out outputs/rag-demo --run latest
```

清理旧版本，只保留最近 3 个 run：

```powershell
conda run -n repo-video-agent gva clean --out outputs/rag-demo --keep 3
```

## 输出目录

每次生成都会创建一个独立 run：

```text
outputs/rag-demo/runs/0003/
  repo-summary.json
  repo-evidence-index.json
  project-insight.json
  video-script.json
  storyboard.json
  storyboard-timed.json
  verification-report.json
  evaluation-report.json
  logs/
  audio/
  assets/
  videos/video.mp4
```

最新视频快捷入口：

```text
outputs/rag-demo/videos/latest/video.mp4
```

`outputs/<project>/videos/` 可以删除，但它是 CLI 保留的 latest 兼容入口；删除后不会影响历史 run，下次成功渲染会重新生成。

## 当前限制

- 目前只支持竖屏 9:16。
- 视频风格仍以程序化模板为主，不依赖 Sora/Veo/可灵等生成式视频模型。
- 项目运行截图暂未自动生成，避免被依赖安装、端口、数据库或 API key 卡住。
- README 内容较弱的项目会更多依赖代码和配置文件证据，Verifier 会阻止无证据 claim 进入最终视频。

## 路线图

- 更细的 scene 模板：架构图、代码焦点、README 滚动截图。
- 更精准的字幕 timing：接入支持 word boundary 的 TTS。
- 更强的 verifier：claim 级证据定位和自动降级改写。
- Web UI：上传仓库链接、预览分镜、对比历史视频。
- 可选项目运行截图：在用户显式配置启动命令后生成 localhost 画面。

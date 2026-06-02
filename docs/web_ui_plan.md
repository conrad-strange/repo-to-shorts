# FastAPI + React/Vite 正式 Web UI 计划

当前项目已经有 CLI 和 FastAPI + React/Vite 本地网页入口。正式 Web UI 的目标不是替代 CLI，而是把“仓库分析、分镜编辑、TTS 调参、校验报告、视频预览”收进一个单命令本地网页工具里。

## 1. 为什么使用 FastAPI + React/Vite

这个项目面向的是希望快速生成 GitHub 项目短视频的开发者，所以正式入口需要尽量简单：用户只运行 `gva ui`，FastAPI 托管构建后的静态页面和 `/api/*`，不要求分别启动前端和后端。

React/Vite 负责更细的交互界面：分镜时间线、手机预览、scene 表单编辑、视频播放器、关键帧网格和校验报告联动都比纯后端模板更自然。

## 2. 技术路线

- Backend: FastAPI，复用现有 Python workflow、Pydantic models、Agent、run artifact。
- Frontend: React + Vite + TypeScript，构建后由 FastAPI 静态托管。
- Renderer: 继续使用现有 Remotion，不替换渲染主线。
- Storage: 初版仍使用本地 `outputs/<project>/runs/<run_id>/`，暂不引入数据库。
- Job: 初版同步触发 workflow，后续升级为任务队列 + 轮询或 SSE。
- Entry: 用户只运行 `gva ui`，默认打开 `http://127.0.0.1:7860`。

## 3. 三栏界面

### 左侧：项目和流程导航

- 输入公开 GitHub 仓库 URL；
- 选择 `short_30s` / `standard_60s` / `technical_90s`；
- 选择 `preview` / `final` 渲染 profile；
- 触发生成；
- 查看历史项目和历史 run；
- 展示 Repo -> Evidence -> Script -> Storyboard -> Verify -> TTS -> Render 流程。

### 中间：手机视频预览 / 分镜预览

- 9:16 手机外框预览最终 `video.mp4`；
- 视频未生成时展示 `preview_grid.jpg`；
- 旁边显示 scene 列表，点击 scene 后右侧编辑；
- 后续可以接入 Remotion preview server，实现未渲染前的实时画面预览。

### 右侧：当前 scene 编辑器 / TTS 设置 / 校验报告

- 编辑当前 scene 的标题、短字幕、时长、旁白、画面关键词、代码片段；
- 保存为 `storyboard.edited.json`，并可激活到 `storyboard.json`；
- 显示 TTS / render profile / verifier / evaluation 摘要；
- 展示 verification report，后续改成更友好的 claim 级列表。

## 4. API 初版

```text
GET  /api/health
GET  /api/system

GET  /api/projects
POST /api/projects

GET  /api/projects/{project_id}/runs
GET  /api/projects/{project_id}/runs/{run_id}

GET  /api/projects/{project_id}/runs/{run_id}/storyboard
PUT  /api/projects/{project_id}/runs/{run_id}/storyboard
POST /api/projects/{project_id}/runs/{run_id}/rerender

GET  /api/projects/{project_id}/runs/{run_id}/files/{artifact_path}
```

初版不做数据库，`project_id` 暂时映射到 `outputs/<project_id>`。这让正式 UI 可以先复用现有 CLI 生成物，避免重写工作流。

正式网页不支持本地项目路径。这个项目的用户场景是“把已经发布到 GitHub 的开源项目快速做成宣传短视频”，如果项目还没有上传 GitHub，优先级应该是先整理 README 和仓库页面，而不是生成推广视频。

## 5. 速度优化方向

正式 UI 的速度优化分两层：

1. 交互预览层：默认使用 `render_profile=preview`，即 540x960 / 30fps；更快生成一个可看节奏的视频，同时不改变 Remotion composition 尺寸。
2. 最终导出层：用户确认 storyboard 后，再使用 `render_profile=final`，即 1080x1920 / 30fps。

已预留配置：

- `RENDER_PROFILE=final | preview`
- `REMOTION_CONCURRENCY=`
- CLI 参数：`--render-profile`、`--remotion-concurrency`

后续可继续优化：

- 将 TTS、字幕、渲染拆成单独 API，避免每次完整重跑；
- scene 未变化时复用已生成 TTS；
- 对静态背景和 GitHub/README 卡片做缓存；
- 接入任务队列后并发处理 clone/LLM/TTS/render 阶段。

## 6. Vite / Node 要求

Vite 当前文档要求 Node.js 20.19+ 或 22.12+。本项目当前可用的 portable Node 是 `v24.16.0`，满足要求；系统 PATH 里的 Node 如果仍是 `v20.11.0`，不建议用于 Vite。

推荐用项目内 portable Node：

```powershell
& .tools\node-v24.16.0-win-x64\node.exe -v
& .tools\node-v24.16.0-win-x64\npm.cmd -v
```

## 7. 启动方式

安装 Python Web 依赖：

```powershell
pip install -r requirements.txt
pip install -e backend
```

启动正式 UI：

```powershell
conda activate repo-video-agent
gva ui
```

`gva ui` 会在需要时构建 `frontend/dist`，然后由 FastAPI 托管页面和 API。前端开发时仍然可以单独跑 Vite，但这不是用户入口。

访问：

```text
http://127.0.0.1:7860
```

## 8. 后续迭代

- 增加后台 job 表和状态轮询；
- 支持只重跑 Script / Storyboard / Verify / TTS / Render 某一步；
- Scene editor 增加可视化 timeline 和拖拽排序；
- Verifier panel 改成 claim 级证据追踪；
- 接入 Remotion preview server；
- 增加最终导出页和下载页；
- 增加项目运行截图，但必须由用户显式配置启动命令和环境变量。

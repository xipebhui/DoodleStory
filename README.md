# DoodleStory

[中文](README.zh-CN.md) | [English](README.en.md)

DoodleStory 是一个文本转图片的故事生成项目。它会把用户输入的原始文本切分成一组画面片段，再结合风格库、风格参考方式和风格内配置的图片模型生成多张图片。每个风格可选择使用 Prompt 或参考图作为生图风格参考。

## 产品形态

- 用户系统：支持邮箱注册、登录、退出和找回密码；普通用户只能看到自己的任务，Admin 可以看到全部任务。
- 风格库：管理图片风格、参考图片、风格基础信息、风格提示词和参考方式；model 和默认参数由后台生成配置维护。普通任务不暴露 provider 控件，Native Agent 用户可在对话中明确指定 Grok、QY 或 xgapi。
- 角色管理：用户维护自己的固定角色形象，创建任务时可把故事里快速识别出的角色名绑定到自己的角色参考图。
- 风格测试：输入一段测试文本，按风格当前参考方式生成测试图，方便调试风格。
- 生成任务：用户输入原始文本，不改写原文；选择自动判断图片数量或固定图片数量；选择风格后提交生成。
- 结果处理：生成后支持图片点击放大，以及一键批量下载所有图片。
- Native Agent 多媒体：Skill 可组合火山 Seed-TTS 六档倍速语音、TTS 原文校准的本地
  Whisper WebVTT 字幕和固定 Remotion 图片旁白视频模板；字幕文字保持语音生成原文，并按
  真实音频时间轴显示。
- 微信公众号素材：Skill 可选择“微信公众号文章” Tool，Agent 通过同级多平台导入服务
  抓取正文并保存 Markdown 素材、标题、作者、发布时间和来源链接。
- YouTube 公开研究：Skill 可选择“读取 YouTube 频道” Tool，Agent 通过官方 Data API v3
  按需读取频道资料、近期视频标题与完整描述、标签、基础数据和顶级评论，并下载频道头像与
  每条视频的最高可用分辨率封面供模型一起分析。
- 多 Agent 文案：系统先用 Workflow Compiler 模型调用把完整“文案创作团队” Skill 编译为
  持久化执行计划，再由 Director 通过 OpenAI Agents SDK `agent.as_tool()` 调用只注入局部
  instructions 的 Writer 与 Reviewer；草稿、审稿和最终文案均持久化，最终稿可长期等待用户
  确认或退回修改。本流程只产出文本，不触发媒体 Tool。
- YouTube 频道发布：管理员维护频道别名、账号定位和对标账号，把审核通过的 Native Agent
  视频登记为可发布视频；频道详情和 Agent 对话共用异步发布服务，支持结构化 `@频道`、发布前
  明确确认、按钮式任务状态获取，以及
  `NativeAgentVideo.id → PublishTask.id → youtube_video_id` 全链路追踪。

## Codex Harness

本仓库使用 `codex-project-template` 的 Codex 开发 harness，并已结合 DoodleStory 的业务进行适配。

## 本地开发

一键重启前后端开发服务：

```bash
./scripts/restart-dev.sh
```

默认后端启动在 `http://127.0.0.1:8000`，前端启动在 `http://127.0.0.1:3000`。日志默认写入 `/tmp/doodlestory-backend.log` 和 `/tmp/doodlestory-frontend.log`。

Agent MLflow tracing 默认关闭。项目提供固定 `3.14.0` 版本的本地 Docker Tracking Server：

```bash
docker compose -f docker-compose.mlflow.yml up -d
```

MLflow metadata 和 artifacts 保存到 Docker named volume `doodlestory_mlflow_data`，UI 与
健康检查地址分别为：

```text
http://127.0.0.1:5000
http://127.0.0.1:5000/health
```

停止服务但保留数据：

```bash
docker compose -f docker-compose.mlflow.yml down
```

然后在本地 `.env` 显式配置：

```text
MLFLOW_TRACING_ENABLED=true
MLFLOW_TRACKING_URI=http://127.0.0.1:5000
MLFLOW_EXPERIMENT_NAME=doodlestory-agent-local
MLFLOW_TRACE_CONTENT=false
```

启用时 Tracking URI 必须指向可用的 HTTP(S) Tracking Server，Experiment 也必须有效，否则后端启动明确失败；直接使用 SQLite/file URI 会被拒绝，避免 MLflow 自身的系统标签暴露内部绝对路径。默认 `MLFLOW_TRACE_CONTENT=false` 只记录 Run/Step ID、Provider、模型、attempt、fallback、延迟、usage 和状态，不记录用户正文、完整 Prompt、图片 URL、密钥或 Provider 原始响应。创建受控本地 smoke 前需准备一个已有用户，然后运行：

如果本机需要在 MLflow UI 查看完整模型输入/输出并做内容质量评估，可只在本地 `.env` 将
`MLFLOW_TRACE_CONTENT=true`。该模式会记录用户输入、Skill、Prompt 和模型输出；密钥、
Authorization、URL 与本地绝对路径仍会强制脱敏，不应在共享或生产环境默认开启。

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/agent-mlflow-smoke.py \
  --owner-email "<existing-user@example.com>" \
  --scenario primary_success
```

## Docker / Coolify 部署

仓库提供生产 `Dockerfile` 和 Coolify Compose 示例：

- `Dockerfile`：构建前端静态文件，并在同一个 FastAPI 容器中提供前端与 `/api/v1/*` API。
- `docker-compose.coolify.yml`：用于 Coolify Docker Compose 服务，同时拉起 DoodleStory 和同级目录的 `douyin-downloader` 依赖镜像；DoodleStory 使用 `expose: "8000"`，不映射宿主机 `80/443`，抖音导入服务只走 Compose 内部网络。
- `docker-compose.local.yml`：本地调试覆盖文件，把 DoodleStory 映射到 `127.0.0.1:18080`。
- `docs/deployment/coolify-docker.md`：部署步骤、环境变量、持久化 volume 和健康检查说明。

本地构建：

```bash
docker build -t doodlestory:local .
```

本地拉起 DoodleStory + 抖音导入依赖服务：

```bash
docker-compose -f docker-compose.coolify.yml -f docker-compose.local.yml up --build
```

需要保持同级目录存在：

```text
tmp-project/
  DoodleStory/
  douyin-downloader/
```

首次部署或更新依赖仓库时，可先执行：

```bash
./scripts/prepare-douyin-downloader.sh
```

如果使用文件形式配置抖音 Cookie，可在 Compose 启动后写入或覆盖依赖服务的 Cookie volume：

```bash
./scripts/install-douyin-cookies.sh /path/to/cookies.json
```

生产容器默认监听 `8000`，SQLite 数据库和本地资产默认写入 `/app/data`，部署时必须把 `/app/data` 配成持久化 volume。

### Grok 订阅图片 / 视频认证

项目固定安装 `grokcli`，本地通过浏览器 OAuth 登录一次即可：

```bash
grokcli login
grokcli status --output json
grokcli image "一只橘猫程序员" --aspect 3:4 --resolution 1k --output json
grokcli video "镜头缓慢掠过山谷中的溪流" --aspect 16:9 --resolution 720p --duration 8 --output json
```

本地默认凭据目录是 `~/.config/grokcli`。Coolify Compose 把 `GROKCLI_HOME` 固定为
`/app/data/grokcli`，位于现有持久化 volume；首次部署或凭据失效后，在运行中的容器内执行：

```bash
docker compose -f docker-compose.coolify.yml exec doodlestory grokcli login --manual-paste
docker compose -f docker-compose.coolify.yml exec doodlestory grokcli status --output json
```

OAuth 凭据不得提交到 Git。`grokcli doctor` 会检查 `/v1/models` 等更宽的 API surface；若它
单独报告 403，仍应以真实 `grokcli image` smoke 判断订阅生图权限。Provider 失败不会自动切换：
Native Agent 对话可明确要求 `Grok`、`QY` 或 `xgapi`，普通任务使用 `IMAGE_PROVIDER`。
Native Agent 的 `generate_video_clip` 固定通过 Grok 生成 1–15 秒 T2V / 单图 I2V 短镜头，默认
使用 `grok-imagine-video-1.5` 与 720p；每次 Tool Call 只发起一次生成，失败或结果未知时不会自动
重试，也不会切换到其他视频 Provider。

Paynes Creek 本地验证另有一个五镜 AI 短片模板：使用真实 Grok 2K 首帧与 720p I2V 镜头、一次
SiliconFlow 旁白和 Remotion 合成 1920×1080 MP4；模板支持独立 `zh-CN` / `en-US` 标题、证据标签、
字幕与产物命名。该路径只用于本地样片，固定不自动发布。

## 抖音热门样本采集环境

项目内的 `douyin-hot-sample-research` Skill 使用当前仓库里的封装脚本调用外部 MediaCrawler，不需要在新对话里记住外部脚本路径。

默认约定：

- MediaCrawler checkout 默认位于 `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler`。
- 如需迁移或换目录，设置 `MEDIACRAWLER_HOME`：

```bash
export MEDIACRAWLER_HOME=/path/to/MediaCrawler
```

- MediaCrawler 目录内需要存在 `.venv/bin/python` 和 `main.py`。
- Chrome 需要开启远程调试：在 Chrome 地址栏打开 `chrome://inspect/#remote-debugging`，勾选 `Allow remote debugging for this browser instance`，页面显示 `Server running at: 127.0.0.1:9222`。
- 运行爬虫时如果 Chrome 弹出授权确认，需要手动点击允许。

从 DoodleStory 仓库调用 MediaCrawler：

```bash
python .agents/skills/douyin-hot-sample-research/scripts/run_mediacrawler.py \
  --platform dy \
  --type search \
  --keywords "文字漫画" \
  --crawler_max_notes_count 30 \
  --save_data_path data_test/wenzimanhua_week_comprehensive \
  --dy_publish_time_type 7 \
  --dy_content_type 0 \
  --get_comment false \
  --get_sub_comment false
```

搜索结果分析：

```bash
python .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py \
  --contents /path/to/MediaCrawler/data_test/<run>/douyin/jsonl/search_contents_YYYY-MM-DD.jsonl \
  --out-dir output/douyin-hot-sample-analysis/<run>
```

分析脚本默认按 `aweme_id` 去重，并输出原始候选数、去重状态、A/B/C/D 候选评分和类目横向对比。生成最终故事前不要只依赖首尾页预览；入选样本必须先走 DoodleStory 全量 VL，提取完整原文后再优化和原创改写。

## 内容迭代控制器

项目内已经有最小版“迷宫控制器” Skill，用于管理内容实验的预测、发布后数据回流、预测误差和策略更新：

```text
.agents/skills/content-iteration-controller/
content-lab/
```

初始化控制器状态：

```bash
python .agents/skills/content-iteration-controller/scripts/init_controller_state.py
```

创建一轮实验目录：

```bash
python .agents/skills/content-iteration-controller/scripts/create_experiment.py \
  --experiment-id 2026-06-16-wenzimanhua-cycle-01 \
  --title "文字漫画第一轮真实感结尾实验"
```

校验控制器状态：

```bash
python .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
```

生成任务提交前，先把故事 brief 转成可画分镜稿，并在实验 `publish_plan.json` 的对应 slot 写入：

```json
{
  "render_storyboard": {
    "artifact": "content-lab/render_storyboards/<file>.md",
    "status": "ready_for_task_submission",
    "source_generation_brief": "content-lab/generation_briefs/<file>.md"
  }
}
```

绑定发布账号画风并提交 DoodleStory 生成任务：

```bash
python .agents/skills/content-iteration-controller/scripts/submit_generation_task.py \
  bind-style \
  --account "行走的故事" \
  --style-id "<DoodleStory style_id>" \
  --style-name "<风格名>"

DOODLESTORY_EMAIL="<email>" DOODLESTORY_PASSWORD="<password>" \
python .agents/skills/content-iteration-controller/scripts/submit_generation_task.py \
  submit-slot \
  --experiment-id 2026-06-16-huayigegushi-cycle-01 \
  --slot-id P3-H2-walking-story
```

内容实验提交任务时固定走 `提取分镜`：`story_input_mode=extracted_storyboard`、`image_count_mode=auto`、`use_character_references=true`、`story_characters=[]`。这与前端普通创建保持一致：不绑定固定角色，但仍走临时角色一致性链路。画风必须通过 `content-lab/strategy_state/account_style_bindings.json` 从发布账号绑定到具体 DoodleStory `style_id`，不会使用默认画风；提交正文必须来自 `render_storyboard.artifact`，只取 `图1/图2...` 开始的逐页可画分镜块。

控制器不自动发布、不自动读取后台、不自动修改 Skill。发布前必须先写 `prediction.json`；发布后有真实数据，才允许写 `prediction_errors.jsonl`、`deviation_review.md` 和 `strategy_update.json`。

内容实验还需要记录叙事人格。控制器人格保持统一，负责证据和规则；内容叙事人格按人群欲望、情绪曲线、道德站位和风险边界配置，并写入 `prediction.json` 的 `narrative_persona_profile`。账号昵称、头像和简介是服务内容人格的包装，可以调整，不应反过来限制内容机制。

开始较大实现工作前，请先阅读：

- [项目规格](docs/spec.md)
- [进度记录](docs/progress.md)
- [全部出站调用与模型端点](docs/integrations/llm-agent-endpoints.md)
- [SiliconFlow Native Agent 兼容性决策](docs/integrations/siliconflow-native-agent-compatibility-decision.md)
- [SiliconFlow Native Agent 适配实施蓝图](docs/architecture/siliconflow-native-agent-adapter-blueprint.md)
- [SiliconFlow Native Agent 适配架构图](docs/architecture/diagrams/siliconflow-native-agent-adapter.svg)
- [Agent V1 全局实施路线图](docs/implementation/agent-v1-implementation-roadmap.md)
- [Agent V1 新窗口实施交接](docs/implementation/agent-v1-new-window-handoff.md)
- [已完成：Sprint 111 独立 Agent Shell 与只读任务检查器](docs/contracts/sprint-111-agent-independent-shell-readonly-inspector.md)
- [Complete：Sprint 112 Agent MLflow 可观测性基线](docs/contracts/sprint-112-agent-mlflow-observability-baseline.md)
- [已完成：Sprint 113 通用 Skill / Tool Runtime 基础](docs/contracts/sprint-113-agent-skill-tool-runtime-foundation.md)
- [Complete：Sprint 114 idea-to-comic Skill、方案确认与真实事件流](docs/contracts/sprint-114-idea-to-comic-skill-hitl-event-stream.md)
- [Complete：Sprint 115 结构化资源引用与同一任务续作](docs/contracts/sprint-115-agent-structured-resource-context.md)
- [Complete：Sprint 116 Panel 版本操作、VL 检查与任务控制](docs/contracts/sprint-116-agent-panel-version-vl-loop.md)
- [Complete：Sprint 117 可插拔 Skill 管理、版本与通用 Agent Loop](docs/contracts/sprint-117-pluggable-skill-management-agent-loop.md)
- [Complete：Sprint 119 最小原生 Agent Loop](docs/contracts/sprint-119-minimal-native-agent-loop.md)
- [Complete：Sprint 120 Native Loop MLflow 与 Agent UI 一致性](docs/contracts/sprint-120-native-loop-mlflow-and-agent-ui.md)
- [Complete：Sprint 123 Native Agent 可恢复执行与持久化事件流](docs/contracts/sprint-123-native-agent-durable-runtime.md)
- [Complete：Sprint 124 Native Agent 火山引擎固定语音 Tool](docs/contracts/sprint-124-native-agent-volcengine-speech-tool.md)
- [Complete：Sprint 125 Native Agent 固定 Remotion 视频 Tool](docs/contracts/sprint-125-native-agent-remotion-video-tool.md)
- [Complete：Sprint 126 Remotion 跟随源图比例与指定会话真实验收](docs/contracts/sprint-126-remotion-source-image-ratio-real-task-smoke.md)
- [Complete：Sprint 134 YouTube 频道账号与视频登记](docs/contracts/sprint-134-youtube-channel-account-and-video-registry.md)
- [Complete：Sprint 135 YouTube 异步发布与 Agent 频道引用](docs/contracts/sprint-135-youtube-publishing-and-agent-channel-mention.md)
- [Complete：Sprint 136 YouTube 列表分页与可读性](docs/contracts/sprint-136-youtube-list-pagination-and-readability.md)
- [Complete：Sprint 137 微信公众号文章 Agent Tool](docs/contracts/sprint-137-wechat-article-agent-tool.md)
- [Complete：Sprint 138 YouTube 频道研究 Tool](docs/contracts/sprint-138-youtube-channel-research-tool.md)
- [Deferred：Agent Evaluation 与内部开放门槛](docs/contracts/deferred-agent-evaluation-internal-release-gate.md)
- [已完成：Sprint 106 对话创建两格真实漫画](docs/contracts/sprint-106-agent-comic-creation-vertical-slice-draft.md)
- [已完成：Sprint 107 传统构建与 AI 构建前端整合](docs/contracts/sprint-107-agent-frontend-workspace-integration.md)
- [已完成：Sprint 108 正式 Agent 前端与已调试 Demo 对齐](docs/contracts/sprint-108-agent-demo-alignment.md)
- [已废止未实施：Sprint 109 Panel 迭代与 VL 草案](docs/contracts/sprint-109-agent-panel-iteration-vl-draft.md)
- [已完成：Sprint 105 Agent Runtime 基础](docs/contracts/sprint-105-agent-runtime-foundation.md)
- [Complete：Sprint 176 SiliconFlow Native Agent 兼容性决策](docs/contracts/sprint-176-siliconflow-native-agent-compatibility-decision.md)
- [Complete：Sprint 177 SiliconFlow Native Agent 适配实施蓝图](docs/contracts/sprint-177-siliconflow-native-agent-adapter-blueprint.md)
- [Complete：Sprint 178 YouTube 首片赛道定案与 Paynes Creek 生产控制台](docs/contracts/sprint-178-youtube-paynes-creek-production-control-room.md)
- [Complete：Sprint 179 Paynes Creek S03 单镜重试证据包](docs/contracts/sprint-179-youtube-paynes-creek-s03-retry-evidence-packet.md)
- [Complete：Sprint 180 SiliconFlow Native Agent 零媒体 Gate 证据包](docs/contracts/sprint-180-siliconflow-native-agent-zero-media-gate-evidence-packet.md)
- [Complete：Sprint 181 Native Agent Run 路由快照基础（G2-A）](docs/contracts/sprint-181-native-agent-run-route-snapshot-foundation.md)
- [Complete：Sprint 192 Native Agent SiliconFlow Chat 有界适配（G2-B）](docs/contracts/sprint-192-native-agent-siliconflow-chat-bounded-adapter.md)
- [Complete：Sprint 193 SiliconFlow Native Agent G3 真实零媒体 Gate](docs/contracts/sprint-193-siliconflow-native-agent-g3-real-zero-media-gate.md)
- [Complete：Sprint 194 Windows SQLite 绝对路径 URL 解析修复](docs/contracts/sprint-194-windows-sqlite-absolute-url-resolution.md)
- [Complete：Sprint 195 Paynes Creek G4 单张 S03 真实媒体 Gate（Attempt 02 needs revision）](docs/contracts/sprint-195-youtube-paynes-creek-g4-single-image-gate.md)
- [In progress：Sprint 196 Paynes Creek G4 Attempt 03 正向对象白名单](docs/contracts/sprint-196-youtube-paynes-creek-g4-attempt-03-positive-object-prompt.md)
- [Complete：Sprint 182 Paynes Creek 本地样片验收包](docs/contracts/sprint-182-youtube-paynes-creek-local-pilot-acceptance-packet.md)
- [Complete：Sprint 183 Paynes Creek Style 状态对账](docs/contracts/sprint-183-youtube-paynes-creek-style-state-reconciliation.md)
- [Complete：Sprint 184 Paynes Creek G5 串行视觉锚点 Gate](docs/contracts/sprint-184-youtube-paynes-creek-g5-serial-anchor-gates.md)
- [Complete：Sprint 185 Paynes Creek G6 九镜串行生产设计](docs/contracts/sprint-185-youtube-paynes-creek-g6-serial-scene-production.md)
- [Complete：Sprint 186 Paynes Creek G7 语音字幕与跨 Run 边界](docs/contracts/sprint-186-youtube-paynes-creek-g7-audio-subtitle-boundary.md)
- [Ready for review：Sprint 187 Native Agent 同会话跨 Run 媒体 Lineage（G7-0）](docs/contracts/sprint-187-native-agent-cross-run-media-lineage.md)
- [Ready for review：Sprint 188 Native Agent YouTube 1080p 固定渲染 Profile（G8-A）](docs/contracts/sprint-188-native-agent-youtube-1080p-render-profile.md)
- [Ready for review：Sprint 189 Native Agent 冻结 Render Manifest Run（G8-B）](docs/contracts/sprint-189-native-agent-frozen-render-manifest-run.md)
- [Complete：Sprint 199 grokcli Native Agent AI 视频短镜头 Tool](docs/contracts/sprint-199-grokcli-native-agent-video-clip-tool.md)
- [Complete：Sprint 200 Paynes Creek Grok AI 五镜短片样片](docs/contracts/sprint-200-paynes-creek-grok-ai-short-pilot.md)
- [Complete：Sprint 201 Paynes Creek Grok AI 英文五镜短片](docs/contracts/sprint-201-paynes-creek-grok-ai-english-short.md)
- [Ready for review：Sprint 190 Native Agent 成片逐镜帧证据包（G8-C）](docs/contracts/sprint-190-native-agent-video-frame-evidence-pack.md)
- [Ready for review：Sprint 191 Native Agent 不可变本地样片验收与发布登记门禁](docs/contracts/sprint-191-native-agent-immutable-local-pilot-acceptance.md)
- [产品设计](docs/design/README.md)
- [开发规范](docs/standards/)
- [参考：Harness design: Building long-running applications with LLMs](docs/references/harness-design-long-running-apps.md)

# DoodleStory

[中文](README.zh-CN.md) | [English](README.en.md)

DoodleStory 是一个文本转图片的故事生成项目。它会把用户输入的原始文本切分成一组画面片段，再结合风格库、风格参考方式和风格内配置的图片模型生成多张图片。每个风格可选择使用 Prompt 或参考图作为生图风格参考。

## 产品形态

- 用户系统：支持邮箱注册、登录、退出和找回密码；普通用户只能看到自己的任务，Admin 可以看到全部任务。
- 风格库：管理图片风格、参考图片、风格基础信息、风格提示词和参考方式；provider、model 和默认参数由后台生成配置维护，不暴露给普通用户。
- 角色管理：用户维护自己的固定角色形象，创建任务时可把故事里快速识别出的角色名绑定到自己的角色参考图。
- 风格测试：输入一段测试文本，按风格当前参考方式生成测试图，方便调试风格。
- 生成任务：用户输入原始文本，不改写原文；选择自动判断图片数量或固定图片数量；选择风格后提交生成。
- 结果处理：生成后支持图片点击放大，以及一键批量下载所有图片。

## Codex Harness

本仓库使用 `codex-project-template` 的 Codex 开发 harness，并已结合 DoodleStory 的业务进行适配。

## 本地开发

一键重启前后端开发服务：

```bash
./scripts/restart-dev.sh
```

默认后端启动在 `http://127.0.0.1:8000`，前端启动在 `http://127.0.0.1:3000`。日志默认写入 `/tmp/doodlestory-backend.log` 和 `/tmp/doodlestory-frontend.log`。

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
- [Agent V1 全局实施路线图](docs/implementation/agent-v1-implementation-roadmap.md)
- [Agent V1 新窗口实施交接](docs/implementation/agent-v1-new-window-handoff.md)
- [已完成：Sprint 111 独立 Agent Shell 与只读任务检查器](docs/contracts/sprint-111-agent-independent-shell-readonly-inspector.md)
- [Planned：Sprint 112 Agent MLflow 可观测性基线](docs/contracts/sprint-112-agent-mlflow-observability-baseline.md)
- [Planned：Sprint 113 通用 Skill / Tool Runtime 基础](docs/contracts/sprint-113-agent-skill-tool-runtime-foundation.md)
- [Planned：Sprint 114 idea-to-comic Skill、方案确认与真实事件流](docs/contracts/sprint-114-idea-to-comic-skill-hitl-event-stream.md)
- [Planned：Sprint 115 结构化资源引用与同一任务续作](docs/contracts/sprint-115-agent-structured-resource-context.md)
- [Planned：Sprint 116 Panel 版本操作、VL 检查与任务控制](docs/contracts/sprint-116-agent-panel-version-vl-loop.md)
- [Planned：Sprint 117 Evaluation 与内部开放门槛](docs/contracts/sprint-117-agent-evaluation-internal-release-gate.md)
- [已完成：Sprint 106 对话创建两格真实漫画](docs/contracts/sprint-106-agent-comic-creation-vertical-slice-draft.md)
- [已完成：Sprint 107 传统构建与 AI 构建前端整合](docs/contracts/sprint-107-agent-frontend-workspace-integration.md)
- [已完成：Sprint 108 正式 Agent 前端与已调试 Demo 对齐](docs/contracts/sprint-108-agent-demo-alignment.md)
- [已废止未实施：Sprint 109 Panel 迭代与 VL 草案](docs/contracts/sprint-109-agent-panel-iteration-vl-draft.md)
- [已完成：Sprint 105 Agent Runtime 基础](docs/contracts/sprint-105-agent-runtime-foundation.md)
- [产品设计](docs/design/README.md)
- [开发规范](docs/standards/)
- [参考：Harness design: Building long-running applications with LLMs](docs/references/harness-design-long-running-apps.md)

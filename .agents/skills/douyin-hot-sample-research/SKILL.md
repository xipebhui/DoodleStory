---
name: douyin-hot-sample-research
description: 用于抖音图文热门赛道预测、关键词样本采集、热门样本评分、账号/评论/VL 探测、发布实验设计和账号复盘。用户提到抖音热门、文字漫画、图文赛道、关键词预测、账号复盘、评论分析、首尾图 VL、全量故事提取或 DoodleStory 内容实验时使用。
---

# 抖音热门图文样本调研与预测

## 目标

这个 Skill 是 DoodleStory 的抖音图文内容预测与实验系统，不是素材包工具。它负责从关键词或账号出发，采集最近热门样本，判断市场正在奖励什么机制，再把机制转成可发布实验、DoodleStory 故事方案和后续复盘输入。

采集底座包括：

- 当前项目内脚本：评分、去重、报告、浏览器态搜索封装。
- 外部 MediaCrawler：通过当前项目内 `scripts/run_mediacrawler.py` 调用。
- `douyin-downloader`：用于选中样本下载、评论和素材落地。
- DoodleStory 现有 VL 链路：用于首尾图预览和全量故事原文提取。

不要把 Codex 手工看图当作正式提取流程。需要 OCR、逐页文案、故事原文或生成前改写时，必须复用 DoodleStory 的视觉理解链路。

这个 Skill 不承诺流量，也不绕过平台校验。所有结论必须来自本地 crawler/downloader/VL 产物，不能伪造市场数据。

## 独立运行依赖

新对话中运行时，不要依赖聊天历史记住路径。先按下面规则确认依赖：

- `MEDIACRAWLER_HOME`：可选环境变量，指向 MediaCrawler checkout。未设置时默认 `/Users/pengfei.shi/workspace/tmp-project/MediaCrawler`。
- MediaCrawler 应有 `.venv/bin/python`，Chrome CDP 已开启 `127.0.0.1:9222`。
- DoodleStory 后端 `.venv` 应可导入 `backend/app/services/media_text_extraction.py`。
- `douyin-downloader` 仍作为选中样本下载底座；路径见下方“先读文件”。

优先通过当前项目内封装调用 MediaCrawler：

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

如果迁移到新机器，优先设置：

```bash
export MEDIACRAWLER_HOME=/path/to/MediaCrawler
```

## 先读文件

1. 当前文件。
2. `references/prediction-workflow-architecture.md`
3. `references/research-fields.md`
4. `references/multidimensional-analysis-strategy.md`
5. `references/seven-day-search-processing.md`
6. `docs/product/content-iteration-controller-agent.md`
7. `backend/app/services/media_text_extraction.py`
8. `backend/app/api/content_extractions.py`
9. `backend/app/prompts/parse_extracted_storyboard_v1.md`
10. `/Users/pengfei.shi/workspace/tmp-project/douyin-downloader/README.zh-CN.md`

## 工作流

### 分步执行协议

默认每轮只执行一个小 step。只有用户明确说 `一次执行到位`、`跑完整流程`、`连续执行`、`直接跑完` 时，才连续执行多个 step。

每轮开始时：

- 识别入口：`new_lane_prediction` 或 `account_review`。
- 从用户表达、本地 artifact、最新 experiment 目录判断当前 step。
- 只执行下一个最小可检查动作。
- 产出可复核文件、表格或判断后停止。
- 结尾必须写 `本轮完成` 和 `下一步建议`，明确用户回复 `继续` 后会执行哪一步。

不要要求用户填复杂 JSON。只问会阻塞下一步的一个缺失字段。

`new_lane_prediction` 步骤：

1. `lane_intake`：确认关键词、新鲜度窗口、要输出的假设数量，以及是否有至少 2 个账号可用于实验。
2. `market_scan`：尽量采集综合排序、最新发布、最多点赞这几类最近结果。
3. `market_scoring`：筛选图文候选，按 A/B/C/D 评分，并输出类目横向对比。
4. `deep_probe_selection`：从 A 类和强 B 类样本里选择需要账号、评论、首尾页 VL 探测的对象。
5. `probe_collection`：采集详情、评论、账号数据，并对选中样本做 `preview_vl`。
6. `topic_hypothesis`：输出可发布假设，写清预测机制、用户需求、风险和可验证指标。
7. `experiment_plan`：把假设分配到账号，定义指标、检查点和最低实验数量。
8. `full_story_extract`：对批准进入生成的种子样本运行 DoodleStory 全量 VL，先得到完整原文。
9. `generation_brief`：分析全量原文后，再优化和原创改写为 DoodleStory 可直接生成的故事方案。
10. `post_result_intake`：发布后接收后台表现数据。
11. `deviation_review`：比较预测和真实结果，诊断市场判断、账号适配或内容执行偏差。
12. `strategy_update`：更新内容库、账号适配结论和下一轮迭代方向。

`account_review` 步骤：

1. `review_intake`：确认账号、复盘窗口，以及后台数据从哪里来。
2. `account_baseline`：总结账号定位、历史作品、流量稳定性和类目适配。
3. `market_expectation`：把账号当前内容类目和最近市场扫描证据对比。
4. `post_result_intake`：把粘贴或导出的后台数据整理成逐作品、逐检查点数据。
5. `deviation_review`：按内容、账号和发布时间比较预期表现与真实表现。
6. `comment_and_topic_review`：分类高赞/高回复评论，提取下一轮选题种子。
7. `strategy_update`：更新账号适配画像、内容库笔记和下一轮实验计划。

每一步输出保持简洁、可执行：

- `input_used`：本轮使用了什么输入。
- `artifact`：本轮产出的文件路径或数据摘要。
- `decision`：本轮判断清楚了什么。
- `blocked_by`：只有下一步无法继续时才写阻塞原因。
- `next_step`：下一步的精确动作或需要用户提供的一项信息。

如果用户只说 `继续`，只执行上一轮写明的 `next_step`，不要自动跑完整流程。

### 0. 判断入口

这个 Skill 只有两个用户入口，不向用户暴露复杂配置。

当用户讨论“控制器 Agent”“人格底座”“预测误差”“Skill 迭代”或“根据发布数据定期决定下一轮选题”时，先读取 `docs/product/content-iteration-controller-agent.md`。该文档定义了迷宫控制器的人格、禁忌、二分心智、预测误差和规则升级门槛；当前 Skill 负责执行采集、分析和复盘步骤，控制器负责决定证据是否足够进入下一步以及是否允许升级规则。

用户给关键词、想拓展新赛道时，使用 `new_lane_prediction`：

- 最小输入：关键词、希望输出的选题假设数量、可选账号组。
- 默认窗口：最近 7 天。
- 默认排序视角：综合排序、最新发布、最多点赞。
- 输出：市场快照、选题假设、实验计划和 DoodleStory 故事方案 brief。

用户给账号或已发布批次、想复盘时，使用 `account_review`：

- 最小输入：账号名、账号 ID 或本地账号资料路径，复盘窗口，作品表现数据。
- 后台数据可以手动粘贴、从 CSV/JSON 读取，后续也可以由 connector 提供。
- 输出：账号基线、市场预期、真实表现、偏差诊断和下一轮实验调整。

重要边界：

- `DY爆款复刻` 仍是单样本执行器：下载、全量 VL 提取、创建 `extracted_storyboard` 任务。
- 预测型创作发生在任务创建之前。除非用户明确要求忠实复刻，否则预测路线应产出 DoodleStory `故事方案` 所需的原创改写 brief。
- 最终故事 brief 不能只基于首尾页 preview。必须先对被选中的源样本做 `full_story_document`，得到完整原文和故事结构，再分析、优化、改写。

实验、数据接入和内容库设计见 `references/prediction-workflow-architecture.md`。

### 1. 基础数据获取：先调研

从关键词或热榜词开始。优先使用最近证据：

- 第一优先级：最近 7 天。
- 第二优先级：最近 30 天。
- 第三优先级：更老的样本只能做结构参考，不作为第一批实验候选。

关键词搜索优先使用当前项目内 MediaCrawler 封装。它调用外部 MediaCrawler，但路径由 `MEDIACRAWLER_HOME` 管理，新对话不需要记住聊天上下文：

```bash
python .agents/skills/douyin-hot-sample-research/scripts/run_mediacrawler.py \
  --platform dy \
  --type search \
  --keywords "故事" \
  --crawler_max_notes_count 30 \
  --save_data_path data_test/story_week \
  --dy_publish_time_type 7 \
  --dy_content_type 0 \
  --get_comment false \
  --get_sub_comment false
```

如果需要监听页面真实搜索响应，而不是 MediaCrawler API 路径，再使用 `browser_search_collect.py`。它依赖已有登录态 `storage_state`，不会打印 cookie。

`douyin-downloader` 热榜和直接搜索只在可用时使用：

```bash
cd /Users/pengfei.shi/workspace/tmp-project/douyin-downloader
.venv/bin/python run.py --hot-board 30 -p ./Downloaded
.venv/bin/python run.py --search "故事" --search-max 100 -p ./Downloaded
```

`douyin-downloader` 的直接搜索只在可用时使用。不要在被风控、无结果或缺少筛选能力时编造数据。

### 2. 基础数据获取：候选评分

保留对 DoodleStory 有用的候选：

- `aweme_type` 或 metadata 能说明它是图集/图文内容。
- `create_time` 满足本次研究窗口。
- `statistics` 有可解释的互动：点赞、评论、收藏、转发。
- 标题或描述里有可复用故事结构，而不只是一次性梗图。
- 视觉形式可以改造成原创图文，不依赖无授权影视片段、明星或 IP 素材。

拒绝依赖无授权版权素材、私人数据或无法从本地证据验证的平台行为的样本。

MediaCrawler 搜索后，用分析脚本把 JSONL 转成候选评分表。脚本默认按 `aweme_id` 去重：

```bash
python .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py \
  --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week/douyin/jsonl/search_contents_2026-06-15.jsonl \
  --out-dir output/douyin-hot-sample-analysis/huayigegushi-week
```

如果入选样本已经采集评论，把评论 JSONL 一起传入：

```bash
python .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py \
  --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week/douyin/jsonl/search_contents_2026-06-15.jsonl \
  --comments /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/comment_probe_top_a/douyin/jsonl/detail_comments_2026-06-15.jsonl \
  --out-dir output/douyin-hot-sample-analysis/huayigegushi-week-with-comments
```

分析脚本输出 `candidate_scores.csv`、`candidate_scores.json`、`category_summary.csv/json` 和 `analysis_report.md`。评分使用新鲜度、图文类型、点赞、评论、收藏、转发、互动率、标签和可选评论信号。小分母高转发率不能单独把样本抬成 A。

如果已经采集了作者主页资料，也一起传入。分析脚本会补充作品数、粉丝数和账号模仿度标签：

```bash
python .agents/skills/douyin-hot-sample-research/scripts/analyze_search_results.py \
  --contents /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/huayigegushi_week/douyin/jsonl/search_contents_2026-06-15.jsonl \
  --creators /Users/pengfei.shi/workspace/tmp-project/MediaCrawler/data_test/account_probe_yierbubu/douyin/jsonl/creator_creators_2026-06-15.jsonl \
  --out-dir output/douyin-hot-sample-analysis/huayigegushi-week-seven-day-processing
```

分析脚本也会写出 `category_summary.csv` 和 `category_summary.json`。先用它们判断最近 7 天整体哪些类目有热度，再决定深挖单个作品。

### 3. 最近 7 天决策层

拿到最近搜索结果后，先处理整批结果，再深入单个作品：

- 横向比较类目：A/B 样本数、总点赞、评论、转发、点赞中位数和代表标题。
- 优先选择有多个 A/B 样本支撑的类目，而不是被单个异常爆款撑起来的类目。
- 给高信号样本标记账号探测优先级。高流量且有 `sec_uid` 的作品优先探测主页。
- 账号作品数、粉丝数、总互动量是重要参考，但大号和作品多通常说明有账号积累，会削弱“可快速模仿”的判断。
- 不因为账号大就否定样本，但要把 `large_mature_account_penalty` 记录进模仿难度。
- Treat `needs_account_probe` as an explicit next action, not as a final judgment.

对于真实感结尾：

- 如果最后一页是真人照片、截图、文档、聊天记录或证据式图片，把它记录为可复用的格式机制。
- 不复制原真人、私人证据或敏感截图。
- 用原创资产、授权素材或 image-2 真实场景生成来复现“可信感功能”。
- 研究问题是：这个热门机制怎样变成原创的真实感场景？

See `references/seven-day-search-processing.md` for category labels, mimicability labels, and realistic-ending generation strategy.

对于新赛道预测，把这一层转成选题假设和实验：

- 重要假设尽量至少用 2 个账号测试。
- 发布前先记录预期结果。
- 发布后把真实后台数据存入实验结果层。
- 如果真实结果严重偏离预期，分别诊断市场判断、账号适配、故事机制、视觉执行或真实感结尾是否失败。

### 4. 下载选中作品

筛完浏览器搜索 JSONL 或 downloader 搜索 JSONL 后，用 `douyin-downloader` 下载选中的 `share_url`、作品 URL 或 `aweme_id` URL。需要评论反馈信号时，打开 JSON metadata 和评论：

```yaml
json: true
comments:
  enabled: true
  include_replies: false
  max_comments: 200
  page_size: 20
```

downloader 会写出 `*_data.json`、媒体文件、可选 `*_comments.json` 和 `download_manifest.jsonl`。

### 5. 汇总本地证据

直接用 downloader 搜索或下载后，使用内置汇总脚本：

```bash
python .agents/skills/douyin-hot-sample-research/scripts/summarize_samples.py \
  --downloader-root /Users/pengfei.shi/workspace/tmp-project/douyin-downloader \
  --data-root /Users/pengfei.shi/workspace/tmp-project/douyin-import-service/storage \
  --format markdown
```

汇总结果只作为起点。任何会影响决策的样本，都要继续检查原始 JSON。

浏览器态搜索产物从 `Downloaded/browser_search` 下的 `*_summary.md` 和 `*_gallery.jsonl` 开始看；真正进入样本库决策前，要检查匹配的 `*_raw_responses.json`。

### 6. 账号与评论分析

这一层只对 A 类和强 B 类候选执行。不要把完整分析精力花在每一个搜索结果上。

账号主页分析回答：样本是账号稳定模板，还是单条偶发爆款。

- 可用时采集账号基础资料：`sec_uid`、昵称、简介、粉丝数、总获赞/互动量和作品数。
- 可以先抓取账号全量作品，再只分析最近 N 条，默认 N=20。不要因为 crawler 暂时不能截断就跳过账号分析；如果全量抓取会过慢或失控，明确说明风险和产物路径。
- 比较最近作品流量分布：点赞/评论/收藏/转发的中位数、p75、p90、最大值、最大值与中位数比例、变异系数。
- 把账号模式标为 `stable_template`、`viral_outlier`、`emerging_series` 或 `mixed_account`。
- 稳定重复结构比单条偶发爆款更能作为实验依据。
- 作品少但高流量通常说明机制更容易被拆出来；作品多、粉丝多、账号积累深则是模仿难度的减弱项。

评论分析是一等的选题方向信号：

- 从入选样本的高赞评论和高回复评论开始。
- 给评论聚类打标签，例如 `emotional_resonance`、`identity_projection`、`moral_judgment`、`plot_question`、`request_followup`、`real_story_probe`、`topic_seed` 和 `format_feedback`。
- 记录用户真实在讨论什么，而不只是判断评论正负。
- 用评论里的 `topic_seed` 和 `request_followup` 推出下一轮关键词和选题方向。

决定下一次实验前，必须把文案和评论合并看：

- 比较标题/首图承诺、故事兑现和高赞评论讨论点。
- 输出 `topic_direction`、`story_archetype`、`hook_type`、`payoff_type`、`comment_trigger`、`audience_need`、`replication_angle`、`risk_note` 和 `next_iteration_hypothesis`。
- 每一次策略变化都要写清 `observed_signal`、`strategy_change`、`expected_effect` 和 `review_after`。

策略依据和标签见 `references/multidimensional-analysis-strategy.md`。重点是让未来 Skill 的自我迭代可检查，而不是隐含在聊天里。

### 7. 判断 VL 范围

选择能回答问题的最小图片理解范围。

只判断样本是否值得深挖时，用 `preview_vl`：

- 首图钩子：只传第 1 页；如果钩子跨页，传前 2 页。
- 结尾/兑现：只传最后 1 页；如果反转需要上下文，传最后 2 页。
- 结尾证据检查：明确标注最后一页是插画、真实照片、截图、文档、聊天记录还是证据式图片。
- 真人照片结尾检查：最后一页像真人、真实地点或真实物品照片时，标记 `last_page_real_photo=true`。很多真实故事/改编故事用它增加可信度，也要记录隐私和肖像风险。
- 中段转折：只传相关局部页。
- 记录原始页码，因为 VL 输出会按传入图片重新编号。
- 不要把 `preview_vl` 叫作完整故事文档。

只有样本进入真实候选后，才使用 `full_story_document`：

- 候选为 A/B，且很可能驱动实验或任务创建。
- 理解故事需要完整页序。
- 需要完整 OCR、对白、旁白、分格布局和画面描述。
- 准备把提取结果转成 DoodleStory 分镜或故事方案。

低置信样本不要做全量提取。第一轮要保护注意力、模型成本和复核时间。

### 8. 复用 DoodleStory 现有 VL

DoodleStory 已有抖音图文提取的 VL 链路：

- `backend/app/services/media_text_extraction.py`
  - `extract_ordered_gallery_comic_content(images)` receives ordered `ImageExtractionReference` entries.
  - It submits `image_url.url` entries to the configured `siliconflow_vision_model`.
  - It rejects non-public image URLs and images beyond `MAX_CONTENT_EXTRACTION_IMAGES`.
- `backend/app/api/content_extractions.py`
  - `apply_content_text_extraction(content, db)` loads ordered image media, requires each asset to have public HTTP(S) `public_url`, and writes the VL result to `content.extracted_text`.
- `backend/app/services/llm.py`
  - `parse_extracted_storyboard(...)` converts full extracted text into structured DoodleStory panels when creating a task from extracted content.

`preview_vl` 只把选中的有序图片传入同一低层 VL 模式，结果仅作为研究证据。

`full_story_document` 要对全部有序图集运行完整内容提取路径。只有完成后，结果才可视为源故事文档，并可通过 `parse_extracted_storyboard` 转成分镜。

除非现有路径无法满足明确需求，不要增加第二套 VL 实现。如果样本只有本地文件、没有公网 asset URL，当前 DoodleStory VL 需要先上传/登记为资产；不要静默降级到 base64 或 Codex 截图。

### 9. Codex 人工抽检

Codex 只用于人工或低量理解：

- 用 `view_image` 看少量已下载图片。
- 描述故事结构、首图钩子、结尾兑现、视觉风格、页序和可复刻性。
- 用 Codex 做质性判断和样本库笔记。

Codex 用于探索、复核和决定下一步。只要流程需要 OCR、逐页提取或故事文档，就必须使用上面的 DoodleStory VL 链路。

## 输出

返回简洁的研究报告：

1. 已检查的关键词和热榜词。
2. 使用的新鲜度窗口。
3. 候选表：作品 ID、标题、作者、日期、指标、媒体类型、标签和证据路径。
4. A/B/C/D 分类：
   - A：最近、高互动、图文、可直接进入实验。
   - B：结构强，但需要改造。
   - C：只适合作参考。
   - D：因时间过旧、权利风险、结构弱或非图文依赖而拒绝。
5. 整个 7 天搜索结果的类目横向对比。
6. 账号模仿度和账号探测优先级。
7. 采集到账号证据后，输出账号级判断：`stable_template`、`viral_outlier`、`emerging_series` 或 `mixed_account`。
8. 评论聚类摘要：高赞/高回复讨论、选题种子，以及最可能解释转发或争议的评论触发点。
9. 开头/结尾 VL 摘要，包括最后一页是否是真人照片或证据式结尾。
10. 样本使用真人照片或证据式结尾时，给出原创真实感场景复现路线。
11. 文案和评论综合字段，以及下一轮迭代假设。
12. 下一步下载、评论、账号或 VL 检查动作，并明确标为 `preview_vl` 或 `full_story_document`。

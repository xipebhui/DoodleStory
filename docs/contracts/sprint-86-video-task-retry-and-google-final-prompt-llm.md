# Sprint 86 合同：视频任务重试与最终生图 Prompt 编译 Google 优先

## 目标

给视频任务增加失败后的手动重试能力；同时将图片生成前的最终生图 prompt 编译 LLM 切换为优先使用 Google 模型通道，减少当前图片生成前文本模型调用慢的问题。

## 范围内

- 新增视频任务重试 API，仅允许失败的视频任务重试。
- 如果失败点来自上游图片任务，复用现有图片任务重试逻辑重置上游 `GenerationTask` 并重新入队。
- 如果上游图片已经成功，按失败阶段恢复视频任务：音频阶段失败则重新生成旁白音频，视频阶段失败则复用已成功音频并重新进入视频提交阶段。
- 前端视频任务详情在失败状态展示重试按钮，并调用新 API 后刷新详情和列表。
- 最终生图 prompt 编译 `compose_final_image_prompts` 改用 LIO/Google JSON 通道；不增加 SiliconFlow 兜底。
- 更新规格、进度和回归测试。

## 范围外

- 不自动重试视频任务。
- 不删除历史音频、视频或图片资产文件。
- 不改变 TTS provider、图文视频服务协议或图片 Provider 参数。
- 不修改普通图片任务的用户可见重试入口行为。
- 不新增外部队列、独立 worker 或新的 provider fallback。

## 完成标准

- 失败的视频任务可以从详情页发起重试。
- 上游图片失败时，视频任务回到等待图片，图片任务进入重试队列。
- 音频或视频阶段失败时，视频任务重新进入对应后续 worker 阶段。
- 最终生图 prompt 编译的测试确认使用 LIO/Google 通道。
- 相关后端测试、前端构建和全量检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt backend.tests.test_video_audio_tasks backend.tests.test_video_task_worker
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

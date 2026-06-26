# Sprint 80 合同：视频任务音频与图文视频生成闭环

## 目标

在 Sprint 79 的视频任务骨架上，补齐第一版可执行后半段：上游图片任务成功后，视频任务自动为每个 panel 生成旁白音频，组装 `comic-video-studio` episode，并提交图文视频渲染服务生成最终 MP4。

## 背景

视频任务的上游事实来源仍然是 `GenerationTask`。它负责故事切分、panel 结构、图片文字和图片资产。视频任务只在上游成功后读取这些真实产物，不重新切故事、不改写文案、不伪造音频或视频结果。

`comic-video-studio` 的契约是每个 shot 包含一张视觉素材、一段音频和字幕文本。因此本 sprint 不生成单条全片音频作为唯一产物，而是按 panel 生成多段旁白音频，再提交多 shot episode。

## 范围内

- 新增视频任务后台队列，继续使用进程内队列 + 数据库状态。
- 上游图片任务成功时自动触发关联视频任务继续执行。
- 启动恢复时重新入队可恢复的视频任务。
- 使用 SiliconFlow 参考音频能力生成每个 panel 的旁白音频。
- 当音频参考尚未注册 voice uri 时，使用音频参考文件和参考文本注册声音；缺少参考文本时明确失败。
- 生成的每段旁白音频保存为 `generated_audio` 资产，并关联到视频任务音频分段表。
- 使用本地真实图片资产和音频资产组装 `comic-video-studio` episode。
- 提交 `comic-video-studio` `/api/v1/jobs`，轮询到终态，下载最终 MP4 并保存为 `generated_video` 资产。
- 视频任务详情展示已生成音频分段和最终视频。
- 更新 `docs/spec.md` 与 `docs/progress.md`。

## 范围外

- 不做剪映草稿导出。
- 不做多视频 provider 选择 UI。
- 不做外部队列、独立 worker 服务或分布式锁。
- 不做音频编辑、替换单段音频或手动重跑单段音频。
- 不做视频任务取消、重试按钮和分步重跑 UI。
- 不做真实 provider 凭证的自动创建或兜底 provider 切换。

## 交付物

- `backend/app/core/config.py`
- `backend/app/models/entities.py`
- `backend/alembic/versions/t4b5c6d7e8f9_add_video_task_render_fields.py`
- `backend/app/schemas/video_task.py`
- `backend/app/services/siliconflow_voice.py`
- `backend/app/services/comic_video.py`
- `backend/app/services/video_task_worker.py`
- `backend/app/services/task_worker.py`
- `backend/app/api/video_tasks.py`
- `backend/app/main.py`
- `backend/tests/test_video_task_worker.py`
- `frontend/src/api/client.ts`
- `frontend/src/main.tsx`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- 图片任务成功后，关联视频任务能自动进入音频生成。
- 缺少参考文本、TTS 配置、图片资产、音频资产或渲染服务失败时，视频任务明确失败并写入错误。
- 成功路径会生成音频分段资产，并把 episode 提交给 `comic-video-studio`。
- 渲染成功后最终 MP4 保存为 DoodleStory 资产，前端详情可播放。
- 相关后端单测、迁移、前端构建和全量检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks backend.tests.test_video_task_worker
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

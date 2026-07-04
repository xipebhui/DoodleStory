# Sprint 79 合同：视频任务与音频管理基础能力

## 目标

新增视频任务与音频管理的第一版产品骨架。视频任务创建时用户只输入故事、选择现有画风和参考音频；后端先复用现有生图任务链路完成故事切分、旁白结构和图片生成，再由视频任务承接后续音频与图文视频生成状态。

## 背景

现有 `GenerationTask` 已经负责 `故事文本 + 风格 -> panels + 旁白/图片文字 + 生成图片`。新视频流程不应重写这段逻辑，也不应把图文视频业务硬塞进图片任务表。视频任务需要以图片任务为上游事实来源，额外管理参考音频、旁白音频和最终视频产物。

## 范围内

- 新增音频管理 tab，支持用户上传、列表、搜索、查看和软删除参考音频。
- 新增视频任务 tab，支持列表、搜索、创建和详情。
- 视频任务创建时同步创建一个上游普通生图任务，并保存关联关系。
- 视频任务详情展示上游图片任务状态、已生成分镜图片和参考音频。
- 数据库新增视频任务与音频参考表，并为音频/视频资产增加明确用途。
- 更新 `docs/spec.md` 与 `docs/progress.md`。

## 范围外

- 不接入真实外部图文视频生成 provider。
- 不伪造旁白音频或最终视频结果。
- 不引入外部队列、独立 worker 服务或视频 provider 兜底切换。
- 不改变现有图片任务切分、生图、人物参考、积分扣费逻辑。

## 交付物

- `backend/app/models/enums.py`
- `backend/app/models/entities.py`
- `backend/alembic/versions/s3a4b5c6d7e8_add_video_audio_tasks.py`
- `backend/app/schemas/audio.py`
- `backend/app/schemas/video_task.py`
- `backend/app/api/audio_references.py`
- `backend/app/api/video_tasks.py`
- `backend/app/main.py`
- `frontend/src/api/client.ts`
- `frontend/src/main.tsx`
- `frontend/src/styles/app.css`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- 用户可以在音频管理页上传并查看参考音频。
- 用户可以在视频任务页输入故事、选择风格和参考音频创建视频任务。
- 创建视频任务会创建并关联一个真实的上游 `GenerationTask`，并进入现有图片生成队列。
- 视频任务列表和详情能显示上游图片任务状态，不把未接入的视频生成显示为成功。
- 相关后端测试、前端构建和全量检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

# Sprint 71 合同：最后一张真人照片风格开关

## 目标

在创建任务时增加显式开关 `最后一张真人图片`。默认关闭；用户勾选后，任务最后一个 panel 按真实摄影/真人自拍质感生成，不继续受全局漫画风格参考图和风格提示词约束。

## 范围内

- 创建任务 API 增加 `last_panel_real_photo` 字段，并保存到任务快照。
- 前端创建任务弹窗增加默认不勾选的 `最后一张真人图片` 开关。
- 内容提取复刻创建任务同样透传该字段。
- 最后一个 panel 生成时不携带任务风格参考图和人物参考图，避免漫画参考图把真实照片拉回手绘风。
- 最后一个 panel 的最终生图 prompt 增加真人摄影风格覆盖指令。
- 任务列表和详情返回该字段，便于排查。
- 更新产品规格、进度和回归测试。

## 范围外

- 不自动推断用户是否需要真人风格。
- 不支持任意 panel 单独切换风格。
- 不改变非最后一张图片的风格参考、人物参考和最终 prompt 逻辑。
- 不重新生成历史任务。

## 交付物

- `backend/app/models/entities.py`
- `backend/alembic/versions/r2f3a4b5c6d7_add_last_panel_real_photo.py`
- `backend/app/schemas/task.py`
- `backend/app/schemas/content_extraction.py`
- `backend/app/services/task_creation.py`
- `backend/app/services/task_worker.py`
- `backend/app/api/tasks.py`
- `backend/app/api/content_extractions.py`
- `backend/tests/test_task_worker_prompt.py`
- `frontend/src/api/client.ts`
- `frontend/src/main.tsx`
- `frontend/src/styles/app.css`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- 新任务默认 `last_panel_real_photo=false`。
- 用户勾选后，任务记录保存 `last_panel_real_photo=true`。
- 最后一个 panel 的 reference pack 为空，不携带漫画风格参考图或人物参考图。
- 最后一个 panel 的最终 prompt 明确要求真实摄影/真人自拍质感，并禁止漫画、手绘、线稿、绘本风。
- 非最后一个 panel 不受影响。
- 相关测试、前端构建和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
backend/.venv/bin/alembic upgrade head
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 最后一张真人照片会牺牲与前面漫画图的人物参考一致性；这是用户显式勾选后的预期行为。
- 如果最后一页仍要求大量图片内文字，真实照片风格下文字可读性仍取决于图片模型执行能力。

# Sprint 67 合同：人物参考图提示词查看

## 目标

让任务详情页里已经生成的人物参考图，也能像 panel 生图一样查看当时发送给图片模型的最终提示词，方便排查人物参考图质量和风格一致性。

## 范围内

- 任务详情接口返回人物参考图对应的 `reference_prompt`。
- 前端人物参考图卡片在存在提示词时展示查看入口。
- 查看入口复用现有 prompt 弹窗。
- 增加回归测试覆盖人物参考图提示词序列化。

## 范围外

- 不重新生成历史人物参考图。
- 不为固定角色参考图补造提示词；固定角色使用用户已有图片，可能没有人物参考图生成 prompt。
- 不改变人物参考图生成逻辑、扣费逻辑或 Provider 请求参数。

## 交付物

- `backend/app/models/entities.py`
- `backend/app/schemas/task.py`
- `backend/tests/test_user_characters.py`
- `frontend/src/api/client.ts`
- `frontend/src/main.tsx`
- `frontend/src/styles/app.css`
- `docs/progress.md`

## 完成标准

- 临时人物参考图生成成功后，任务详情人物参考卡片可打开完整人物参考图提示词。
- 固定角色或没有保存提示词的人物参考卡片不显示空入口。
- 现有 panel 生图提示词查看不受影响。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_user_characters
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 老任务如果人物参考图生成时未保存 `reference_prompt`，前端不会显示查看按钮。

# Sprint 76 合同：风格参考图上传可靠性加固

## 目标

修复风格创建和编辑时参考图上传慢、用户关闭弹窗或重复操作导致状态不一致的问题，并增强后端上传文件校验。

## 背景

风格创建时当前流程是先保存风格基础信息，再逐张上传新选的参考图；编辑风格时选择文件后立即上传参考图。旧交互只在创建保存按钮上显示 `saving`，编辑上传没有独立上传中状态，保存或上传期间仍可关闭抽屉、重复选择文件、删除参考图或删除风格。后端上传入口只依赖客户端声明的 `content-type` 判断图片格式，也没有单文件大小上限。

## 范围内

- 创建保存和编辑上传期间统一进入 busy 状态。
- 保存或上传期间禁止关闭风格抽屉，避免用户以为操作已结束。
- 编辑上传期间显示上传中状态和逐张上传进度。
- 上传期间禁止重复上传、删除参考图、删除风格和再次提交保存。
- 后端上传图片限制单文件最大 10MB。
- 后端使用 PIL 校验上传内容必须是真实 PNG、JPEG 或 WebP 图片。
- 后端拒绝客户端声明类型与真实图片内容不一致的文件。
- 增加上传校验单元测试。

## 范围外

- 不改变风格创建、编辑、删除和上传接口的角色权限模型。
- 不把风格创建和参考图上传合并成一个事务接口。
- 不增加断点续传、后台上传队列或对象存储直传。
- 不修改生图风格参考和人物参考逻辑。

## 交付物

- `frontend/src/main.tsx`
- `frontend/src/styles/app.css`
- `backend/app/services/storage.py`
- `backend/tests/test_storage_upload.py`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- 创建风格上传参考图时，保存过程中不能关闭抽屉或重复提交。
- 编辑风格上传参考图时，能看到上传中状态，且不能重复上传或删除参考图。
- 伪造图片、内容类型不一致图片、超过 10MB 图片会被后端明确拒绝。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_storage_upload backend.tests.test_style_delete
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

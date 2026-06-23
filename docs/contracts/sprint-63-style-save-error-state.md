# Sprint 63 合同：风格保存错误状态修复

## 目标

修复风格保存时同名风格导致的 500 和不清晰 loading 体验，让用户能明确知道保存失败原因，以及创建风格时当前处于基础信息保存还是参考图上传阶段。

## 范围内

- 风格创建和编辑时，重复风格名称返回 400 业务错误。
- 风格名称保存前去除首尾空白。
- 保留数据库唯一约束作为最终一致性保护，并把并发写入导致的唯一约束异常转换成业务错误。
- 前端创建风格时区分“创建/保存风格”和“上传参考图”两个 loading 阶段。
- 增加后端单元测试覆盖重复创建和重复改名。

## 范围外

- 不重构风格测试为异步图片 job。
- 不改变风格参考图上传的存储后端。
- 不清理历史 `style_tests.running` 数据。
- 不改变风格名称唯一性规则。

## 交付物

- `backend/app/api/styles.py`
- `backend/tests/test_style_delete.py`
- `frontend/src/main.tsx`
- `docs/progress.md`

## 完成标准

- 创建同名风格时返回明确的“风格名称已存在，请换一个名称”。
- 编辑风格改成已有名称时返回同样的业务错误。
- 前端保存按钮能显示当前保存阶段。
- 后端测试、前端构建和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend/tests/test_style_delete.py
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 风格测试仍是同步生图请求，后续需要单独改造成图片 job，才能彻底解决风格测试长请求和重启后 running 状态残留问题。

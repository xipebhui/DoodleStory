# Sprint 74 合同：人物参考图失败后任务重试

## 目标

修复人物参考图第三方接口偶发失败后，用户点击任务重试仍然秒失败的问题。

## 范围内

- 任务重试时重置失败的 `task_character_appearances` 状态。
- 清理失败人物外观上的错误码、错误信息、provider request id 和旧 reference prompt。
- 保留旧的失败 `character_reference` 图片 job 作为历史记录。
- 让下一轮任务执行重新创建人物参考图 job。
- 增加回归测试覆盖失败人物参考在 retry 时被重置。
- 更新进度记录。

## 范围外

- 不改变图片 Provider。
- 不自动切换模型或引入降级路径。
- 不自动重跑历史任务或消耗用户积分。
- 不改变 panel 图片重试规则。

## 交付物

- `backend/app/api/tasks.py`
- `backend/tests/test_user_characters.py`
- `docs/progress.md`

## 完成标准

- 第三方人物参考图 job 失败后，点击任务重试不会因为旧 appearance failed 状态直接失败。
- 旧失败 job 保留，新的人物参考图 job 由现有 worker 链路重新创建。
- 相关测试和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_user_characters backend.tests.test_task_worker_recovery
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

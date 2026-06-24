# Sprint 64 合同：风格参考图快照完整性修复

## 目标

修复线上任务单分镜修改时因历史风格参考图资产被删除而反复失败的问题，让任务快照引用的资产不会被风格库编辑误删，并让已损坏快照返回明确错误而不是 `AttributeError` 或 500。

## 范围内

- 删除风格参考图时，如果文件资产仍被历史任务风格参考图快照引用，只删除风格库关联，不物理删除文件资产记录。
- SQLite 连接启用外键约束，避免后续绕过数据库完整性保护。
- 单图修改加载任务时补齐任务风格参考图快照及其文件资产。
- 构建风格参考图请求时，如果快照资产缺失，返回明确的 `ImageProviderConfigError`。
- 增加回归测试覆盖历史任务快照资产保留和损坏快照错误。

## 范围外

- 不把损坏任务自动切换到当前风格参考图。
- 不自动用当前风格参考图替换历史任务快照。
- 不重建已经缺失且无法从备份完整恢复的历史参考图资产。
- 不改变图片 Provider 或模型配置。

## 交付物

- `backend/app/api/styles.py`
- `backend/app/core/database.py`
- `backend/app/services/style_references.py`
- `backend/app/services/task_worker.py`
- `backend/tests/test_style_delete.py`
- `backend/tests/test_task_worker_prompt.py`
- `docs/progress.md`

## 完成标准

- 历史任务快照引用的风格参考图资产不会因删除风格库参考图被删除。
- 损坏任务快照在生成或单图修改时显示明确错误。
- 相关后端测试、编译和全量检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_style_delete backend.tests.test_task_worker_prompt
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 线上任务 `138f53d7e7be489e8f893a609f382773` 的历史快照当前指向 7 个已经不存在的文件资产；备份中只找到其中 1 个，无法完整恢复原始快照。若要让该任务继续按参考图模式修改，需要用户确认采用哪种数据修复策略。

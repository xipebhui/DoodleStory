# Sprint 62 合同：人物参考图统一图片 Job

## 目标

把任务内临时人物参考图生成从任务主流程里的同步 Provider 调用，改为和 panel 生图一致的统一图片 job。人物参考图和 panel 图共享图片 worker、全站并发、单用户并发、lease、attempt、重启恢复、积分占用与失败记录语义。

## 范围内

- 扩展 `generated_images` 为通用图片生成 job，新增 `job_kind` 和 `character_appearance_id`。
- `panel_id` 改为可空；旧 panel 图片 job 统一标记为 `panel_image`。
- 人物参考图生成阶段只创建 `character_reference` 图片 job，不再同步调用图片 Provider。
- 统一 image worker 根据 `job_kind` 分发：
  - `panel_image` 继续生成 panel 图。
  - `character_reference` 生成人物参考图并写回 `task_character_appearances.reference_image_id`。
- 人物参考图 job 成功、失败、积分占用、释放和扣费与 panel 图使用同一套图片 job 状态。
- 启动恢复支持 `generate_character_references` 阶段：有活跃人物图 job 则继续等待，无活跃 job 但人物参考未完成则重新入队。
- 防止重启或重复 claim 后的旧 Provider 返回结果覆盖新 attempt。
- 任务详情 API 继续只把 panel 图片放入 `generated_images`，人物参考图仍通过 `character_references` 展示。

## 范围外

- 不引入 Redis、Celery、外部队列或独立 worker 服务。
- 不新增前端页面。
- 不改变用户角色库的长期角色保存方式。
- 不重跑历史任务的人物参考图。

## 交付物

- `backend/app/models/enums.py`
- `backend/app/models/entities.py`
- `backend/alembic/versions/q1e2f3a4b5c6_add_character_reference_image_jobs.py`
- `backend/app/services/character_references.py`
- `backend/app/services/task_worker.py`
- `backend/app/api/tasks.py`
- `backend/tests/test_task_worker_recovery.py`
- `docs/spec.md`
- `docs/progress.md`

## 完成标准

- 人物参考图生成不再阻塞任务主 worker 的同步执行。
- 人物参考图和 panel 图都由统一 image worker 领取和处理。
- 服务重启后，人物参考图 job 能像 panel 图一样从 DB 状态恢复。
- 任务详情 `generated_images` 不包含人物参考图 job。
- 相关后端测试、前端构建和全量检查通过。

## 验证

```bash
backend/.venv/bin/python -m compileall backend/app
backend/.venv/bin/alembic upgrade head
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

## 风险 / 说明

- 远程部署前必须先备份数据库并执行 Alembic 迁移；远程当前如果仍停留在 `n9c0d1e2f3a4`，需要先补上 `p0d1e2f3a4b5`，再升级到本 Sprint 的 `q1e2f3a4b5c6`。
- 历史孤儿 `generated_images.running` 不应盲目重新排队，需要在部署前按任务上下文清理或标记中断，避免重复出图和扣费。
- 本 Sprint 期间根据线上硅基流动账号余额不足问题，将文本 LLM 与 VL 调用切换到 LIO OpenAI Chat Completions 兼容接口；该变更不改变图片 job 数据结构，但会影响人物提取、最终生图 prompt 编译、单图修改 prompt 重写、角色参考图描述和内容提取 VL 的外部模型配置。
- 长故事与入口统一已纳入本 Sprint 的后续修正：完整故事不再使用程序断句 chunk，改为 LIO 文本 LLM 按语义、场景和情绪节奏生成 storyboard panels 和 continuity_plan；用户原文仍原样保存，panel 文本允许轻微语义整理，但不得改变事实、顺序、人物关系、关键台词含义或新增剧情。故事方案、提取分镜和 DY 爆款复刻继续统一进入页式分镜中间态。最终生图 prompt 编译按 `LLM_PANEL_BATCH_SIZE` 分批调用，默认 10，并携带 compact storyboard context。该变更不改数据库结构，也不改变图片 job 队列。

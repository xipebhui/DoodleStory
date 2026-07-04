# Sprint Contract

## Sprint Name

`admin-video-audio-visibility`

## Goal

将视频任务和音频管理从普通用户能力收紧为管理员能力，确保普通用户不能在导航、直接 URL、API 或文件资产入口看到或操作相关内容。

## In Scope

- 普通用户左侧导航不展示 `视频任务` 和 `音频管理`。
- 普通用户直接访问 `/video-tasks` 或 `/audio-references` 时不渲染对应页面。
- 后端视频任务和音频参考 API 仅允许管理员访问。
- 音频参考、生成旁白音频和生成视频资产仅允许管理员读取。
- 更新产品规格和进度记录。

## Out of Scope

- 不删除历史视频任务、音频参考或文件资产。
- 不改变视频任务生成流程、TTS 流程、图文视频导出服务地址或任务 worker。
- 不新增角色体系、组织权限或更细粒度 RBAC。

## Deliverables

- 前端导航和路由守卫更新。
- 后端视频任务、音频管理和资产读取权限更新。
- 权限回归测试。
- `docs/spec.md` 与 `docs/progress.md` 更新。

## Done Means

- 管理员仍可进入视频任务和音频管理并调用对应 API。
- 普通用户不能通过 UI、API 或文件资产接口访问视频任务和音频管理资源。
- 现有视频任务和音频任务核心测试通过。
- 前端生产构建通过。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
```

Manual or QA checks:

- 使用普通用户访问 `/video-tasks` 和 `/audio-references` 时页面不展示对应管理功能。
- 使用管理员账号确认左侧导航仍展示视频任务和音频管理。

## Risks / Notes

- 历史普通用户创建的视频任务和音频参考不会被迁移或删除，只是访问入口被收紧为管理员。

## Handoff

- Next likely step: 如需继续收紧业务数据归属，可单独讨论是否迁移历史视频任务 owner 或做后台管理筛选。

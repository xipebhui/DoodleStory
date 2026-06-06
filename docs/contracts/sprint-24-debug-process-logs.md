# Sprint 24 合同：内容提取与故事画图过程日志

## 目标

为本地排查补充可直接查看的过程日志，让内容提取和故事画图两条链路能通过后端日志按任务 ID 追踪每一步。

## 范围内

- 内容提取流程增加 `content_extraction_debug` 日志前缀。
- 记录内容提取任务创建、抖音下载开始与结果、媒体登记、图文逐页识别、二次 LLM 整理、视频转写、故事总结、后台任务提交点和失败信息。
- 故事画图流程增加 `story_drawing_debug` 日志前缀。
- 记录生成任务开始、故事方案规划、完整故事分段、风格参考图准备、人物识别、人物参考图生成、panel prompt 采纳、final prompt 准备、图片 Provider 请求、单图成功/失败和任务完成。
- 日志使用现有 Python logging 输出到后端日志文件，不新增环境变量、不新增数据库字段。

## 范围外

- 不改变业务流程、模型 prompt、任务状态或数据库 schema。
- 不把日志写入前端页面。
- 不新增远程日志采集、链路追踪系统或单独调试服务。
- 不输出 Authorization、API key 或图片 base64 原文。

## 完成标准

- 后端日志可用 `content_extraction_debug` grep 内容提取过程。
- 后端日志可用 `story_drawing_debug` grep 故事画图过程。
- `backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。
- 本地后端服务重启后加载新日志代码。

# Sprint 129：Native 语音 ffprobe 可执行路径

## Status

Complete。用户于 2026-07-28 要求终止正在重复失败的 Native Agent 任务，并修复火山语音未返回
时长时后端找不到 `ffprobe` 的问题。

## Goal

让语音真实时长探测使用显式、可审计的 `FFPROBE_EXECUTABLE`，本地启动脚本把当前已安装的
绝对路径传给后端，避免依赖子进程继承的 PATH。

## In scope

- 终止 Run `22a69626bdcc4902a9bc4361c680886f`，停止后端进程并把 Run 标记为 cancelled。
- 新增 `FFPROBE_EXECUTABLE` 配置，语音时长探测使用该可执行文件。
- 本地重启脚本启动前解析并校验 `ffprobe` 绝对路径，再显式传给后端。
- 更新示例环境变量和单元测试。
- 使用真实火山语音响应验证 Provider 未返回时长时能完成本地探测。

## Out of scope

- 自动恢复或重放已终止 Run。
- 为失败 Run 自动补音频、重新生图或生成视频。
- 用文本长度估算音频时长。

## Done means

- 被终止 Run 保持 cancelled，重启后不恢复。
- 后端进程获得可执行的绝对 `FFPROBE_EXECUTABLE`。
- 真实语音能返回大于零的 `duration_ms`。
- `./scripts/check.sh` 与 `git diff --check` 通过。

## Verification result

- Run `22a69626bdcc4902a9bc4361c680886f` 已停止并保持 `cancelled`，重启后 active Run 为空。
- 本地启动解析到 `FFPROBE_EXECUTABLE=/opt/homebrew/bin/ffprobe`，后端启动成功。
- 真实火山语音 smoke 返回 32301 bytes MP3、4032ms，Provider request ID
  `2026072814495173DC27A9B1A317DB420F`。

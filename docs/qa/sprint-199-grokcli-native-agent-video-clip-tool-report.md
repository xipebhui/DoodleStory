# Sprint 199 grokcli Native Agent AI 视频短镜头验收记录

状态：代码验收通过，真实媒体验收被 `xai_video_credits_or_subscription` 阻断。

## 已通过

- 依赖固定为 `ele-yufo/grokcli` commit
  `2dcd4d4b2dc6c35f013a6b2a826721e4b98bfe13`（0.2.0，MIT）。
- `generate_video_clip` 已进入 Native Runtime、Skill Tool Catalog、Capability API 与前端名称映射。
- T2V / 当前 Conversation 单图 I2V、1–15 秒、七种比例和服务端模型/分辨率配置均有严格校验。
- 每次调用只执行一个 `grokcli video`，不自动重试、不切换 Provider；认证、额度、超时、网络和
  内容审核按上游退出码明确失败。
- 输出限制在独立临时目录的唯一文件，并经 MP4 magic 与 ffprobe H.264、容器、宽高、时长、帧率、
  帧数校验。
- 成功结果复用 `generated_video` / `NativeAgentVideo`，快照保存 Provider、模型、模式、Prompt、
  源图片、请求参数和 grokcli 版本；同一成功 Tool Call 重放不再次调用 Provider。
- Windows 下图片与视频适配器共享单进程 grokcli 锁，弥补上游 `fcntl` 在 Windows 的 no-op；
  项目现有单实例约束仍是运行前提。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| Grok/Native 聚焦测试 | 65 项通过 |
| 后端全量测试 | 432 项通过 |
| 前端测试 / build | 14 项通过 / build 通过 |
| Remotion typecheck / tests | 通过 / 8 项通过 |
| 空 SQLite Alembic upgrade | 通过 |
| 内容迭代控制器校验 | `ok=true`，无 warning |
| `compileall` / `git diff --check` | 通过 |
| 上游 grokcli 测试 | Windows 346/352 通过；6 项为 POSIX 权限、端口复用与文件锁平台差异 |

## 真实调用

- Windows 项目虚拟环境已安装并确认 `grokcli 0.2.0`；浏览器 OAuth 登录成功。
- 只提交一次 Paynes Creek S03、8 秒、16:9、720p I2V。
- xAI 在提交阶段返回退出码 4 / HTTP 403，含义为视频额度或订阅不可用；没有生成 MP4。
- 未重试、未切换到 SiliconFlow、Wan 或其他 Provider。
- 脱敏记录：`docs/testing/paynes-creek-grok-video-smoke-2026-08-13.json`。

## 剩余条件

账号恢复 xAI 视频 credits 或对应订阅后，显式重新运行一次 smoke 并验收真实 MP4；在此之前不能把
Sprint 199 状态改为 Complete，也不能把当前结果描述成已生成可上传视频。

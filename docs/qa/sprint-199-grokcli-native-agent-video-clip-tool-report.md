# Sprint 199 grokcli Native Agent AI 视频短镜头验收记录

状态：Complete，代码与真实媒体验收均通过。

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
- 初始账号状态曾返回退出码 4 / HTTP 403，脱敏记录保留在
  `docs/testing/paynes-creek-grok-video-smoke-2026-08-13.json`，没有自动重试或切换 Provider。
- 账号恢复后，第一次显式复验已生成视频，但本地 `.env` 仍指向 macOS
  `/opt/homebrew/bin/ffprobe`，校验失败且临时文件按设计清理；记录保留在 attempt 02。
- 明确改用 Windows `C:/ProgramData/chocolatey/bin/ffprobe.exe` 后，7 项适配器测试通过；后续显式调用
  成功保存 8.042 秒、1280×720、24fps、H.264 MP4。最终选中版本为 attempt 04，文件 10,091,881
  bytes，SHA-256 `5b6a1f9bb3e141eade11ec388be1b4e8ef0588b22193790c436ab026bb0457ec`。
- 四点接触表确认盐土托盘、漏斗、液流与陶罐关系在运镜中保持；未出现文字、现代器件或明显形变。
- 所有 attempt 均未切换到 SiliconFlow、Wan 或其他视频 Provider。

## 结论

Sprint 199 的“Native Agent 可生成、校验、保存真实 Grok 短镜头”目标已满足。该 8 秒资产仍只是镜头，
不是可上传完整成片；五镜 AI 样片的合成与验收由 Sprint 200 独立承担。

# Sprint 200 Paynes Creek Grok AI 五镜短片验收记录

状态：Complete，终态 `pass_local_ai_short`。

## 产物

- 最终视频：`storage/exports/paynes-creek/grok-ai-short-v1/paynes-creek-grok-ai-short-v1-yuv420p.mp4`
- 时长：41.856 秒
- 文件大小：37,294,529 bytes
- SHA-256：`e6b1089b084b21411ef4ee73df16920dfd6c0ee5be29aaa670258da0d5ac7b98`
- Profile：1920×1080、30fps、H.264/AAC、yuv420p、tv range、1254 帧
- 发布授权：`false`

## 真实调用

| 类型 | 调用 | 选中 | 说明 |
| --- | ---: | ---: | --- |
| Grok 图片 | 6 | 5 | 一张火上结晶图片因陶器与火焰关系错误被明确否决 |
| Grok 视频 | 7 | 5 | 两条为 FFprobe 配置失败后的技术产物或旧错误首帧验证 |
| SiliconFlow TTS | 1 | 1 | `FunAudioLLM/CosyVoice2-0.5B:alex`，41.796 秒 |
| Remotion | 1 | 1 | `paynes-creek-grok-ai-short-v1` |
| FFmpeg 规范化 | 1 | 1 | pc → tv range，yuv420p |
| 发布 | 0 | 0 | 未创建 YouTube 任务 |

所有生成均未自动重试、未切换 Provider、未使用 BGM。内容失败只在人工复核后建立独立新 attempt。

## 视觉检查

- S01：海岸盐作棚、泻湖和光路稳定，运镜没有新增建筑或文字。
- S03：盐土托盘、木质漏斗、液流和陶罐始终保持垂直关系，液流终止于罐内。
- S04：陶盆、黏土支座与正下方火焰关系稳定，只有蒸汽、火焰和轻微镜头变化。
- S09：独木舟、木桨和模糊包裹稳定，没有把未知货物变成确定盐饼或货单。
- S12：证据链保留开放结尾，没有生成文字、具体买家或闭合路线。
- 五镜中点接触表与 20 帧高密度接触表中的标题、证据标签和中文逐镜字幕均可读。

## 技术检查

- 完整视频和音频流解码通过，ffmpeg 未报告错误。
- ffprobe：H.264 / AAC、1920×1080、30fps、1254 帧、41.856 秒。
- 音频相对视频流只长 56ms；没有超过 1.5 秒、低于 -45dB 的静音段。
- Python Grok/Runner 聚焦 10 项、Remotion 11 项、TypeScript typecheck、JSON 校验、敏感信息扫描与
  `git diff --check` 均通过。

## 边界

该结果证明项目已经能用 Grok AI 图片和视频制作一条完整、可播放的中文短片，不代表 YouTube 市场验证，
也不代表原 G4 随机图片 Gate 通过。音频内容没有另行运行 ASR 逐字校验，最终上传前仍应由用户完整观看；
当前明确禁止自动发布。


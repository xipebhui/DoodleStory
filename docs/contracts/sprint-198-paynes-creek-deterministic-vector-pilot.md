# Sprint 198：Paynes Creek 确定性矢量本地样片

状态：Complete（本地矢量样片、媒体规范化、逐镜视觉复核与技术 QA 均已完成；未授权发布）

## Goal

在不继续消耗随机图片调用的前提下，把已审计的 Paynes Creek 12 镜中文脚本制作成一支真实可播放的本地
MP4。画面改为 Remotion 内联矢量动画，以代码锁定对象坐标、证据层级、字幕安全区和运动；旁白使用一次
SiliconFlow `FunAudioLLM/CosyVoice2-0.5B` 系统预置音色调用。

## Why this slice

- G4 Attempt 02–04 已证明自由生图可分别产生现代器件、伪文字、多余对象和关键机制倒置；第三轮即使 VL
  满分也被事实 / 视觉复核否决。
- 该首片是机制解说，木槽、陶罐、船桨、独木舟、作业空间和证据边界都可用确定性几何表达；不需要用
  随机图片模拟摄影质感。
- 当前用户明确授权先完成视频；本 Sprint 只改变首片的视觉生产方法，不改变事实脚本、不发布。

## Authorization and external-call boundary

- 用户当前完整本地视频制作授权覆盖本 Sprint 的一次 TTS 请求和一次本地 Remotion 渲染。
- TTS 固定直连已配置的 SiliconFlow `/audio/speech`：模型
  `FunAudioLLM/CosyVoice2-0.5B`，系统预置音色
  `FunAudioLLM/CosyVoice2-0.5B:alex`，`mp3 / 32000 Hz / speed 1.0 / gain 0`；不上传音色、不重试、
  不切换模型或 Provider。
- 视觉完全本地确定性渲染，不调用图片或视频生成 Provider。BGM 为空。
- 禁止 YouTube 上传、外部消息、远端发布或把本地成片标记为市场验证通过。

## In scope

1. 新增 `paynes-creek-vector-v1` Remotion Composition，固定 1920×1080、30fps、H.264/AAC、yuv420p。
2. 用 12 个场景组件表达既有 S01–S12：海岸到内陆、年代地点、浓缩重建、陶器加热、居住与盐厨房、
   超出自用、散盐 / 盐饼、1.43 米木桨、合理但未知的独木舟货载、内陆交换网络、后期淹没、已知 / 未知
   证据边界。
3. 从 `paynes-creek-production-draft.json` 读取 12 段旁白，不改写原文；一次生成完整旁白 MP3，并以
   ffprobe 真实时长按每镜汉字权重分配 Scene 时间，首尾各保留短停顿。
4. 每镜显示受控中文字幕、Scene ID、证据标签；S03 / S07 / S09 / S10 的“重建 / 可能 / 不等于 /
   不知道 / 未知”限定词必须原样保留。
5. 输出 MP4、音频、规范 Manifest、ffprobe 报告、帧接触表、SHA-256 和本地验收记录到
   `storage/exports/paynes-creek/vector-pilot-v1/`。
6. Remotion 原始 MP4 若实际标记为 `yuvj420p`，保留该原始文件，并以一次固定 FFmpeg
   `scale=in_range=pc:out_range=tv,format=yuv420p + libx264 CRF 18 + AAC copy` 生成独立最终文件；这是一项
   固定交付规范化步骤，不重发 TTS、不重跑 Remotion，也不覆盖原始文件。

## Out of scope

- 修改前三个 G4 失败结论、把随机候选图标记为 approved、继续生图或调用图像编辑。
- 新建通用矢量视频编辑器、数据库迁移、前端页面、队列、发布流程或 YouTube 上传。
- 声音克隆、BGM、音效、缩略图、标题 / 描述 / SEO、频道选择和市场实验。

## Done means

- 12 镜、旁白逐字 hash、证据标签和 Scene 顺序与生产草案一致。
- 只有一次 TTS Provider 请求；响应非空、可由 ffprobe 解码，真实音频时长写入 Manifest。
- Remotion typecheck / tests 及新增 Manifest 测试通过；渲染只执行一次并生成非空 MP4。
- ffprobe 证实 1920×1080、30fps、H.264、AAC、yuv420p，视频时长与旁白时长误差不超过一帧。
- 抽取 12 个中点帧形成接触表并逐镜视觉复核；S03 必须明确表现木槽在上、陶罐在下、液流终止罐内。
- 输出和报告不含密钥、Authorization、绝对凭据路径或发布授权；`publication_authorized=false`。

## Verification

```powershell
npm run typecheck --prefix remotion
npm test --prefix remotion
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_paynes_creek_vector_pilot
& backend/.venv/Scripts/python.exe -m compileall scripts/run_paynes_creek_vector_pilot.py
py -3.11 .agents/skills/content-iteration-controller/scripts/validate_controller_state.py
git diff --check
```

## Handoff

- 通过：交付本地 MP4 与可审计媒体报告；是否上传、用哪个频道和何时发布仍需独立确认。
- 失败：保留实际音频或渲染证据并停止，不自动换音色、模型、Provider 或渲染实现。

## Observed initial execution

- 唯一一次 TTS 已生成 115.704 秒 MP3，SHA-256
  `edc097f0623da8e2d4fe9a245bea3ebbd6756e4ee2548283ad044d84ee11875f`；唯一一次 Remotion 已生成
  3472 帧原始 MP4，SHA-256 `b6f15480a3675bb63048511ec1aedcc050d63f986ea82f9ffe3f760adebe1db3`。
- 原始 MP4 的 H.264 / AAC / 1920×1080 / 30fps 均通过，视频流 115.733 秒，与源旁白相差 29ms；容器
  115.776 秒来自 AAC 尾部填充，不能代替视频流时长做一帧门禁。
- Remotion 虽请求 `yuv420p`，ffprobe 实际观测为全范围 `yuvj420p`。1 秒只读方案探针证明上述固定 FFmpeg
  规范化可得到 `yuv420p / color_range=tv`。下一步只处理已生成的精确三文件，不再次调用 TTS 或 Remotion。

## Observed final result

- 固定规范化只执行一次，最终 MP4 为 1920×1080、30fps、H.264 / AAC、`yuv420p / color_range=tv`，
  3472 帧、容器时长 115.776 秒；视频流与 115.704 秒源旁白仅相差 29ms，不超过一帧。
- 最终 MP4 SHA-256 为 `e063e02009c8dfc109781b8f030134fd36dc327c368816efd86f919d523d6a09`；完整
  视频 / 音频解码通过，未检测到超过 1.5 秒的长静音，音频均值 / 峰值分别为 -28.3 / -0.8 dB。
- 12 个中点帧和 S03 专项帧已复核：镜头齐全、顺序正确、受控字幕可读；S03 明确为木槽在上、陶罐在下、
  液流终止罐内。11 个镜头边界距最近自然停顿最大 0.780 秒，满足本地样片节奏检查。
- 唯一 TTS、唯一 Remotion、唯一 FFmpeg 规范化均无重试；图片、VL、视频生成 Provider 和发布调用均为 0。
  决策为 `pass_local_vector_pilot`，只表示本地确定性制作验证通过；原 G4 随机图片 Gate 仍失败，G5 未开放，
  `publication_authorized=false`。
- 未执行 ASR 转写：当前可用 ASR Skill 要求另一次显式确认。旁白输入由 SHA-256 锁定，技术音频 QA 已通过，
  但发音准确性尚未由独立转写复核。

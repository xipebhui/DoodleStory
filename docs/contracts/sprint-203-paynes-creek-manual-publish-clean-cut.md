# Sprint 203：Paynes Creek 英文手动发布清理版

状态：In progress

## Goal

在不重新生成旁白、图片或视频镜头的前提下，把 Sprint 202 已通过音画同步与技术校验的英文留存版
转成一条可直接交给用户手动上传的干净成片：画面和交付文件名不出现独立 `AI` 标识，也不显示
`PHRASE x/y` 等制作期计数器。

## In scope

1. 为五镜 Remotion 模板新增显式 `manual_publish` presentation mode；既有计划显式保留 `review`，
   历史复跑语义不变。
2. `manual_publish` 渲染隐藏短语计数器，保留短语字幕、钩子、镜头标题、证据等级、证据图层和页脚。
3. 发布计划复用 Sprint 202 Attempt 5 的旁白 hash、1170 帧 source-aligned 时间轴和五个 Grok 镜头
   hash，不新增 Provider 调用。
4. Runner 与 Manifest 在渲染前拒绝可见文案中的独立 `AI` 字样，并拒绝 artifact slug 中独立的
   `ai` token。
5. 输出独立的 1920×1080、30fps、H.264/AAC、yuv420p MP4、接触表与审计记录。

## Out of scope

- 不重写脚本、旁白、事实主张或证据等级。
- 不重新调用 Grok、SiliconFlow、音乐或其他 Provider。
- 不自动上传 YouTube，不修改频道、标题、描述、封面或公开视频状态。
- 不覆盖 Sprint 202 的 v5 成片。

## Done means

- 既有 review 计划与新的 manual-publish 计划均通过 Python、Manifest 与 TypeScript 校验。
- 新产物文件名、页脚和全部画面可见文案不包含独立 `AI` 标识，短语字幕上方不显示
  `PHRASE x/y`。
- 最终 MP4 保持 39 秒级、1920×1080、30fps、H.264/AAC、yuv420p/tv range，完整解码通过。
- 高密度接触表覆盖钩子、字幕切换、五个场景及收尾，并确认无黑场、溢出和制作期标签。
- 调用账本记录 TTS=0、Grok=0、音乐=0、发布=0、Remotion=1、FFmpeg=1。

## Verification

```powershell
python -m unittest backend.tests.test_paynes_creek_grok_ai_short
node --test remotion/tests/paynes-creek-grok-short-manifest.test.mjs
npm --prefix remotion run typecheck
python scripts/run_paynes_creek_grok_ai_short.py --preflight ...
python scripts/run_paynes_creek_grok_ai_short.py --execute ...
ffmpeg -v error -i <final.mp4> -f null NUL
```

另检查最终 Manifest、ffprobe、SHA-256、中点接触表和高密度接触表，并对渲染帧执行一次机械视觉扫描。

## Handoff

向用户提供不含 `AI` 命名的最终 MP4 绝对路径；`publication_authorized=false` 只表示项目未被授权
自动操作外部频道，不限制用户自行上传该本地文件。

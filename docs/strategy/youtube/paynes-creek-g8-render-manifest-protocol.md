# Paynes Creek G8 冻结 Render Manifest 与单次成片协议

更新时间：2026-08-12
状态：协议已设计；G8-B 未实施，12 组媒体与最终 Manifest 均不存在
用途：把 G4–G7 已审核资产确定性地交给一次 G8 本地渲染；不是发布授权

## 1. 一句话结论

G8 不能让模型根据“最新资产”自由拼片。12 张图片和 12 对 Audio / Subtitle 全部通过后，先按叙事顺序
填写 Manifest 请求，由认证用户逐项确认，再由服务端编译出不可变 hash。专用 G8 Run 只允许零参数触发
一次渲染；技术成功后仍必须人工完整观看。

## 2. 前置 Gate

| Gate | 必须状态 | 需要的证据 |
| --- | --- | --- |
| G0 / G1 | `pass` | 来源账本、12 镜脚本与证据板 |
| G2 | `pass_offline` | Native 路由与 Chat 适配离线通过 |
| G3 | `pass_for_s03_single_image_review` | 零媒体真实兼容性记录 |
| G4 | `pass_for_s01_anchor` | S03 图片 / VL / 两类人工审核 |
| G5 | `pass_for_remaining_image_plan` | S01、S04 锚点分别通过 |
| G6 | `pass_for_g7_audio_subtitle_plan_review` | 其余九镜逐镜通过 |
| G7-0 | `pass_for_g7_scene_runs` | 同会话跨 Run 媒体 lineage 离线通过 |
| G7 | `pass_for_g8_render_plan_review` | 12 对 Speech / Subtitle 逐镜语言审核通过 |
| G8-A | `pass_for_g8_render_manifest` | 固定 1080p Profile 与离线真实校准通过 |
| G8-B | 尚未实施 | 冻结 Manifest Run 能力与离线测试通过，产生 `pass_for_g8_frame_evidence_pack` |
| G8-C | 尚未实施 | 逐镜帧证据包能力与合成校准通过，产生 `pass_for_single_g8_render` |

任一前置状态为空、失败、证据引用不可读或与当前资产不一致时，终态为 `blocked_precondition`，不创建
Manifest-bound Run。

## 3. 先填请求模板，不手写服务端事实

复制[空白 Render Manifest 模板](paynes-creek-g8-render-manifest-template.json)到独立 attempt 目录，并只填写：

- 每镜真实 `image_id`、`audio_id`、`subtitle_id`；
- 对应不可覆盖的图片审核记录与语言审核记录引用、文件 SHA-256；
- 明确的认证用户确认。

下列字段不由人填写：

- Asset ID、source Run ID、SHA-256、宽高、时长和 cue 数；
- 视频模板、codec、fps、crop 和文件路径；
- “latest”“current”或文件名推断。

先调用只读 preview，由服务端返回 canonical snapshot 和 Manifest SHA-256；人工核对后把该 hash 原样写入
Run Create confirmation。Run 创建时服务端重新编译，hash 不一致必须停止并重新 preview。客户端模板中的
`null` 不能被解释为“使用默认值”，preview 也不能创建 Run 或队列消息。

## 4. 成片顺序固定

G6 和 G7 按风险安排生产顺序，G8 必须恢复最终叙事顺序：

| 成片序号 | Scene | Motion | 图片审核来源 | 语音 / 字幕审核来源 |
| ---: | --- | --- | --- | --- |
| 1 | S01 | `zoom_in` | G5-A attempt | G7-01 attempt |
| 2 | S02 | `static` | G6-01 attempt | G7-02 attempt |
| 3 | S03 | `pan_right` | G4 attempt | G7-04 attempt |
| 4 | S04 | `zoom_in` | G5-B attempt | G7-10 attempt |
| 5 | S05 | `pan_down` | G6-04 attempt | G7-11 attempt |
| 6 | S06 | `zoom_out` | G6-07 attempt | G7-12 attempt |
| 7 | S07 | `static` | G6-06 attempt | G7-05 attempt |
| 8 | S08 | `zoom_out` | G6-02 attempt | G7-03 attempt |
| 9 | S09 | `pan_right` | G6-05 attempt | G7-06 attempt |
| 10 | S10 | `static` | G6-08 attempt | G7-07 attempt |
| 11 | S11 | `pan_down` | G6-03 attempt | G7-08 attempt |
| 12 | S12 | `zoom_out` | G6-09 attempt | G7-09 attempt |

这张表来自锁定生产草案。不得按 attempt 编号、Run 创建时间、Asset 创建时间或文件目录顺序合成。

## 5. 冻结前人工检查

认证用户确认前逐项检查：

- 12 个 Scene key 恰好为 S01–S12，无重复、缺失或额外项；
- 顺序与上表一致；
- 每张图片的审核记录终态为对应 Gate 的 `pass_for_*`，且 ID / hash 与记录一致；
- 每条 Audio / Subtitle 的 G7 记录为 `pass_for_*`，字幕属于对应音频；
- S03、S07、S09、S10 的语言审核记录明确保留限定词；
- Motion 与表中值完全一致；
- `output_preset=youtube_16_9_1080p`；
- `bgm_asset_id=null`；
- purpose 仍是 `local_production_validation`，`publication_authorized=false`；
- 本轮只改“从已锁定纸面包进入真实媒体”这个变量，不同时改脚本、画风、语速或镜头顺序。
- preview 返回的 canonical Scene、lineage、Asset hash、时长与审核 ref / hash 均已逐项核对。

确认不代表成片通过，只代表“允许用这组确定输入运行一次本地渲染”。

## 6. G8-B Run 创建

创建请求必须同时满足：

```text
Skill = youtube-frozen-render 的当前发布版本
Tools = [render_story_video]
render_manifest = 已填完整的 v1 请求
render_manifest_confirmation.confirmed = true
render_manifest_confirmation.expected_manifest_sha256 = preview 返回值
style / creation channel / publish context = null
```

API 返回后记录：

- Run ID；
- Skill Version ID / content hash；
- model route / provider / API shape / model snapshot；
- canonical Render Manifest JSON；
- Manifest SHA-256；
- authenticated confirmer 与 server confirmation time；
- enqueue / Run 状态。

若 API 拒绝，记录安全错误和 `video_render_processes=0`，不要通过普通 Run 绕过冻结入口。

## 7. 单次执行预算

| 副作用 | 本 Gate 上限 |
| --- | ---: |
| 模型调用 | 仅允许完成“调用零参数 Tool + 报告结果”所需的有界调用；记录真实次数 |
| 图片 Provider | 0 |
| VL Provider | 0 |
| Speech Provider | 0 |
| Subtitle process | 0 |
| Remotion video process | 1 |
| YouTube publish call | 0 |

Tool 不接受参数。模型若试图传入 scenes、BGM、preset 或任意字段，Schema 必须拒绝且 Remotion 为 0 次。
同一 Manifest-bound Run 即使换 `tool_call_id` 也只能准备一次 Render。失败后不自动重试；由人判断是否
保留同一 Manifest 处理运行故障，或因输入修订建立新 Manifest。

## 8. 自动证据

渲染成功后，从数据库和真实文件记录：

- Run / Step / Tool Call / Video / FileAsset ID；
- Manifest key / SHA-256；
- 12 组 Scene 的 image / audio / subtitle source Run 与 Asset lineage；
- 每组输入文件实际 SHA-256 与快照一致；
- output preset、template ID 与 Remotion renderer version；
- 1920×1080、30fps、H.264、yuv420p、AAC、视频 / 音频各一个流；
- duration frames、真实 duration 与一帧容差结果；
- MP4 byte size 与 SHA-256；
- 模型、图片、VL、语音、字幕、视频和发布的真实 call counts。

任一技术字段失败时，不产生 Video / FileAsset；G8 终止于 `failed_during_render` 或
`invalid_manifest_evidence`。

## 9. G8-C 抽帧交接

ffprobe 不证明视觉质量。Sprint 190 / G8-C 已把后续步骤固定为独立 Evidence Pack 作业：

- Render Tool 成功只写 `rendered_awaiting_frame_evidence`，先保留唯一 MP4；
- 每镜按真实帧区间抽取 `expected_dark_start / safe_start / midpoint / safe_end / expected_dark_end` 五个角色；
- S03、S07、S09、S10 通过 Subtitle cue 的逐字片段自动定位限定词帧，不接受人猜时间戳；
- endpoint PNG、像素统计与 `blackdetect` 共同形成观察，模板自己的 8 帧 fade 不被误判为故障；
- 完整 decode、PNG、canonical manifest 与无公网依赖的离线 HTML 打包成一个 owner-only ZIP；
- Pack 失败保留 Video，不自动重渲染；Pack 成功才进入 `ready_for_full_watch_review`。

详细操作见 [G8-C 逐镜帧证据协议](paynes-creek-g8-frame-evidence-protocol.md)和
[空白 Evidence request](paynes-creek-g8-frame-evidence-request-template.json)。

## 10. 人工完整观看

审核人必须从头到尾播放同一个 MP4，并填写：

1. 12 镜是否按叙事顺序出现；
2. 画面是否有拉伸、黑边、意外裁切、跳帧、空白或明显分辨率问题；
3. Motion 是否裁掉唯一证据对象；
4. 字幕是否可读、同步且不遮挡关键物件；
5. 语音是否完整、音量一致，专名和数字可懂；
6. S03 / S07 / S09 / S10 的限定词是否在声音和字幕中同时保留；
7. 片头是否立即建立“海岸盐如何到内陆”的问题；
8. 片尾是否明确“机制可重建、单船旅程未知”的边界；
9. 文件是否能从头播到尾且音画不中断；
10. 是否存在必须新建 Manifest / 新 Run 修正的问题。

完整观看只能由真实人签字；模型摘要、自动字幕检查或 ffprobe 不能代替。

## 11. 终态

| 状态 | 条件 | 下一动作 |
| --- | --- | --- |
| `not_run` | Manifest 模板尚未填满 | 等待上游媒体，不创建 Run |
| `blocked_precondition` | 任一前置 Gate、审核人或成本授权缺失 | 补齐缺口，保持 0 次渲染 |
| `invalid_manifest_evidence` | ID / hash / lineage / review ref 不一致 | 当前 Manifest 作废，重新编译 |
| `failed_during_render` | Tool / Remotion / ffprobe 失败 | 保留失败 Step；人工评审下一 Run |
| `rendered_awaiting_frame_evidence` | 技术渲染通过，Evidence Pack 尚未完成 | 对同一 Video hash 创建 G8-C Pack |
| `frame_evidence_failed` | Pack 失败或取消 | 保留视频；人工评审是否新建 Pack |
| `ready_for_full_watch_review` | 同一 Video hash 的自动证据包通过 | 只开放人工完整观看 |
| `needs_revision` | 人工观看任一项失败 | 保留原视频；新 manifest key / 新 Run |
| `pass_local_pilot` | 总 acceptance 四维和完整观看全部通过 | 可评审下一实验；G9 仍关闭 |

## 12. 当前控制器决策

- `input_used`：12 镜生产草案、G4–G7 attempt 结构、Sprint 187 lineage、Sprint 188 1080p Profile、总验收
  模板与当前 Render Tool。
- `artifact`：本协议、空白 Manifest / G8 attempt、Sprint 189 合同，以及 Sprint 190 的 Evidence Pack
  协议、请求模板和架构蓝图。
- `decision`：允许预先固定 G8 业务顺序与审计字段；禁止当前填写真实 ID、确认 Manifest、运行 Remotion
  或把技术成功写成样片通过。
- `next_step`：完整观看与 G9 入口已由
  [G8 不可变人工验收协议](paynes-creek-g8-human-acceptance-protocol.md)和 Sprint 191 固定；当前实际开发仍
  G3 已独立通过；等待 G4–G7 前序媒体 Gate 与 G8-A / G8-B / G8-C 实施完成。

本轮完成：把 12 组媒体从人工审核结果到一次确定性本地渲染的操作步骤和停止条件锁定。

下一步建议：评审 G8 不可变人工验收；研究侧继续设计 G9-A 包装与发布授权快照，不调用媒体。

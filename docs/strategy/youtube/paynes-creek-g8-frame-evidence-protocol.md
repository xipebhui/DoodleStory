# Paynes Creek G8-C 逐镜帧证据包与完整观看交接协议

更新时间：2026-08-12
状态：协议已设计；G8-C 未实施，真实 Video、cue、Pack 和 Archive 均不存在
用途：把一次已保存的 G8 MP4 转成可复核证据，不是成片通过或发布授权

## 1. 一句话结论

真实 G8 Render 成功后先保留唯一 MP4，再对同一个 Video SHA-256 创建一份固定 Profile 的 Evidence Pack。
系统按真实 Scene 帧区间抽取每镜五个角色帧，并自动定位四组限定词所处 cue；证据包成功后才开放人工从头
到尾观看，任何自动指标都不能代替审核人签字。

## 2. 前置 Gate

| Gate | 必须状态 | 证明什么 |
| --- | --- | --- |
| G0–G7 | 既有要求全部通过 | 来源、图片、语音、字幕与跨 Run lineage 已审核 |
| G8-A | `pass_for_g8_render_manifest` | 固定 1080p Profile 与真实文件 probe 能力通过 |
| G8-B | `pass_for_g8_frame_evidence_pack` | 冻结 Manifest Run 能力通过，且单 Run 只能渲染一次 |
| G8-C | `pass_for_single_g8_render` | Evidence Pack 的合成校准、权限、恢复与 Archive 通过 |
| G8 Render | `rendered_awaiting_frame_evidence` | 唯一 Manifest-bound MP4 已保存，但尚不能验收 |

任一前置缺失时，不创建 Evidence Pack。G8-B / G8-C 的离线通过不授权真实渲染，真实 G8 仍需单独成本与
运行确认。

## 3. 先复制空白请求模板

复制[空白 G8-C 请求模板](paynes-creek-g8-frame-evidence-request-template.json)到独立 attempt 目录。只有真实
G8 Video 已保存后才填写：

- `video_id`；
- Video FileAsset 的真实 SHA-256；
- 同一 Run 的 Render Manifest SHA-256；
- caller-stable idempotency key；
- 如果重试证据作业，填写旧的终态 `previous_pack_id`。

该 JSON 是完整 attempt 记录，不是可原样发送的 HTTP body：`video_id` 用于组成
`POST /agent-loop/videos/{video_id}/evidence-packs` 路径，实际 body 只提交 `schema_version`、`profile_id`、
两个 expected hash、idempotency key、`previous_pack_id` 与四组 qualifier。

不填写或猜测：

- 绝对帧号、时间戳、Scene duration、fade 区间；
- ffmpeg filter、路径、尺寸或压缩参数；
- cue index、cue 时间或“差不多出现限定词的位置”；
- Pack ID、Archive hash、像素指标或通过结论。

四组 `required_exact_fragments` 已来自锁定旁白，不在 G8 attempt 内改文案。

## 4. 四组限定词

| Group | Scene | 必须逐字定位的片段 | 为什么单独留帧 |
| --- | --- | --- | --- |
| `S03-reconstruction-and-possibility` | S03 | `依据遗迹和类比做的重建`、`可能` | 防止重建画面被说成直接事实 |
| `S07-possibility-not-currency` | S07 | `可能`、`不等于玛雅人已经把盐当成通用货币` | 防止盐饼推断变成货币定论 |
| `S09-no-manifest-unknown-load` | S09 | `没有留下某一条船的货单`、`不知道它装了多少盐` | 保留单船装载量未知 |
| `S10-route-city-buyer-unknown` | S10 | `具体路线、城市和买家仍然未知` | 保留交换网络的证据断点 |

服务端必须在该 Scene 对应 Subtitle cues 的拼接文本中逐字且唯一命中，再自动选择所有相交 cue 的中间可见
帧。若一个片段跨两个 cue，就保留两个物理帧；不得只截其中一个后声称限定词完整。

## 5. 每镜固定五帧

Paynes Creek 12 镜各保留：

| role | 位置 | 人工看什么 |
| --- | --- | --- |
| `expected_dark_start` | 本地帧 0 | 这是模板淡入黑场，不误报为空白故障 |
| `safe_start` | 本地帧 8 | Motion 起点、对象和字幕安全区 |
| `midpoint` | Scene 中点 | 主要画面、字幕和叙事顺序 |
| `safe_end` | 倒数第 9 帧 | Motion 终点有没有裁掉唯一证据对象 |
| `expected_dark_end` | 末帧 | 这是模板淡出黑场，不误报为异常 |

固定角色总数为 60。四组限定词最多再解析 20 个 cue 目标；同一物理帧重复承担角色时只保存一张 PNG，但
所有角色都必须出现在 Manifest。

## 6. 创建与运行

调用 owner-scoped API 后记录：

```text
Evidence Pack ID
Video ID / Asset ID / Video SHA-256
Render Manifest SHA-256
profile_id = narrated_panel_review_v1
request SHA-256 / sampling plan SHA-256
queued time / started time / finished time
ffmpeg / ffprobe version
status / safe error
```

本 Gate 的副作用预算：

| 项目 | 上限 |
| --- | ---: |
| Agent 模型 | 0 |
| 图片 / VL / Speech Provider | 0 |
| Whisper | 0 |
| Remotion | 0 |
| ffprobe | 固定资格复验所需次数 |
| ffmpeg | 完整 decode 1 次、frame select 1 次、blackdetect 1 次 |
| YouTube publish | 0 |

Evidence Worker 不允许重新渲染、重新生成语音、修改字幕或自动 retry。

## 7. 成功 Archive 必须包含

```text
manifest.json
index.html
frames/*.png
```

核对：

- Archive Asset purpose 为 `generated_video_evidence`；
- source Video / Asset / Manifest hash 与 G8 attempt 完全一致；
- 12 个 Scene 帧区间连续，总和等于真实 Video frame count；
- 60 个固定角色全部出现；
- 四个 qualifier group 全部命中，选中 cue 数在 4–20 范围；
- 每个 PNG 都为 1920×1080、非空、有独立 SHA-256；
- endpoint、safe frame、midpoint 和 qualifier roles 到物理文件的映射完整；
- 完整音视频 decode 成功；blackdetect 与像素数据只标为 observation；
- 离线 HTML 无公网依赖、无绝对路径，解压后可直接浏览原尺寸帧；
- ZIP 不含原 MP4、音频、字幕文件、审核文件或凭据。

Archive 或 Manifest 任一不完整时，Pack 不能标 `succeeded`。

## 8. 自动观察不等于结论

以下可以由系统记录：

- expected dark endpoint 是否接近黑；
- safe / midpoint frame 是否也接近黑或低方差；
- blackdetect 是否发现预期 fade window 之外的区间；
- PNG 是否缺失、损坏或尺寸错误；
- cue 指定帧是否在字幕可见区间。

以下只能由人判断：

- 深色 safe frame 是正常夜景还是意外空白；
- Motion 是否裁掉考古对象；
- 字幕是否真正可读、遮挡关键物件或节奏过快；
- Scene 之间的黑场是否过长或造成明显跳变；
- 限定词是否在声音和字幕中都能理解；
- 全片是否值得进入本地样片通过状态。

## 9. 人工完整观看顺序

Evidence Pack 成功后，审核人必须：

1. 先核对 HTML 顶部的 Video SHA-256 与 G8 attempt；
2. 按 S01–S12 查看每镜五帧和四组 qualifier 帧；
3. 打开同一个 MP4，从第一帧连续播放到最后一帧，不拖动跳看代替完整观看；
4. 核对 12 镜顺序、拉伸 / 黑边 / 裁切 / 空白 / 跳帧；
5. 核对 Motion 起终点与唯一证据对象；
6. 核对字幕可读、同步、安全区和四组限定词；
7. 核对语音完整、音量、专名、数字和限定词；
8. 核对片头问题与片尾证据边界；
9. 再次确认完整播放无解码、音画中断；
10. 在 G8 attempt 填写审核人、时间、Video hash、Evidence Manifest hash、问题和 verdict。

不能用离线 HTML 浏览代替播放 MP4，也不能只播放有问题的片段。

## 10. 终态

| 状态 | 条件 | 下一动作 |
| --- | --- | --- |
| `rendered_awaiting_frame_evidence` | Video 已保存，尚未创建 Pack | 填写固定请求 |
| `frame_evidence_running` | Pack queued / running | 等待真实终态，不观看签字 |
| `frame_evidence_failed` | Pack failed / cancelled | 保留 Video；人工决定是否新建 Pack |
| `ready_for_full_watch_review` | 同一 hash 的 Pack succeeded 且四组证据齐全 | 开放人工完整观看 |
| `needs_revision` | 人工观看任一项失败 | 保留 Video / Pack；新 Manifest / Run 修订 |
| `pass_for_local_pilot_acceptance` | 完整观看全部通过 | 进入总 acceptance 四维汇总 |

证据重试只创建新 Pack，不需要重渲染同一个有效视频；成片内容需要修改时必须新 Manifest key、新 Run、
新 Video 和新 Evidence Pack，不能把旧 Pack 绑定到新视频。

## 11. 当前控制器决策

- `input_used`：固定 12 镜与旁白、G7 字幕边界、Sprint 188 / 189、当前 Remotion 8 帧 fade、G8 attempt。
- `artifact`：本协议、空白 Evidence request、Sprint 190 合同与架构蓝图。
- `decision`：允许固定证据抽取协议；禁止当前填写 Video / cue / Pack 事实，禁止把自动观察写成人工通过。
- `next_step`：完整观看通过后的 exact-hash 签署已由
  [G8 人工验收协议](paynes-creek-g8-human-acceptance-protocol.md)与 Sprint 191 承接；真实开发仍先等待
  Sprint 181。

本轮完成：把同一个 G8 MP4 从“已渲染”推进到“可以人工完整观看”的证据链固定下来。

下一步建议：评审 G8 不可变人工验收；研究侧继续设计 G9-A 标题、封面与发布包，不调用媒体。

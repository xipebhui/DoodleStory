# Paynes Creek G8 人工完整观看与不可变验收协议

更新时间：2026-08-13<br>
状态：协议已设计；真实 Video、Evidence Pack、审核人和 Acceptance 均不存在<br>
用途：把同一支 G8 本地母版形成最终人工决定，不是公开发布授权

## 1. 一句话结论

只有当同一个 Video SHA-256 的 Evidence Pack 成功后，认证 owner 才能从头播放该 MP4、核对四个固定维度，
通过无写入 preview 看清将被签署的 canonical snapshot，再提交一条不可修改的
`pass_local_pilot | needs_revision`。通过后只开放发布资料准备，不创建 PublishTask。

## 2. 前置事实

| 事实 | 必须状态 |
| --- | --- |
| G0–G7 | 所有既有来源、视觉、语音、字幕 Gate 通过 |
| G8-A | `pass_for_g8_render_manifest` |
| G8-B | `pass_for_g8_frame_evidence_pack` |
| G8-C | `pass_for_single_g8_render` |
| G8 Render | `rendered_awaiting_frame_evidence` 后产生唯一 Video |
| Evidence Pack | 同一 Video hash 的 `succeeded` Pack |
| 人工验收入口 | `ready_for_full_watch_review` |

任何字段仍为 `null / not_run / not_reviewed` 时，不复制本协议中的示例值冒充已完成。

## 3. 先复制空白请求

复制[空白人工验收请求](paynes-creek-g8-human-acceptance-request-template.json)到当前 G8 attempt 目录。该 JSON
是完整审计记录，不是可原样发送的 HTTP body：`evidence_pack_id` 用来组成 API path，`preflight / preview /
submission_result / audit` 只在操作记录中保存。

真实填写前必须能同时读取：

- Video ID、Asset ID、FileAsset SHA-256 和实际 bytes SHA-256；
- Render Manifest key / SHA-256；
- Evidence Pack ID、Evidence Manifest SHA-256、Archive Asset ID / SHA-256；
- 离线 `index.html` 和所有必需 PNG；
- 同一个 MP4 的完整播放入口。

不填写 Reviewer 名字、时间或 Acceptance ID；这些最终事实由认证会话和服务器生成。

## 4. 完整观看顺序

审核人按固定顺序：

1. 核对页面显示的 Video ID / SHA-256 与 Evidence Pack manifest 一致；
2. 下载并打开 Evidence Archive，确认 12 镜五角色帧与四组限定词帧齐全；
3. 打开同一个 MP4，从开头连续播放到结尾；浏览 Evidence HTML 不能替代播放；
4. 按 S01 → S12 核对画面、旁白和字幕顺序；
5. 在播放中核对 S03、S07、S09、S10 的限定词确实被听见并读到；
6. 核对所有 Motion、安全区、裁切、黑边、空白、跳帧和字幕遮挡；
7. 核对专名、年代、度量、音量和同步；
8. 播放结束后填写四维 verdict；
9. 调用 acceptance preview，逐项核对 canonical snapshot 和 hash；
10. 最后确认该 hash，提交一次不可变终态。

浏览器播放事件只辅助操作。权威事实是当前认证 owner 明确勾选 `full_watch_attested=true` 并签署 exact hash。

## 5. 四维判定

### 5.1 Visual evidence continuity

必须全部通过：

- 12 镜均为批准的唯一证据对象，没有错镜、重复镜或来源不明画面；
- S03 重建、S07 可能性、S09 无货单、S10 路线未知没有被画成确定事实；
- Motion 起点、中点和终点不裁掉关键对象；
- 无拉伸、未批准裁切、黑边、异常空白、冻结画面或转场外黑帧；
- 字幕安全区没有遮挡视觉锚点。

### 5.2 Script evidence and pacing

必须全部通过：

- 成片顺序严格 S01 → S12；
- 旁白仍与锁定 536 字脚本同义，四组限定词完整；
- 真实总时长 120–150 秒；
- 没有为缩短时长删除证据边界，没有补写货量、路线、买家或货币定论；
- 开头问题清楚，结尾明确区分已知、解释和未知。

### 5.3 Chinese speech and subtitles

必须全部通过：

- “佩恩斯克里克”“伯利兹南部”“公元六百到九百年”“一米四三”可懂；
- 语音无漏句、截断、异常停顿、音量突变或多余声音；
- WebVTT 字幕与语音同步、可读、最多两行且不出安全区；
- S03 / S07 / S09 / S10 限定词在语音和字幕中都存在；
- 无未批准 BGM、音乐、音效或声音素材。

### 5.4 Render delivery and traceability

必须全部通过：

- 同一个 MP4 从第一帧播放到最后一帧，无解码或音画中断；
- 文件仍为 H.264 / yuv420p、AAC、1920×1080、30fps、120–150 秒；
- Video、Manifest、Pack、Evidence Manifest、Archive 和 Acceptance preview hash 均可回查；
- Pack 的 endpoint 黑帧符合模板淡入淡出，不把预期黑场误判为错误；
- 没有任何自动指标被写成人工通过结论。

## 6. Verdict 规则

### `pass_local_pilot`

只在以下全部成立时选择：

```text
四维 verdict = pass
full_watch_attested = true
revision_summary = null
四个 expected hash 与服务器重算完全一致
```

### `needs_revision`

只在以下成立时选择：

```text
至少一维 verdict = fail
revision_summary 非空并指出首个可复现失败点
```

失败问题按维度记录，不把“感觉不太好”作为唯一说明。已有视频不能原地重新审批；后续必须新 Manifest、
新 Run、新 Video、新 Pack 和新 Acceptance。

## 7. Preview 与最终提交

1. 先调用：

   ```text
   POST /agent-loop/video-evidence-packs/{pack_id}/acceptance-preview
   ```

2. 核对返回：

   ```text
   video_id / video_sha256
   render_manifest_sha256
   evidence_pack_id / evidence_manifest_sha256 / evidence_archive_sha256
   four dimension verdicts
   decided_by_user_id
   publication_authorized = false
   acceptance_snapshot_sha256
   ```

3. 把 exact `acceptance_snapshot_sha256` 放入最终请求，再调用：

   ```text
   POST /agent-loop/video-evidence-packs/{pack_id}/acceptance
   ```

4. 任何 409 都表示当前 preview 已失效或事实不一致；重新读取，不猜测、不改 hash、不走旧登记接口。

5. 成功后保存 Acceptance ID、status、snapshot hash、服务器审核人和时间。记录从此不可编辑。

## 8. 通过后只允许严格登记

`pass_local_pilot` 后可以准备标题、描述、标签和可选封面，但 Manifest-bound 视频只能调用：

```text
POST /youtube/publishable-videos/from-local-pilot-acceptance
```

请求从 Acceptance 推导源 Video，不再发送：

```text
source_native_agent_video_id
review_status = approved
contains_synthetic_media
```

服务端固定 `approved / synthetic=true` 并保存 Acceptance / Video / Manifest / Evidence hash。旧
`POST /youtube/publishable-videos` 对此视频必须拒绝，不能作为兼容入口或失败 fallback。

严格登记成功仍不表示可以发布。以下仍为空：

- 目标频道最终确认；
- YouTube 语言与地区；
- 发布前 `prediction.json`；
- 本轮只改变的一个主要变量；
- 封面 Asset / SHA-256 / 权利审核；
- 标题与描述的发布审核；
- 可见性、计划时间、通知订阅者；
- 发布责任人、撤回责任与数据回流检查点。

## 9. 操作终态

| 状态 | 含义 | 唯一下一动作 |
| --- | --- | --- |
| `ready_for_full_watch_review` | Pack 成功，尚未签署 | 完整观看并 preview |
| `needs_revision` | 人工至少一维失败 | 新 Manifest / Run / Video，不登记 |
| `pass_local_pilot` | exact 母版四维通过 | 评审 G9 发布资料包 |
| `publishable_registered` | 已绑定通过母版和元数据 | 仍等待目标频道与真实发布确认 |

不存在 `review_again`、`edit_acceptance`、`force_approve` 或“先登记后补审核”。

## 10. 当前控制器决策

- `input_used`：本地样片四维章程、G8 Render attempt、G8-C Evidence 协议、Sprint 134 / 135 当前登记与发布
  行为、Sprint 191 蓝图。
- `artifact`：本协议和空白人工验收请求模板。
- `decision`：允许固定 owner 对 exact Video / Evidence hash 的不可变四维终态；禁止当前填写真实结果，禁止
  未通过母版进入 PublishableVideo，禁止通过后自动发布。
- `next_step`：设计 G9-A 发布包，仍不调用媒体或 YouTube。

本轮完成：把 Paynes Creek G8 从“可以观看”推进到“可审计地通过或退回”的人工操作协议固定下来。

下一步建议：固定 G9-A 的频道、预测、单一变量、标题、封面权利、披露与发布确认快照。

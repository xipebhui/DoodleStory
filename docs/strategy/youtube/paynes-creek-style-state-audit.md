# Paynes Creek 16:9 Style 状态审计

审计日期：2026-08-12<br>
状态：`local_record_active / media_observed_but_rejected / no_channel_binding`<br>
审计方式：仓库本地验证库只读查询 + 当前 Style / Agent / 图片代码静态核对

## 结论

`Paynes Creek Evidence Desk 16:9` 已经存在于当前仓库配置的本地验证库，不应重复创建。它是一条
`active` 的 Prompt 模式配置记录，但从未执行 Style Test，也没有完成过图片调用、图片资产验证或 YouTube
频道绑定。因此，准确表述是“Style 配置已建立，视觉输出未验证”，不能写成“Style 待建立”，也不能写成
“Style 已通过”。

## 四层状态

| 层级 | 当前事实 | 可以说明 | 不能说明 |
| --- | --- | --- | --- |
| Style 记录 | `style_record_created=true` | 本地存在唯一可引用记录 | 其他环境也有同一记录 |
| 配置状态 | `config_active=true` | 名称、Prompt、模型和比例满足当前启用条件 | Prompt 会稳定生成合格画面 |
| 媒体验证 | `media_output_verified=false` | Attempt 02 已观察到真实输出，但因现代器件、文字与安全区失败被拒绝 | Provider、构图、安全区或风格一致性已通过 |
| 频道关系 | `youtube_channel_binding_count=0` | 当前没有生产频道绑定 | 频道已选定或允许发布 |

## 只读事实快照

| 字段 | 观测值 |
| --- | --- |
| 本地 Style ID | `4443d2412c994ec298b635e6c63806e7` |
| 名称 | `Paynes Creek Evidence Desk 16:9` |
| 状态 | `active` |
| 图片模型 | `Qwen/Qwen-Image` |
| 画幅 | `16:9` |
| 参考模式 | `prompt` |
| 参考图数量 | 0 |
| Style Prompt 字符数 | 883 |
| Style Prompt SHA-256 | `5b8b5a7d144b13d6cdecc2ba2949205090df0958d8563b69968e8940a23b0d1b` |
| `last_tested_at` | `null` |
| Style Test 数量 | 0 |
| 生成任务数量 | 0 |
| 关联 Native Agent Run 数量 | 1 |
| 关联 Native Agent 图片数量 | 0 |
| YouTube 频道绑定数量 | 0 |

本地 ID 只用于本次审计和历史 lineage。文档不记录数据库绝对路径、连接串或任何凭据。

## `active` 的实际语义

当前 Style API 的激活条件只要求 Style Prompt 非空；Prompt 模式允许零参考图。模型名会做首尾空白规范化，
Style 画幅允许 `16:9`，而 `Qwen/Qwen-Image` 是当前图片 Gateway 认识的模型。由此只能得出这条配置可以
被选入 Run 快照，不能得出以下结论：

- 图片 Provider 已收到过请求；
- 16:9 请求一定返回目标尺寸；
- 画面满足中央 84%、上方 70%、底部 30% 字幕安全区；
- 重建 / 直接证据的颜色语义或无文字要求已被模型遵守；
- 图片已经通过 `inspect_image` 或人工事实 / 视觉审核。

保存的 883 字符 Prompt 与当前共享视觉语言在模型、画幅、色板、证据 / 重建表达、安全区和禁止项上相符。
这种文本一致性只是配置审查，不替代一次真实 S03 媒体 Gate。

## 历史 Run 能证明什么

本地唯一关联 Run `de8b148d122343fd984a9d646801c12b` 保存了该 Style 的名称、模型和 `16:9` 快照，
关联的最小 Skill 只开放 `generate_image` 与 `inspect_image`。Run 在首轮 Agent 文本规划时因
`gpt-5.5` 返回 429 `usage_limit_reached` 而失败：模型调用 1，图片、语音、字幕和视频调用均为 0。

因此，Run 只能证明“Style 被写入过执行快照”，不能证明图片 Tool、`Qwen/Qwen-Image` 或视觉验收工作正常。
完整历史证据见 [S03 单镜真实媒体 Gate 记录](paynes-creek-s03-media-gate.md)。

## 未来 G4 的重新解析规则

本次审计不是 G4 通行证。获得独立媒体授权后，preflight 必须从当时数据库重新读取：

1. Style ID 与未删除状态；
2. `active` 状态；
3. 图片模型严格等于 `Qwen/Qwen-Image`；
4. 画幅严格等于 `16:9`；
5. Prompt SHA-256 严格等于本次锁定值；
6. 参考图数量仍为 0。

任一字段变化，都结束当前 preflight，记录 `blocked_precondition`，在新的 attempt 中评审差异。禁止自动重建
Style、切换模型 / Provider、补参考图或把历史本地 ID 直接写入空白 Gate 模板。

## 控制器决策

- `input_used`：当前本地 Style / Test / Task / Run / Image / Channel Binding 只读事实，Style API 与图片
  Gateway 代码，S03 历史 Gate。
- `artifact`：本状态审计、生产草案 v2 与相关生产入口的状态同步。
- `decision`：保留现有 Style；Attempt 02 证明 Provider 可出图，但当前 Prompt 输出质量不通过。
- `next_step`：另建 G4 Attempt 03 的 Prompt 修订评审；不重复创建 Style、不换模型或 Provider。

本轮完成：把 Style 记录、启用、媒体验证和频道绑定四种状态拆开，并固定未来重新解析规则。<br>
下一步建议：先把 Attempt 02 的硬失败固化，再以正向对象白名单冻结 Attempt 03；仍只生成一张 S03。

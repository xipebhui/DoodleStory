# Paynes Creek 首片生产控制室

更新时间：2026-08-13<br>
状态：`lane_selected / g2_pass_offline / g3_pass / stop_before_g4 / no_media / no_publish_authorization`<br>
用途：首片生产验证的权威运行手册；不是 YouTube 市场实验，也不是已完成视频

本地可视化入口：[HTML 生产控制台](paynes-creek-production-control-room.html)

## 一句话决策

可以进入实际视频制作验证。首个赛道固定为：

> **考古证据驱动的古代技术与日常生活机制解释**

第一条固定为：

> **公元 600–900 年，伯利兹南部 Paynes Creek 的玛雅海岸盐工，如何把卤水变成可运往内陆的盐。**

这项决策证明的是“它适合用 DoodleStory 当前的静态插画、中文旁白、字幕和 Remotion 链路做首片”，
不是“该赛道已经被市场验证”。当前没有真实发布、频道基线或数据回流，不能声称它会获得播放、涨粉、
获利或形成稳定频道。

## 为什么先做这个赛道

| 判断维度 | 当前证据 | 结论 |
| --- | --- | --- |
| 产品适配 | 一镜一图、原创旁白、字幕和有限平移 / 缩放可以表达机制链 | 高适配 |
| 事实可审计 | 已有来源账本、主张编号和“直接证据 / 解释 / 未知项”边界 | 已具备首片研究基础 |
| 视觉可生产 | 地图、盐水、陶器、木构、船桨和网络可用原创解释图表达 | 有条件可做 |
| 版权控制 | 默认不使用许可不清的现场照片，优先原创图和可商用开放来源 | 已有明确边界 |
| 差异化方向 | 不复制通用 `Ancient Humans` 问句，使用地点、时期、机制物件和来源审计 | 形成可辨认结构 |
| 市场证据 | 公开样本存在需求信号，但多个频道依赖异常单条，且本项目尚无发布数据 | 未验证 |

赛道模板固定为：

```text
一个日常限制
→ 一个具体历史地点与时期
→ 一条可见的机制链
→ 每个主张对应来源
→ 明说重建、可能与未知项
```

## 首片制作护照

| 字段 | 已锁定值 | 证据状态 |
| --- | --- | --- |
| 题目 | Paynes Creek 盐生产—运输解释链 | 已锁定 |
| 用途 | 中文本地生产验证 | 已锁定，不代表市场实验 |
| 画幅 | 16:9 普通视频 | 已锁定 |
| 镜头 | S01–S12，共 12 镜 | 已锁定 |
| 计划时长 | 138 秒 | 计划值 |
| 旁白 | 536 个汉字，`zh-CN`，`speed=1.0` | 文本已定；真实时长未测 |
| 图片模型 | `Qwen/Qwen-Image` | 本地 Prompt Style 为 `active`；Style Test 0、图片 0，输出未验证 |
| 图片请求目标 | 当前 Gateway 对 16:9 请求 1792×1024 | 代码事实；Provider 实际返回未验证 |
| 交付目标 | 1920×1080，30 fps | 目标；当前 Remotion 不自动标准化 |
| BGM | 无 | 已锁定 |
| 发布 | 禁止 | 未指定频道、责任人和发布确认 |

## 十二镜接触印样

| 镜头 | 秒 | 唯一主张 | 证据 | 当前资产状态 |
| --- | ---: | --- | --- | --- |
| S01 | 8 | 海岸的盐如何到达内陆 | 解释 | 旁白 + Prompt 已就绪，图片禁止 |
| S02 | 10 | 地点与公元 600–900 年时间边界 | 直接 | 旁白 + Prompt 已就绪，图片禁止 |
| S03 | 11 | 依据遗迹与类比重建卤水浓缩 | 直接 + 重建 | **当前媒体 Gate；图片 0** |
| S04 | 12 | 陶器与黏土支座支持加热结晶 | 直接 + 解释 | 旁白 + Prompt 已就绪，图片禁止 |
| S05 | 13 | 盐厨房与居住空间相邻 | 直接 + 解释 | 旁白 + Prompt 已就绪，图片禁止 |
| S06 | 14 | 专门作业空间支持超出日常自用的生产 | 解释 | 旁白 + Prompt 已就绪，图片禁止 |
| S07 | 11 | 盐可能被做成便于搬运的盐饼 | 重建 | 旁白必须保留“可能 / 非通用货币” |
| S08 | 11 | 船桨证明当地具备水路移动能力 | 直接 | 旁白 + Prompt 已就绪，图片禁止 |
| S09 | 12 | 物质联系支持水路运输解释 | 解释 | 旁白必须保留“没有逐船货单” |
| S10 | 11 | 海岸到未命名内陆节点的方向网络 | 解释 | 禁止具体路线、城市、买家与价格 |
| S11 | 12 | 遗址后来被淹没，泥炭保存木柱与布局 | 直接 | 禁止把古人画成在水下煮盐 |
| S12 | 13 | 以已知、可解释和未知收束 | 证据边界 | 旁白 + Prompt 已就绪，图片禁止 |

完整逐镜事实、构图和运动规格见[逐镜证据板](paynes-creek-shot-evidence-board.md)，完整旁白与图片指令见
[中文旁白与 Prompt 包](paynes-creek-chinese-script-prompt-pack.md)，机器可读 Scene 见
[生产草案 JSON](paynes-creek-production-draft.json)。

## 现在的真实状态

```text
来源与事实边界                 PASS
视觉来源与商业使用边界         CONDITIONAL PASS
12 镜与 16:9 规格              PASS
中文旁白与逐镜 Prompt           PASS
本地 Style 配置                 ACTIVE / PROMPT / STYLE TEST 0
本地最小 Skill                  PUBLISHED / RUN SNAPSHOT ONLY
S03 Native Agent 规划           FAILED: gpt-5.5 / 429 usage_limit_reached
S03 图片调用                    0
SiliconFlow Chat 适配设计        COMPLETE / OFFLINE VERIFIED
SiliconFlow Chat 运行时代码      IMPLEMENTED / ADMIN-ONLY S03
G2-A Run 路由快照                COMPLETE / OFFLINE VERIFIED
G2-B Chat 有界适配               COMPLETE / OFFLINE VERIFIED
零媒体真实兼容性 Gate            NOT RUN
G3 零媒体 Attempt 1              STOPPED AT LOCAL DB PREFLIGHT / PROVIDER REQUESTS 0
G3 零媒体 Attempt 2              PASS / 5 REQUESTS / TOOL ONCE / MEDIA 0
G8-A 1080p Profile 设计          READY / NOT IMPLEMENTED
G8-B 冻结 Manifest 设计          READY / NOT IMPLEMENTED
G8-C 逐镜帧证据包设计             READY / NOT IMPLEMENTED
G8 不可变人工验收设计             READY / NOT IMPLEMENTED
S03 图片 / VL / 人工复核         NOT RUN
其余 11 镜、TTS、字幕、视频      BLOCKED
公开发布                        NOT AUTHORIZED
```

唯一一次 S03 Run 在 Agent 第一轮规划阶段失败，`generate_image` 与 `inspect_image` 都没有执行。
因此当前问题不是图片 Prompt 或画风质量，不能通过继续改 Prompt、直接调用更多图片或换 Provider 绕过。
完整事实见 [S03 单镜 Gate 记录](paynes-creek-s03-media-gate.md)。未来重试必须使用
[S03 单镜重试协议](paynes-creek-s03-retry-protocol.md)和
[空白证据模板](paynes-creek-s03-gate-evidence-template.json)另建记录；模板已准备不代表 G4 已开放。

## 本地样片最终验收

Gate 回答“是否允许进入下一步”，最终验收回答“整支本地样片是否真的合格”。本轮只验证一个变量：
把锁定的纸面生产包推进到真实端到端媒体，题目、脚本、画风规则、时长目标和 Provider 策略不在同一
attempt 内变化。

| 验收维度 | 必须留下的真实证据 | 通过门槛 |
| --- | --- | --- |
| 视觉证据连续性 | 12 张 approved 图、真实尺寸、机器检查、事实与视觉人工 verdict | 12/12 对象锚点、证据边界、比例和字幕安全区通过 |
| 脚本、证据与节奏 | 12 镜来源映射、真实音频总长、四处限定词核对 | 120–150 秒且不删除重建 / 可能 / 未知 |
| 中文语音与字幕 | 12 音频、12 WebVTT、专名试听、字幕安全区截图 | 专名可懂、字幕与 TTS 同义、不遮挡唯一证据对象 |
| 渲染与可追溯性 | 视频探针、文件哈希、Run / Step / Tool / Asset lineage、完整观看 | 1920×1080、30 fps、可从头播放到尾且全部证据可回查 |

四项同时通过、owner 完整观看并签署同一 Video / Manifest / Evidence exact hash 后，才允许保存不可变的
`pass_local_pilot`。这个终态只证明当前链路能做出一条合格的本地生产样片，不能证明 YouTube 点击、留存、
频道适配、增长或获利，也不自动开放 G9。完整定义见
[本地样片生产验证章程](paynes-creek-local-pilot-charter.md)，未来 attempt 使用
[空白成片验收模板](paynes-creek-local-pilot-acceptance-template.json)和
[G8 人工验收协议](paynes-creek-g8-human-acceptance-protocol.md)，未观测字段保持
`null / not_run / not_reviewed`。

## 严格生产闸门

每个 Gate 只在上一 Gate 留下可审计的通过证据后开放。失败时停止，不自动换模型、Provider、上下文策略
或工具组合。

| Gate | 状态 | Owner 类型 | 输入 | 通过证据 | 失败动作 |
| --- | --- | --- | --- | --- | --- |
| G0 赛道与事实 | 已通过 | 研究 / 事实审核 | 来源账本、10 条主张、视觉权利矩阵 | 题目、主张和禁区可追溯 | 回研究，不制作 |
| G1 分镜与脚本 | 已通过 | 内容 / 事实审核 | 12 镜、536 字旁白、12 段 Prompt | 138 秒计划、四处不确定性进入原文 | 回脚本，不生图 |
| G2 Native 路由离线适配 | **通过：`pass_offline`** | 开发负责人 | [G2-A 合同](../../contracts/sprint-181-native-agent-run-route-snapshot-foundation.md)；[G2-B 合同](../../contracts/sprint-192-native-agent-siliconflow-chat-bounded-adapter.md) | 路由快照、Chat Adapter、迁移、能力边界和离线测试全部通过 | 开放 G3 授权评审，不开放外部调用 |
| G3 SiliconFlow 零媒体 Gate | **通过：`pass_for_s03_single_image_review`** | 开发 + 成本批准人 | Attempt 2、V3.2、[真实报告](../../testing/siliconflow-native-agent-compatibility-report.json) | 5 次请求内普通流、Tool + 跨进程恢复、10 / 11 消息边界全部通过；媒体 0 | 已开放 G4 单张授权 |
| G4 S03 单镜媒体 Gate | **当前下一步；已获用户授权，尚未执行** | 视觉审核人 + 事实审核人 | 一张 S03、`inspect_image` 文本 verdict、[重试协议](paynes-creek-s03-retry-protocol.md) | 真实尺寸、机制对象、重建表达、安全区、人工复核全通过 | 保留证据并停止，不生成第二镜 |
| G5 视觉锚点检查 | 未开放；[串行协议已准备](paynes-creek-g5-serial-anchor-protocol.md) | 视觉 + 事实审核人 | G5-A 一张 S01；通过并停止后，G5-B 一张 S04 | 地图抽象边界、器物关系、前序图同尺寸和中心缩放探针分别通过 | 返回对应单镜；两个子 Gate 不共用授权，不启动余图 |
| G6 剩余图片 | 未开放；[九镜串行协议已准备](paynes-creek-g6-serial-production-protocol.md) | 制作负责人 | 已批准锚点；S02 → S08 → S11 → S05 → S09 → S07 → S06 → S10 → S12 | 九个子 Gate 分别留下资产、尺寸、来源边界和人工 verdict | 在首个失败镜停止；不自动生成下一镜 |
| G7 语音与字幕 | 未开放；[协议已准备但受 G7-0 阻断](paynes-creek-g7-audio-subtitle-protocol.md) | 语言审核人 + 开发负责人 | G7-0 同会话跨 Run 渲染 lineage；最终 536 字原文 | S01 → S02 → S08 → S03 → S07 → S09 → S10 → S11 → S12 → S04 → S05 → S06 逐镜通过；总长 120–150 秒 | G7-0 未实现不调用 TTS；单镜失败阻断后继镜 |
| G8-A 1080p Profile | 未开放；设计已准备 | 开发负责人 | 版本化 preset、裁切预算、真实 MP4 probe | 离线模板与真实校准通过，产生 `pass_for_g8_render_manifest` | 不生成 Paynes Creek 视频 |
| G8-B 冻结 Manifest Run | 未开放；[协议已准备](paynes-creek-g8-render-manifest-protocol.md) | 制作负责人 + 确认人 | 12 组已审核媒体、review refs、固定顺序 / Motion / preset | Run 级 canonical Manifest、SHA-256、认证确认与零参数 Tool 离线通过，产生 `pass_for_g8_frame_evidence_pack` | 不允许 Prompt 转抄或普通 Run 绕过 |
| G8-C 逐镜帧证据包能力 | 未开放；[协议已准备](paynes-creek-g8-frame-evidence-protocol.md) | 开发负责人 + 质量审核 | 固定采样 Profile、完整 decode、Archive 权限与恢复 | 合成校准、权限、恢复、确定性 ZIP / HTML 通过，产生 `pass_for_single_g8_render` | 不生成 Paynes Creek 视频；不把机器指标当人工 verdict |
| G8 本地成片与不可变验收 | 未开放；[人工验收设计已准备](paynes-creek-g8-human-acceptance-protocol.md) | 制作 + 质量审核 owner | 已确认 Manifest-bound Run、已通过 Evidence Pack 能力与 succeeded Pack | 唯一 MP4 先进入 `rendered_awaiting_frame_evidence`；同一 hash 的 Pack 成功后完整观看，并以 exact hash preview / commit 保存 `pass_local_pilot | needs_revision` | 不直接提交 `review_status=approved`；Pack 或验收失败不重渲染、不登记 |
| G9 发布准备 | 未开放 | 频道 owner + 发布责任人 | `pass_local_pilot` Acceptance、标题、描述、缩略图、披露决定 | 频道、预测、单一变量、语言、封面权利、数据回流和明确发布确认齐全 | 保持本地样片 |

### G2 已离线完成，G3 已真实通过；停在 G4 单镜执行前

G2 的离线 Phase A 拆成两个串行子 Gate，避免同时改持久化事实、Responses 回归和 Chat 事件。
[Sprint 181 / G2-A](../../contracts/sprint-181-native-agent-run-route-snapshot-foundation.md) 已完成：

- 分离 Native 当前火苗模型与旧 Router 的 `AGENT_MODEL`；
- 保存并返回 Run 级 route、provider、API shape 与 model 快照；
- 让普通执行、文章角色、重试、恢复和 Follow-up 全部只读该快照；
- 迁移历史 Run 为当时唯一存在的 `huomiao_responses` 路径，保留原模型值；
- 保持默认 Route 为火苗 Responses，不从旧 Router 模型回退。

[Sprint 192 / G2-B](../../contracts/sprint-192-native-agent-siliconflow-chat-bounded-adapter.md) 也已完成：

- 只有 Admin 可显式选择 `siliconflow_chat_v1`，模型固定为 `deepseek-ai/DeepSeek-V3.2`；
- 只接受 `generate_image + inspect_image`、有效 Style、零创作 / 发布上下文的 S03 Profile；
- 稳定模型调用身份、Provider ID、Chat Tool 参数完成和 10 / 11 消息预检均已离线验证；
- Chat 生图只返回文本 ID，同 Run 只有一次 Provider attempt，必须形成真实检查终态且不能 Follow-up；
- revision `w4x5y6z7a8b9` 的空库、历史升级与降级通过，历史模型 Step 新字段保持 `NULL`。

因此 G2 记录为 `pass_offline`。G3 Attempt 1 在本地 SQLite 前置停止且 Provider 请求为 0；Sprint 194 修复后，
Attempt 2 用恰好 5 次真实请求通过 Z1–Z4，Tool 执行一次，媒体与发布仍为 0。当前只开放 G4 的唯一一张
S03，不开放第二张图片或后继媒体。

## 发布前仍缺的外部输入

以下空位不会阻止本地生产验证，但会阻止市场实验和公开发布：

| 缺口 | 当前值 | 何时必须补齐 |
| --- | --- | --- |
| 目标 YouTube 频道与 owner | 未指定 | G9 前 |
| 原始发布语言与目标地区 | 本地样片为中文；市场值未定 | 建立发布实验前 |
| 事实审核人 | 未指定 | G4 人工复核前 |
| 视觉 / 版权审核人 | 未指定 | G4 与 G9 前 |
| 语言审核人 | 未指定 | G7 前 |
| 发布责任人和撤回责任 | 未指定 | G9 前 |
| 单片成本上限 | 未指定；不得把“免费额度”当作零成本保证 | G3 前 |
| 数据回流权限与 24 / 72 小时检查点 | 未指定 | 创建 `prediction.json` 前 |
| 频道同长度内容基线 | 无 | 市场实验前 |

这些输入补齐前，首片始终标记为 `local_production_validation`，不创建具有市场含义的发布实验。

## 运行中不允许跨越的边界

- S03 没有图片，不评价图片质量，也不批准 S01。
- S03 只有机器 verdict、没有人工复核，不算通过。
- 图片模型返回尺寸与请求目标不同，以真实文件为准；不得伪造 1920×1080。
- S03、S07、S09、S10 的重建 / 可能 / 未知词不能在 TTS 或字幕阶段删掉。
- 当前 G8 只读取本 Run 音频 / 字幕；G7-0 跨 Run lineage 未实现前，不把逐镜语音 Profile 写成可执行状态。
- G8-B 未实现前，不把 12 组媒体 ID 写进 Prompt 让模型自由拼接；Manifest 必须由服务端编译并冻结。
- G8-C 未实现前，不执行真实 G8；Render 成功不能直接写 `ready_for_full_watch_review`，证据失败也不能自动
  重渲染同一 Manifest。
- G8 immutable Acceptance 未实现前，Manifest-bound Video 不得通过旧登记表单直接提交
  `review_status="approved"`；Pack success、浏览器播放事件和管理员身份都不能单独替代 exact-hash 人工签署。
- 无法确认许可的照片、地图、字体、音乐或音效不进入成片。
- 任何 Provider 失败都停在当前 Gate；不自动换模型、平台或上下文处理方式。
- 本地样片完成不等于可公开发布；发布必须由明确的人确认具体成片和频道。
- 单条发布结果只记录为观察，不更新 `strategy_memory.md` 或内容 Skill。

## 产物导航

| 要回答的问题 | 文件 |
| --- | --- |
| 为什么是 Paynes Creek | [来源账本](ancient-salt-access-source-ledger.md) |
| 哪些图能商业使用 | [视觉来源与授权清单](paynes-creek-visual-source-rights-ledger.md) |
| 每一镜说什么、画什么 | [逐镜证据板](paynes-creek-shot-evidence-board.md) |
| 如何快速浏览 12 镜 | [逐镜 HTML 阅读板](paynes-creek-shot-board.html) |
| 最终旁白和图片 Prompt | [中文旁白与 Prompt 包](paynes-creek-chinese-script-prompt-pack.md) |
| 程序可读 Scene | [生产草案 JSON](paynes-creek-production-draft.json) |
| Style 是否已经建立和验证 | [16:9 Style 状态审计](paynes-creek-style-state-audit.md) |
| 第一次真实运行发生了什么 | [S03 媒体 Gate](paynes-creek-s03-media-gate.md) |
| 下一次 S03 如何授权、记录与停止 | [S03 重试协议](paynes-creek-s03-retry-protocol.md)；[空白 JSON 模板](paynes-creek-s03-gate-evidence-template.json) |
| S03 通过后怎样逐张验视觉锚点 | [G5 串行锚点协议](paynes-creek-g5-serial-anchor-protocol.md)；[Profile](paynes-creek-g5-anchor-profiles.json)；[空白 attempt](paynes-creek-g5-anchor-attempt-template.json) |
| 12 组媒体如何冻结并只渲染一次 | [G8 Render Manifest 协议](paynes-creek-g8-render-manifest-protocol.md)；[Manifest 模板](paynes-creek-g8-render-manifest-template.json)；[空白 attempt](paynes-creek-g8-render-attempt-template.json) |
| 一次成片如何形成逐镜可复核证据 | [G8-C 帧证据协议](paynes-creek-g8-frame-evidence-protocol.md)；[空白请求](paynes-creek-g8-frame-evidence-request-template.json)；[架构蓝图](../../architecture/native-agent-video-frame-evidence-pack-blueprint.md)；[Sprint 190 合同](../../contracts/sprint-190-native-agent-video-frame-evidence-pack.md) |
| 完整观看如何形成不可变 G8 决定 | [G8 人工验收协议](paynes-creek-g8-human-acceptance-protocol.md)；[空白请求](paynes-creek-g8-human-acceptance-request-template.json)；[交接蓝图](../../architecture/native-agent-local-pilot-acceptance-handoff-blueprint.md)；[Sprint 191 合同](../../contracts/sprint-191-native-agent-immutable-local-pilot-acceptance.md) |
| SiliconFlow 为什么不能直接切地址 | [兼容性决策](../../integrations/siliconflow-native-agent-compatibility-decision.md) |
| 如何实施适配 | [适配蓝图](../../architecture/siliconflow-native-agent-adapter-blueprint.md) |
| 已完成的路由基础 | [Sprint 181 / G2-A 路由快照合同](../../contracts/sprint-181-native-agent-run-route-snapshot-foundation.md) |
| 整支本地样片最终怎样算通过 | [本地样片生产验证章程](paynes-creek-local-pilot-charter.md)；[空白成片验收模板](paynes-creek-local-pilot-acceptance-template.json) |
| G3 如何测试且不触发媒体 | [零媒体 Gate 协议](../../testing/siliconflow-native-agent-zero-media-gate-protocol.md)；[空白证据模板](../../testing/siliconflow-native-agent-zero-media-gate-evidence-template.json) |
| 进入公开实验还缺什么 | [外部依赖清单](external-dependency-readiness.md) |

## 控制器决策

- `input_used`：YouTube 赛道研究、Paynes Creek 来源 / 版权 / 分镜 / 旁白 / Prompt / Run 记录、
  SiliconFlow 兼容性决策与适配蓝图。
- `artifact`：G2-A / G2-B 离线适配、模型调用证据迁移、本运行手册、配套 HTML 控制台、Style 状态审计、G5 串行锚点协议、G6 九镜串行协议、
  G7 语音字幕与 Run 边界协议、
  本地样片生产验证章程、G8 不可变人工验收协议与空白模板。
- `decision`：G2=`pass_offline`，G3 Attempt 2=`pass_for_s03_single_image_review`；真实 Provider 兼容性已在
  固定 5 次零媒体范围内通过，但不能把它扩大为媒体质量已通过或跳过 G4。
- `next_step`：按既有授权和 S03 协议生成唯一一张 S03，执行 VL 与人工事实 / 视觉复核；失败即停止。

本轮完成：G3 已以 5 次真实零媒体请求通过，Tool 恢复、消息边界和证据链一致，媒体仍为 0。
下一步建议：进入 G4，只生成并审核唯一一张 S03。

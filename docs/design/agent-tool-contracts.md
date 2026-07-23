# Agent V1 模型与 Tool 契约

## 1. 契约原则

Agent V1 只向模型暴露完成漫画创作所需的最小能力。工具数量少不等于继续使用固定 Pipeline：Agent 仍然自主决定故事、分镜、Prompt、调用顺序、检查结果和重试方向。

Runtime 不把数据库、积分、Provider 选择、队列或文件系统直接暴露给模型。

## 2. 能力端口与 Skill 加载

### 2.1 `AgentModelPort`

职责：承担 Agent 的文本理解、规划、Function Calling 和最终回应。

它不是 Agent 可调用的 Tool，而是运行 Agent Loop 的模型本身。把“生成文本”再包装成同一个 Agent 的工具会形成不必要的递归调用和上下文分裂。

V1 必须支持：

- system/developer/user 上下文。
- Function Calling。
- 多轮 Tool Call 与 Tool Output。
- 结构化最终输出。
- 应用侧完整历史重放。
- Provider 与模型调用追踪。

### 2.2 `ImageGenerationPort`

职责：根据一个完整、简洁的图片生成请求创建图片版本。

模型可见工具名：`generate_image`。

### 2.3 `VisionInspectionPort`

职责：检查一张或一组图片是否满足明确的漫画质量标准。

模型可见工具名：`inspect_image`。

### 2.4 `SkillRegistry`

Skill 不是外部能力端口，而是 Agent 按需加载的方法说明。基础 instructions 只包含 Skill 的 name、description、version 和内容 hash；模型通过只读 `load_skill` 取得完整 `SKILL.md`。

模型可见工具名：`load_skill`。

Runtime Skill 只能从 `backend/app/agent_skills/` 受控目录读取，不允许模型提供文件路径或任意 URL。Skill 加载必须记录 name、version、hash 和 AgentStep；它不产生业务副作用或费用。

## 3. 资源引用不是 Tool

用户通过界面明确选择的 `@风格`、`@角色`、`@任务`、`@Panel` 和 `@图片版本` 在 Turn 创建时由 Runtime 解析、鉴权和快照，然后作为结构化上下文提供给 Agent。

这样可以避免：

- Agent 用错误名字猜资源。
- 模型绕过用户权限枚举其他人的资源。
- 每轮为了读取已选资源增加无意义 Tool Call。

未来如需让 Agent 主动搜索用户资源，可以单独增加受权限控制的 `search_resources`，但不属于 V1。

## 4. `generate_image`

### 4.1 模型可见输入

```json
{
  "panel_key": "panel-3",
  "purpose": "panel_image",
  "prompt": "完整但简洁的单图画面指令",
  "aspect_ratio": "3:4",
  "reference_image_ids": ["asset-character-linxia", "asset-style-pencil"],
  "revision_instruction": "只加强紧张表情，构图、服装和场景不变"
}
```

字段规则：

- `panel_key` 必须指向当前 Run 已授权的任务 Panel；创建新任务时使用 Runtime 分配的临时 Panel key。
- `purpose` V1 只允许 `panel_image` 或 `character_reference`。
- `prompt` 是 Agent 根据当前上下文生成的最终画面要求，不再由代码拼接多层创作规则。
- `reference_image_ids` 只能引用 Runtime 已提供的资源，不接受任意文件路径或未授权 URL。
- `revision_instruction` 仅修改已有 Panel 时出现，用于审计修改边界。
- 模型不能提供 Provider、API key、积分、用户 ID、版本号或幂等键。

### 4.2 Runtime 注入字段

- `run_id`、`step_id`、`task_id`、`panel_id`
- `user_id`
- `provider` 和实际图片模型
- `idempotency_key`
- 风格、角色和参考图的任务快照
- 积分占用记录

### 4.3 Tool 成功输出

```json
{
  "status": "succeeded",
  "image_version_id": "image-version-id",
  "asset_id": "asset-id",
  "width": 896,
  "height": 1200,
  "provider": "configured-image-provider",
  "model": "task-style-model-snapshot"
}
```

模型只在图片 job 成功并持久化后收到成功输出。排队、生成中和下载中的状态作为用户可见 Runtime 事件展示，不作为虚假的 Tool 成功结果。

### 4.4 Tool 失败输出

```json
{
  "status": "failed",
  "error_code": "IMAGE_PROVIDER_TIMEOUT",
  "message": "图片生成超时，可以调整提示词后重试",
  "retryable": true
}
```

- Tool Output 不包含 API key、完整第三方响应或内部路径。
- `retryable` 由 Runtime 错误分类产生，模型不能自行推断 HTTP 错误是否安全重放。
- 同一个 `idempotency_key` 重放时不得重复创建图片 job 或重复扣费。

## 5. `inspect_image`

### 5.1 模型可见输入

```json
{
  "image_version_ids": ["image-version-id"],
  "checks": [
    "story_alignment",
    "character_consistency",
    "continuity",
    "text_accuracy",
    "visual_artifacts"
  ],
  "expected": {
    "story_beat": "收到家人消息后强忍紧张",
    "characters": ["林夏"],
    "required_text": ["工作还顺利吗？"]
  }
}
```

### 5.2 检查枚举

- `story_alignment`：画面是否表达当前剧情目标。
- `character_consistency`：人物身份、外观、年龄和服装是否连续。
- `continuity`：场景、道具、时间和前后 Panel 是否冲突。
- `text_accuracy`：指定文字是否完整、唯一、可读。
- `visual_artifacts`：肢体、五官、文字乱码和明显生成缺陷。

### 5.3 Tool 成功输出

```json
{
  "status": "succeeded",
  "verdict": "revise",
  "scores": {
    "story_alignment": 0.72,
    "character_consistency": 0.94,
    "continuity": 0.91,
    "text_accuracy": 1.0,
    "visual_artifacts": 0.88
  },
  "issues": [
    {
      "code": "EXPRESSION_TOO_CALM",
      "message": "人物表情过于平静，没有表现紧张感",
      "suggested_change": "只加强眼神和嘴角紧张程度"
    }
  ]
}
```

`verdict` 只允许：

- `accept`
- `revise`
- `ask_user`
- `blocked`

VL 给出检查证据，漫画导演 Agent 决定是否重试；Runtime 仍检查预算和最大调用次数。

## 6. 漫画计划如何保存

漫画计划不是一个外部 Tool。Agent 在需要创建或更新任务时输出受 JSON Schema 约束的 `ComicPlan`：

```json
{
  "title": "被裁员的第七天",
  "summary": "从隐藏失业到重新获得掌控感",
  "panels": [
    {
      "panel_key": "panel-1",
      "story_beat": "早高峰逆着人群走出地铁",
      "visual_goal": "疲惫但克制，不渲染崩溃",
      "required_text": []
    }
  ]
}
```

Runtime 校验完整计划后保存任务和 Panel。保存失败时 Run 明确失败，不把部分计划当作成功任务。

Sprint 114 起，漫画计划先保存为版本化 `comic_plan` Artifact，并创建绑定 Artifact hash 的 Approval Request。用户批准前，Runtime 不创建图片 job、不占用图片积分；请求修改会创建新 Artifact 版本，旧版本保留为 superseded。Artifact/Approval 是 Runtime 确定性状态，不作为模型可绕过的自由 Tool。

## 7. Runtime 内部操作

以下能力不向模型暴露为 Tool：

- 创建 Conversation、Message、Turn、Run、Step。
- 校验资源权限和生成资源快照。
- 创建/更新漫画任务、Panel 和图片版本行。
- Provider 路由和 fallback。
- 积分占用、扣费和释放。
- 文件存储与公网 URL 生成。
- 暂停、继续、取消和服务重启恢复。
- 生成用户可见进度事件。
- 保存 Artifact、Approval 和用户安全事件。
- MLflow Trace 关联与脱敏。

这些操作由 Runtime 根据已校验的模型输出和 Tool Call 确定性执行，避免模型获得不必要的系统权限。

## 8. Tool 通用约束

- Tool Schema 使用严格类型和枚举，拒绝额外字段。
- Tool Call 必须绑定 `run_id` 和 `step_id`。
- 外部副作用必须先持久化 Tool Call，再开始执行。
- Tool Output 必须持久化后才能进入下一次模型调用。
- 失败必须返回稳定错误码和用户安全信息。
- Tool 执行不允许静默切换图片 Provider；当前图片 Provider 规则保持不变。
- Agent 不能通过修改 Prompt 绕过用户权限、积分或安全策略。

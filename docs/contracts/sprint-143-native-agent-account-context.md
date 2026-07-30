# Sprint 143：Native Agent 创作账号 Context 注入

Status: Complete

## Goal

修复 Native Agent 通过 `@创作账号` 选择账号后只推导绑定 Style、却没有把账号资料传入模型
Context 的断链。选中的账号必须在 Run 创建前解析为可审计快照，并用于当前 Run 的普通 Agent
和多 Agent 文案链路。

## In scope

- `creation_channel_id` 继续作为前端到后端的规范账号标识，不从用户文本猜测账号。
- Run 创建时按准确频道 ID 读取账号定位、目标受众、阶段目标、AI 定义、运营备注、频道指标、
  对标账号和最近历史视频，保存为 JSON 快照。
- 快照必须与账号 ID、绑定 Style 快照在同一事务内持久化；运行期间账号资料变化不改变旧 Run。
- 普通 Native Agent instructions 与文案 Director、Writer、Reviewer instructions 都注入
  同一份 `creation_account_context`。
- 未选择创作账号时不注入该 Context。
- 快照数据无法解析时 Run 创建明确失败，不静默省略账号 Context。
- 保留 `get_account_creation_context` Tool，供未通过界面选择账号时按 Skill 白名单主动查询；
  已选择账号的主链路不依赖模型是否调用该 Tool。

## Out of scope

- 不改变创作账号与直接 Style 的互斥规则。
- 不改变 YouTube 发布频道和审核视频 Context。
- 不新增账号资料编辑字段或远程同步逻辑。
- 不自动补跑或改写历史 Run。

## Done means

- 选择 `@创作账号` 创建的 Run 持久化完整账号安全快照。
- 普通 Agent 和多 Agent 文案角色都能直接读取选中账号 Context。
- 自动化覆盖快照内容、旧 Run 稳定性和两类 instructions 注入。
- 真实浏览器可通过 `@` 选择账号并显示准确账号标签；后端集成测试验证请求账号 ID、Run 快照
  与模型 instructions 的完整链路。
- `./scripts/check.sh`、空库迁移、前端构建和浏览器控制台验收通过。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_native_agent_loop \
  backend.tests.test_native_article_workflow \
  backend.tests.test_account_creation_context
npm --prefix frontend test
npm --prefix frontend run build
./scripts/check.sh
git diff --check
```

## Completion evidence

- 根因确认：Sprint 140/141 只把 `creation_channel_id` 用于推导绑定 Style，没有把账号资料
  保存到 Run 或传入模型。
- 新迁移为 `native_agent_runs` 增加 `creation_channel_context_json`；开发库和空库迁移
  均已通过。
- Run 创建按准确频道 ID 保存账号定位、目标受众、阶段目标、AI 定义、运营备注、频道指标、
  对标账号和近期视频的有界快照；账号后续修改不会改变旧 Run。
- 普通 Native Agent 以及文案 Director、Writer、Reviewer 均注入同一
  `<creation_account_context>`，不依赖 Skill 是否开放查询账号 Tool。
- 真实浏览器选择“中国文明长纪录片”后显示 `@创作账号` 标签与绑定 Style；使用开发库真实
  数据验证 Context 包含定位、受众和 1 个对标账号，且 instructions 可读取定位和受众。
  未调用收费模型，也未创建新的对话 Run。
- 定向 44 项后端测试与 `./scripts/check.sh` 全部通过；统一检查覆盖 339 项后端测试、空库
  迁移、14 项前端测试、前端生产构建、Remotion 类型检查和 5 项测试。

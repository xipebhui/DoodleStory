# Sprint 139：账号创作上下文 Tool

状态：完成

## Goal

让 Native Agent 根据用户自然语言中的账号名称读取平台已保存的账号定位、受众、阶段目标、
AI 定义、运营备注、对标账号和近期视频，不要求用户输入内部账号 ID。

## In Scope

- 新增只读 `get_account_creation_context(account_name)` Native Agent Tool。
- 按账号别名、Handle、频道标题和远程频道 ID 做规范化精确匹配。
- 唯一精确命中时返回内部稳定账号 ID、完整创作策略、统计、对标账号和有界近期视频。
- 没有精确命中时返回不超过 5 个候选；重名或模糊匹配不得静默选中。
- Tool 只允许当前 Run 的管理员 owner 读取现有管理员频道数据。
- 把 Tool 加入 Skill 管理目录、Native Agent 白名单、能力声明和运行时构建。
- 增加唯一命中、候选歧义、权限和 Tool 白名单测试。

## Out of Scope

- 不修改账号、对标或历史视频数据库结构。
- 不实现对标视频 Transcript、脚本抓取或文风分析。
- 不自动同步远程频道、统计或视频。
- 不实现完整选题、文案或媒体生产 Skill。
- 不把模糊搜索的单个结果当作精确命中。

## Deliverables

- 本地账号创作上下文查询服务与 Native Agent Tool。
- Skill Tool 目录、能力声明和运行时接入。
- 聚焦自动化测试和进度记录。

## Done Means

- 用户说“给历史商业取证做选题”时，模型可以调用
  `get_account_creation_context(account_name="历史商业取证")`，无需知道账号 ID。
- Tool 唯一命中后返回完整定位、受众、阶段目标、AI 定义、运营备注和对标研究。
- 重名、模糊匹配、未找到、非管理员调用均返回明确结果或错误，不泄露账号邮箱。
- 未勾选该 Tool 的 Skill 不会向模型暴露它。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest \
  backend.tests.test_account_creation_context \
  backend.tests.test_native_agent_loop \
  backend.tests.test_agent_skill_management
./scripts/check.sh
git diff --check
```

Manual check:

- 使用本地数据库的“历史商业取证”验证完整上下文返回。
- 使用部分名称验证只返回候选，不自动绑定。

## Risks / Notes

- 当前频道数据是管理员共享资源，没有普通用户 owner 字段，因此 Tool 保持现有频道管理权限边界。
- 对标 notes 足够支持当前选题，但精确文风模仿仍需要后续接入正文或 Transcript。

## Handoff

- 下一步把该 Tool 写入正式内容生产 Skill，并实现选题确认 Artifact。

## Actual Result

- 新增 `get_account_creation_context(account_name)` Native Function Tool，并按当前 Run 的
  Conversation owner 校验管理员权限。
- 精确匹配按别名、Handle、频道标题、远程频道 ID 的顺序执行；`@Handle` 与无 `@` 存储格式
  均可命中。部分匹配和重名只返回候选，不注入创作策略。
- 唯一命中返回账号定位、目标受众、阶段目标、AI 定义、运营备注、频道汇总指标、最多 10 个
  对标账号和最多 10 条近期视频；视频描述与标签有显式上下文边界，不返回账号邮箱和原始
  Analytics JSON。
- Tool 已进入 Skill Tool 目录、Native Runtime 白名单、能力接口和前端显示名称。
- 40 项聚焦测试通过；`./scripts/check.sh` 通过 334 项后端测试、空库 Alembic 全量升级、
  8 项前端测试、前端生产构建、Remotion typecheck 与 5 项测试。
- 本地真实数据库只读 smoke 使用“历史商业取证”按 alias 唯一命中，创作策略完整，返回
  1 个对标账号；该账号当前没有本地已发布视频，因此近期视频为 0。

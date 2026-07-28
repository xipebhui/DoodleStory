# Sprint 137：微信公众号文章采集 Agent Tool

状态：已完成

## Goal

把同级 `douyin-import-service` 中已调通的微信公众号文章抓取能力接入
DoodleStory Native Agent，并在 Skill 管理页面中作为可选择的微信公众号 Tool
明确展示。

## In Scope

- 新增 `capture_wechat_article(url)` Native Agent Tool，只接受
  `mp.weixin.qq.com` 文章链接。
- 通过多平台导入服务 `POST /api/v1/import` 获取文章正文和来源元数据，不在
  DoodleStory 内复制 Crawl4AI / Playwright 实现。
- 将完整 Markdown 正文保存为 `FileAsset`，并将来源 URL、标题、作者、发布时间、
  平台内容 ID、标签和指标保存为可追踪的 Agent 外部内容记录。
- Tool 向模型返回内容记录 ID、正文资产 ID、来源摘要和有限长度正文预览，避免把完整
  长文无条件塞入模型上下文。
- Native Agent 会话详情 API 返回文章采集记录。
- Skill Tool 目录和管理页面明确显示“微信公众号文章”及其能力说明。
- Coolify Compose 改用同级多平台导入服务，使部署环境真实包含公众号抓取依赖。

## Out of Scope

- YouTube 频道、视频、评论采集。
- 小红书或抖音 Agent Tool。
- 公众号账号文章列表、搜索、评论和登录态管理。
- 对文章内容做自动评分、总结或对标分析。
- 新增重试、降级、Mock 或备用抓取链路。

## Done Criteria

- 已发布 Skill 可以选择 `capture_wechat_article`，Native Runtime 只在 Skill
  勾选后向模型暴露该 Tool。
- 非微信公众号 URL 在发起外部请求前被明确拒绝。
- 成功调用真实 `/api/v1/import` 后，正文资产和来源记录持久化，Tool 返回稳定的
  `external_content_id` 与 `asset_id`。
- 同一 Tool 调用遵循现有 Native Agent Step 幂等、失败记录和手动重试规则。
- Skill 管理列表、详情与编辑页都能辨认该 Tool 属于微信公众号文章采集。
- Compose 配置能够构建多平台导入服务，并共享抓取结果目录给 DoodleStory。

## Verification

- 后端测试覆盖导入服务响应校验、公众号域名校验、Tool 成功持久化与重复调用复用。
- Skill 管理测试覆盖 Tool 目录和白名单。
- 数据库迁移 upgrade / downgrade 检查。
- 前端 TypeScript 构建与项目 `./scripts/check.sh` 通过。
- Compose 配置展开检查通过；没有真实公众号 URL 时不伪造端到端抓取结果。

## Handoff

下一 Sprint 再基于统一外部内容记录讨论 YouTube 频道、视频与评论读取 Tool；本
Sprint 不预埋未启用平台枚举分支。

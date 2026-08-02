# Sprint 151：Video API 文档本地归档

## 状态

Complete

## 目标

把 `video.inboxlinks.top` 的公开 Video API 文档完整摘取为本地 Markdown，便于项目内查阅和后续接口接入。

## In Scope

- 从 `/api-docs/` 首页递归发现全部站内文档页面。
- 使用通用网页内容提取器保存每个页面的 Markdown 和来源 frontmatter。
- 将文档集中保存到 `docs/external-api/video-inboxlinks/`，并提供本地索引。

## Out of Scope

- 不调用视频发布、上传、分析或刷量接口。
- 不下载页面中的图片或视频媒体。
- 不根据文档内容实现 API 客户端或修改业务代码。

## Deliverables

- 11 篇本地 Markdown 文档。
- 文档归档索引 `docs/external-api/video-inboxlinks/README.md`。
- 项目级 URL 转 Markdown 偏好配置。

## Done Means

- 每个站内 `/api-docs/` 文档路由都有对应的本地 Markdown 文件。
- 文件标题、来源 URL 和正文通过质量门禁检查，没有登录墙、404 或框架错误页。
- 仓库检查和差异格式检查通过。

## Verification

```powershell
git diff --check
./scripts/check.sh
```

Manual or QA checks:

- 递归抓取站内导航得到 11 个文档路由。
- 逐文件核对标题、URL、正文长度、标题层级和错误页标记。
- `git diff --check` 与归档专属检查通过；`scripts/check.sh` 已尝试，但当前 WSL 缺少
  `python3.11`，且仓库没有可用项目虚拟环境，因此未完成标准脚本的后续代码测试。

## Risks / Notes

- 文档内容来自 2026-08-02 的公开页面快照；远程页面后续更新时需要重新抓取。
- 本次只新增文档和项目级抓取偏好，没有修改运行时代码；标准全量检查的环境限制不影响归档专属检查。

## Handoff

- Next likely step: 在真正接入发布 API 前，依据 `auth-conventions.md` 和对应资源文档设计客户端封装。

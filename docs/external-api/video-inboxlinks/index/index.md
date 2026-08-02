---
title: "Video API 文档 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/"
requestedUrl: "https://video.inboxlinks.top/api-docs/"
siteName: "Video API 文档"
summary: "YouTube 视频上传、频道管理与数据分析 API 接口文档"
adapter: "generic"
capturedAt: "2026-08-02T03:26:35.799Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## Video API 文档

完整的 YouTube 视频管理 API 接口文档，涵盖视频上传、频道管理与数据分析

## 概览

本文档面向 **调用方/集成方** ，用于说明如何通过 HTTP API 与服务端交互，以完成「YouTube 频道管理 → 创建上传计划任务 → 查询上传结果 → 后续操作（改可见性/评论等）→ 数据分析」的完整流程。

快速开始

3 分钟跑通完整上传流程，了解核心调用链路。

认证与约定

API Key 认证方式、HTTP 规范、日期时间格式与错误码。

通用 CRUD 接口

标准化的增删改查接口规范，支持复杂条件查询与游标分页。

YouTube 频道管理

获取频道列表、修改频道信息、设置频道横幅图片。

频道刷量任务

开始/停止频道刷量任务，查询任务当前状态。

上传任务

创建与管理异步上传到 YouTube 的计划任务。

已上传视频

管理已成功上传到 YouTube 的视频：查询、删除、改可见性、评论。

视频分析数据

获取视频最新汇总数据（含时序 points）与观众留存曲线。

频道分析数据

获取频道最新汇总数据。

更新日志

查看 API 字段与行为变更记录。

## 建议阅读顺序

1. [认证与约定](https://video.inboxlinks.top/api-docs/auth-conventions/) — 了解认证方式与通用规则
2. [通用 CRUD 接口](https://video.inboxlinks.top/api-docs/crud/) — 掌握标准查询、分页、游标续拉
3. [YouTube 频道管理](https://video.inboxlinks.top/api-docs/youtube-channels/) — 获取可用频道
4. [频道刷量任务](https://video.inboxlinks.top/api-docs/channel-boost/) — 开始/停止频道刷量任务
5. [上传任务](https://video.inboxlinks.top/api-docs/upload-tasks/) — 创建上传计划
6. [已上传视频](https://video.inboxlinks.top/api-docs/uploaded-videos/) — 查看上传结果与后续操作
7. [视频分析数据](https://video.inboxlinks.top/api-docs/video-analytics/) — 查看视频数据指标
8. [频道分析数据](https://video.inboxlinks.top/api-docs/channel-analytics/) — 查看频道数据指标
9. [更新日志](https://video.inboxlinks.top/api-docs/changelog/) — 了解近期字段与接口变更
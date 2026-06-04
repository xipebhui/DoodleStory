# Sprint 06 合同：抖音下载 Cookie 与导入适配

## 当前状态

本 sprint 是早期验证记录：当时用 `jiji262/douyin-downloader` 官方 Cookie 登录流程和后端子进程 adapter 验证了抖音图文下载可行性。后续 Sprint 07 起，DoodleStory 的正式集成边界改为调用独立 HTTP 下载服务，主仓库不再保留旧的直连 adapter、Cookie 获取脚本或命令行下载脚本。

当前有效运行链路：

1. DoodleStory 后端通过 `app/services/douyin_import_service.py` 调用同机下载服务。
2. 下载服务地址由 `DOUYIN_IMPORT_SERVICE_BASE_URL` 配置，默认 `http://127.0.0.1:8010`。
3. Cookie、下载器源码和下载产物顺序处理都属于独立下载服务的职责，不放在 DoodleStory 主仓库内。

## 历史目标

接入外部抖音下载器的 Cookie 获取与下载运行方式，为后续把抖音视频或图文素材导入 DoodleStory 做最小可验证基础。

## 历史范围

- 按外部下载器官方方式获取 Cookie。
- 通过临时后端 adapter 调用外部下载器并验证媒体文件落盘。
- 明确暴露路径、Cookie、下载失败和无媒体文件等错误。
- 不把外部下载器源码 vendoring 到本仓库。
- 不新增前端素材导入 UI、数据库表或素材管理后台。
- 不把 Cookie 写入仓库、日志或临时下载配置。

## 后续内容提取设计边界

用户后续需要新增 `内容提取` tab：由后端解析抖音分享文本中的真实 URL，同步调用同机抖音下载服务 `127.0.0.1:8010` 下载图文或视频；下载完成后，用户再同步触发文案提取，视频先分离音频并调用 SiliconFlow 音频多模态能力提取原始文案，图文按图片顺序逐张调用 SiliconFlow 视觉理解能力提取图片文字。该需求已记录在 `docs/design/content-extraction.md`，并在后续 sprint 中实现。

## 当前完成标准

- DoodleStory 主仓库只保留 HTTP 下载服务调用配置。
- 旧的直连下载 adapter 和临时脚本已移出主仓库。
- `.env.example` 只说明当前内容提取集成所需配置。
- 已运行相关检查。

## 当前验证

```bash
./scripts/check.sh
curl -sS http://127.0.0.1:8010/health
```

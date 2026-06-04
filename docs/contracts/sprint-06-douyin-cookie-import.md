# Sprint 06 合同：抖音下载 Cookie 与导入适配

## 目标

接入 `jiji262/douyin-downloader` 的 Cookie 获取与下载运行方式，为后续把抖音视频或图文素材导入 DoodleStory 做最小可验证基础。

## 范围内

- 增加 DoodleStory 后端配置：
  - `DOUYIN_DOWNLOADER_ROOT` 指向外部 `jiji262/douyin-downloader` 仓库。
  - `DOUYIN_DOWNLOADER_PYTHON` 指向该下载器依赖所在 Python，可为空，默认使用当前 Python。
  - `DOUYIN_COOKIE` 支持直接传入浏览器 Cookie header。
  - `DOUYIN_COOKIE_FILE` 支持读取官方 `tools.cookie_fetcher` 生成的 JSON Cookie 文件。
  - `DOUYIN_DOWNLOAD_TIMEOUT_SECONDS` 控制单次下载超时。
- 增加 Cookie 获取脚本，按下载器官方方式打开浏览器登录并保存 Cookie JSON。
- 增加后端下载 adapter，通过子进程运行外部下载器，并把 Cookie 临时注入环境变量。
- 下载 adapter 必须显式报错：
  - 下载器仓库路径缺失或错误。
  - Cookie 缺失或 Cookie 文件无效。
  - 下载器退出失败。
  - 命令执行后没有产生媒体文件。
- 增加命令行测试脚本，用于输入抖音链接并检查实际落盘媒体文件。

## 范围外

- 不把 `jiji262/douyin-downloader` 源码 vendoring 到本仓库。
- 不新增前端素材导入 UI。
- 不新增数据库表或素材管理后台。
- 不默认启用浏览器兜底、评论采集、转写、封面、头像或音乐下载。
- 不把 Cookie 写入仓库、日志或临时下载配置。

## 后续内容提取设计边界

用户后续需要新增 `内容提取` tab：由后端解析抖音分享文本中的真实 URL，调用同机抖音下载服务 `127.0.0.1:8010` 下载图文或视频；下载完成后，视频先分离音频并调用 SiliconFlow 音频多模态能力提取原始文案，图文按图片顺序逐张调用 SiliconFlow 视觉理解能力提取图片文字。该需求已记录在 `docs/design/content-extraction.md`。

该内容不纳入 Sprint 06 的实现范围。Sprint 06 仍只负责旧的下载器 Cookie、后端 adapter 和命令行验证入口；内容提取 tab、下载服务代理、内容提取数据库记录和前端页面应在新的 sprint contract 中实现。

## 完成标准

- `.env.example` 说明抖音下载器与 Cookie 配置。
- `scripts/fetch-douyin-cookie.sh` 可调用官方 `tools.cookie_fetcher` 保存 Cookie JSON。
- `scripts/test-douyin-download.sh <url>` 可通过后端 adapter 调用下载器。
- 缺少 Cookie 时返回明确配置错误。
- 已运行 `./scripts/check.sh`。

## 验证

```bash
./scripts/check.sh
```

人工验证：

```bash
export DOUYIN_DOWNLOADER_ROOT=/path/to/douyin-downloader
export DOUYIN_DOWNLOADER_PYTHON=/path/to/python
./scripts/fetch-douyin-cookie.sh
./scripts/test-douyin-download.sh "https://v.douyin.com/..."
```

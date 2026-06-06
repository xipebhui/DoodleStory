# Sprint 27 合同：统一生图 Gateway 接入

## 目标

接入 `docs/api_v3.md` 中已同意的 OpenAI Images 兼容生图服务，把当前可用生图模型统一路由到 `/v1/images/generations`，减少旧 SiliconFlow、ApexerAPI Chat 和 XG edits 多分支路由带来的复杂度。

## 范围内

- 后端新增统一生图 gateway 配置：
  - `IMAGE_GATEWAY_BASE_URL`
  - `IMAGE_GATEWAY_API_KEY`
- 当前可用生图模型精确限定为：
  - `gpt-image-2`
  - `Tongyi-MAI/Z-Image`
  - `Qwen/Qwen-Image`
  - `baidu/ERNIE-Image-Turbo`
  - `gemini_3.1_flash_image_preview`
  - `gemini_3.0_pro_image_preview`
  - `gemini_3.1_flash_image_preview_4K`
  - `gemini_3.0_pro_image_preview_4K`
  - `gemini-3.1-flash-image-preview`
  - `gemini-3-pro-image-preview`
- 统一请求 `POST /images/generations`，保留现有 timeout 重试、请求/响应脱敏日志、结果保存到 DoodleStory 资产的行为。
- 响应必须同时支持 `data[0].url` 和 `data[0].b64_json`。
- 参考图按 `images` 数组传入；当模型超过文档限制的参考图数量时明确报错。
- 风格测试、人物参考图、任务 panel 生图和单 panel 修改继续通过现有任务链路调用统一 gateway。
- 更新产品规格和进度文档，记录本次 provider 收敛。

## 范围外

- 不接入视频生成。
- 不接入未列入当前可用清单的模型。
- 不自动回退到旧 XG、ApexerAPI Chat 或 SiliconFlow 直连接口。
- 不把图片模型做成独立管理模块。
- 不迁移历史任务或历史风格配置。

## 完成标准

- 当前可用模型走统一 `/images/generations`。
- 未列入清单的模型返回明确配置错误，不静默走旧 provider。
- `data[0].url` 返回会下载图片并保存资产。
- `data[0].b64_json` 返回会解码图片并保存资产。
- `backend/.venv/bin/python -m compileall backend/app`、`git diff --check` 和 `./scripts/check.sh` 通过。

# Sprint 35 合同：显式生图 Provider 切换

## 目标

为临时排查内部 QY `gpt-image-2` 多图不稳定提供显式切换能力。后端可通过 `IMAGE_PROVIDER=qy|xgapi` 选择生图 provider，但不做自动兜底、不做失败后降级，也不把 xgapi 的请求格式混入 QY 代码。

## 范围内

- 新增 `IMAGE_PROVIDER` 配置，默认 `qy`。
- 保留 QY adapter 的公网 URL + `image`、`image2`、`image3` 请求格式。
- 新增 xgapi adapter：
  - 无参考图走 `/v1/images/generations` JSON。
  - 有参考图走 `/v1/images/edits` JSON。
  - 多张参考图使用 `image: [url1, url2]` 公网 URL 数组。
  - `model` 必须使用任务保存的风格模型快照，不允许通过 `XG_IMAGE_MODEL`、代码默认值或其他环境变量覆盖用户在风格里选择的模型。
- 人物参考图打包只向 provider 传递公网 URL，不下载本地文件，不转 base64。
- 新增 `scripts/switch-image-provider.sh qy|xgapi`，只切换 provider 标记，不写入密钥。
- 增加单元测试覆盖 provider routing 和 xgapi 多图提交格式。

## 范围外

- 不在 UI 暴露 provider 或密钥。
- 不把 xgapi 作为 QY 失败后的自动 fallback。
- 不修改风格库里的模型字段。
- 不提供 xgapi 专用兜底模型；如果任务没有模型或 xgapi 不支持该模型，必须明确失败。
- 不调用真实外部 QY 或 xgapi 服务。
- 不迁移历史任务或历史图片。

## 完成标准

- `IMAGE_PROVIDER=qy` 时只调用 QY adapter。
- `IMAGE_PROVIDER=xgapi` 时只调用 xgapi adapter。
- xgapi 请求体中的 `model` 等于任务风格模型快照。
- xgapi 无参考图请求体是 JSON generations。
- xgapi 多参考图请求体是 JSON edits，且包含 `image` 公网 URL 数组。
- 单元测试、后端编译、前端构建、`git diff --check` 和 `./scripts/check.sh` 通过。

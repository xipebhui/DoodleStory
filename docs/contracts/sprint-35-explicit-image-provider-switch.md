# Sprint 35 合同：显式生图 Provider 切换

## 目标

为临时排查内部 QY `gpt-image-2` 多图不稳定提供显式切换能力。后端可通过 `IMAGE_PROVIDER=qy|xgapi` 选择生图 provider，但不做自动兜底、不做失败后降级，也不把 xgapi 的请求格式混入 QY 代码。

## 范围内

- 新增 `IMAGE_PROVIDER` 配置，默认 `qy`。
- 保留 QY adapter 的公网 URL + `image`、`image2`、`image3` 请求格式。
- 新增 xgapi adapter：
  - 无参考图走 `/v1/images/generations` JSON。
  - 有参考图走 `/v1/images/edits` multipart。
  - 多张参考图使用重复 `image` form part，字段值直接使用公网 URL。
- 人物参考图打包只向 provider 传递公网 URL，不下载本地文件，不转 base64。
- 新增 `scripts/switch-image-provider.sh qy|xgapi`，只切换 provider 标记，不写入密钥。
- 增加单元测试覆盖 provider routing 和 xgapi 多图提交格式。

## 范围外

- 不在 UI 暴露 provider 或密钥。
- 不把 xgapi 作为 QY 失败后的自动 fallback。
- 不修改风格库里的模型字段。
- 不调用真实外部 QY 或 xgapi 服务。
- 不迁移历史任务或历史图片。

## 完成标准

- `IMAGE_PROVIDER=qy` 时只调用 QY adapter。
- `IMAGE_PROVIDER=xgapi` 时只调用 xgapi adapter。
- xgapi 无参考图请求体是 JSON generations。
- xgapi 多参考图请求体是 multipart edits，且包含重复 `image` URL form part。
- 单元测试、后端编译、前端构建、`git diff --check` 和 `./scripts/check.sh` 通过。

# Sprint 34 合同：QY 参考图公网 URL 字段格式

## 目标

修正统一生图平台携带多张参考图时的请求体格式。QY / `gpt-image-2` 多参考图不再使用 `images` 数组，也不再把参考图转成 `data:image/...;base64,...`，而是直接使用人物参考图资产的公网 URL，并按 `image`、`image2`、`image3` 独立字段提交。

## 范围内

- Provider 请求构造从 `reference_paths` 改为 `reference_urls`。
- 人物参考图打包阶段直接读取 `FileAsset.public_url`，缺少公网 URL 时明确失败。
- 统一生图 Gateway payload 使用 `image`、`image2`、`image3` 字段保存参考图公网 URL。
- 拒绝非 HTTP(S) 参考图，避免重新回到 base64 data URL。
- 更新正式 panel 生图和单 panel 修改的参考图传递路径。
- 增加单元测试覆盖 QY 公网 URL 字段格式。

## 范围外

- 不调用真实外部 QY 服务。
- 不改变人物参考图自身的生成流程。
- 不改变结果图解析逻辑，仍兼容 `data[0].url` 和 `data[0].b64_json`。
- 不引入 XG 或其他生图兜底。

## 完成标准

- 两张参考图时 payload 包含 `image` 和 `image2`，不包含 `images`。
- 参考图字段值是公网 URL，不包含 `data:image` 前缀。
- 单元测试、后端编译、前端构建、`git diff --check` 和 `./scripts/check.sh` 通过。

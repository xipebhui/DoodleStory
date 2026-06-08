# Sprint 40 合同：Policy Blocked 生图切换百度模型

## 目标

当生图 Provider 明确返回 Google policy blocked 类错误时，自动改用 `baidu/ERNIE-Image-Turbo` 重新生成该图，并且不提交任何参考图。该模型切换只处理用户明确指定的 policy blocked 场景，不作为普通 Provider 失败兜底。

## 范围内

- 识别 `Unable to show the generated image`、`Generative AI Prohibited Use policy`、`filtered out` 等明确 policy blocked 错误。
- 正式任务 panel 生图遇到该错误时，使用同一 final prompt 改走 `baidu/ERNIE-Image-Turbo` 重试一次。
- 单 panel 修改生图遇到该错误时，也使用同一 final prompt 改走 `baidu/ERNIE-Image-Turbo` 重试一次。
- 切换模型时参考图列表必须为空，因为 `baidu/ERNIE-Image-Turbo` 不支持参考图。
- 成功后图片版本的 `image_model_name_snapshot` 写入实际使用的百度模型名。
- 增加单元测试覆盖 policy blocked 切换和普通 Provider 错误不切换。

## 范围外

- 不改写 prompt。
- 不对普通 400、配置错误、timeout、下载错误或非 policy blocked 错误切换模型。
- 不把该逻辑下沉到 QY 或 XG provider 基础适配层。

## 完成标准

- 远程任务 `3564da7ea27e496bb30fdb608441e51c` 的 panel 9 prompt 已验证可用 `baidu/ERNIE-Image-Turbo`、无参考图生成成功。
- policy blocked 后的第二次请求不携带参考图。
- `./scripts/check.sh` 通过。

## 风险 / 说明

- 百度模型不支持参考图，切换后角色一致性可能弱于原模型，但可避免 Google policy blocked 导致单图失败。
- 如果百度模型也失败，任务仍按失败处理并展示明确错误。

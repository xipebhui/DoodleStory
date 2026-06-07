# Sprint 30 合同：生图只使用统一平台

## 目标

根据 `docs/api_v4.md` 的最新路由约定，DoodleStory 后端只调用统一生图平台 `/v1/images/generations`。`gpt-image-2`、线路别名和 `nano-banana` 系列模型的供应商选择由统一生图平台内部路由负责，DoodleStory 不再直连 XG 作为兜底。

## 范围内

- 保留 `IMAGE_GATEWAY_BASE_URL` 和 `IMAGE_GATEWAY_API_KEY` 作为唯一生图平台配置。
- 扩展统一平台模型白名单，兼容 `docs/api_v4.md` 新增的图片模型和历史别名。
- 删除 Gateway 失败后切换到 XG `/v1/images/generations` 或 `/v1/images/edits` 的后端兜底逻辑。
- 清理不再使用的 XG 直连配置示例与单元测试。
- 更新产品规格和进度记录，明确生图失败时由统一平台错误直接暴露，不在 DoodleStory 内做 provider 兜底。

## 范围外

- 不改变风格库中的图片模型输入方式，仍由用户手动填写模型名。
- 不在 UI 暴露 provider、channel、API key 或线路选择。
- 不修改统一生图平台本身的 channel 优先级、模型映射或内部兜底策略。
- 不迁移历史任务或历史生成结果。

## 完成标准

- DoodleStory 生图请求只调用统一平台。
- Gateway Provider 响应错误不会触发 XG fallback。
- `docs/api_v4.md` 新增的统一平台模型名不会被本地白名单拒绝。
- `backend/.venv/bin/python -m unittest discover -s backend/tests`、`backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过。

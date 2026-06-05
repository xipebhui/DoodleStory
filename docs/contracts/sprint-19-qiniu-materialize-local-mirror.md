# Sprint 19 合同：七牛资产本地镜像优先读取

## 目标

修复远程生成任务在七牛存储配置下，为了读取刚生成的人物参考图又从公开 CDN 回拉，导致 `cdn.vdgen.shop` 读取超时并使任务失败的问题。

## 范围内

- `materialize_asset_to_local()` 读取七牛资产时，先检查 `storage_key` 对应的服务器本地镜像。
- 本地镜像存在且非空时直接返回本地路径，不访问公开 CDN。
- 已有 `_cache/qiniu` 缓存仍保留为第二优先级。
- 镜像和缓存都不存在时，保留现有公开 CDN 下载逻辑用于历史资产。
- 更新规格和进度记录。

## 范围外

- 不修改七牛上传逻辑。
- 不迁移历史资产。
- 不改变前端展示使用固定公开 CDN URL 的规则。
- 不改变任务重试接口或任务状态机。

## 完成标准

- 远程任务中的七牛人物参考图如果已有本地镜像，准备 panel 参考图时不再访问 `cdn.vdgen.shop`。
- `backend/.venv/bin/python -m compileall backend/app` 和 `./scripts/check.sh` 通过。

## 验证

自动验证：

```bash
backend/.venv/bin/python -m compileall backend/app
./scripts/check.sh
```

功能验证：

1. 单元级 smoke 构造七牛资产和本地镜像，禁用 `requests.get` 后确认 `materialize_asset_to_local()` 仍返回本地镜像路径。
2. 远程用任务 `bec1e4f7dda144278b4254bf4eba4d7d` 的人物参考图资产验证本地镜像存在。

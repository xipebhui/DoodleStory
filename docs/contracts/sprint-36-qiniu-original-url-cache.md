# Sprint 36 合同：七牛原图 URL 缓存污染修复

## 目标

修复生成图片在对象存储公网 URL 下显示为 320x568 WebP 缩略图的问题。对象存储中的原始文件应通过原图 URL 直接展示原图，不能因为缩略图 query 请求污染同一路径缓存。

## 范围内

- 七牛资产的前端 `thumbnail_url` 不再追加 `imageView2` query 参数。
- 七牛资产接口的 `thumbnail` 变体不再返回同 key query 缩略图 URL。
- 保持 `public_url` 作为对象存储原图固定公网 URL。
- 增加测试覆盖七牛原图和缩略图 URL 都不带图片处理 query。
- 更新规格和进度文档。

## 范围外

- 不新增后端原图代理下载路径。
- 不新增自动降级或 fallback。
- 不迁移历史资产 key。
- 不调用七牛刷新 CDN 缓存接口。

## 完成标准

- 新返回给前端的七牛 `content_url` 和 `thumbnail_url` 都是无 query 的对象原图 URL。
- `/assets/{id}/content?variant=thumbnail` 对七牛资产跳转到无 query 的对象原图 URL。
- 单元测试和项目检查通过。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_qiniu_asset_urls.py
./scripts/check.sh
```

## 风险 / 说明

- 现有已经被 CDN 缓存污染的历史 URL 可能仍需等待缓存过期、手动刷新 CDN，或重新生成新 key 才能立即恢复。
- 列表缩略图暂时会使用原图 URL，带宽会比缩略图方案高；后续如需缩略图，应生成独立对象 key，而不是同 key query 处理。

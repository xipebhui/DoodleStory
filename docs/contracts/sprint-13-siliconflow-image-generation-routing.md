# Sprint 13 合同：SiliconFlow 生图模型路由

## 目标

当风格绑定的生图模型名为 SiliconFlow 图片生成模型时，后端应调用 SiliconFlow `/v1/images/generations`，并把返回的一小时有效图片 URL 立即下载保存为 DoodleStory 资产。

## 范围内

- 后端生图 Provider 路由：
  - `Qwen/Qwen-Image-Edit-2509`
  - `Qwen/Qwen-Image-Edit`
  - `baidu/ERNIE-Image-Turbo`
  - `Qwen/Qwen-Image`
- SiliconFlow 图片生成请求：
  - 使用已有 `SILICONFLOW_API_KEY` 和 `SILICONFLOW_BASE_URL`。
  - 请求地址为 `/images/generations`。
  - 按模型能力构造 `image_size`、`cfg`、`num_inference_steps` 和参考图字段。
  - 解析 `images[0].url`，立即下载并写入现有文件存储。
- 保持现有调用方不变：
  - 风格测试、任务 panel 生图、人物参考图和单 panel 修改继续使用统一生图入口。
  - 其它模型仍按现有 ApexerAPI 或 XG 路由处理。
- 更新规格、接口文档和进度记录。

## 范围外

- 不新增前端模型选择器。
- 不新增数据库字段或迁移。
- 不新增外部队列、降级 Provider 或 mock 生图结果。
- 不改变已有 XG `/v1/images/edits` 与 ApexerAPI `/v1/chat/completions` 路由。

## 完成标准

- 以上 4 个模型名精确命中时走 SiliconFlow 图片生成接口。
- SiliconFlow 返回的 URL 不直接暴露给前端，必须下载后保存到 `file_assets`。
- 参考图数量超过对应模型能力时，任务或风格测试应明确失败，不能静默丢弃参考图。
- `python3.11 -m compileall backend/app` 和 `./scripts/check.sh` 通过。

## 验证

自动验证：

```bash
python3.11 -m compileall backend/app
./scripts/check.sh
```

功能验证：

1. 用单元级脚本确认 `Qwen/Qwen-Image-Edit-2509` payload 使用 `/images/generations`、`cfg=4` 和 `image/image2/image3`。
2. 用单元级脚本确认 `Qwen/Qwen-Image` payload 使用推荐 `image_size` 和 `cfg=4`。
3. 用单元级脚本确认 SiliconFlow `images[0].url` 会进入下载路径。

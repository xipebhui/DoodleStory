# Sprint 98 合同：内容提取图文 VL 切换到 gpt-5.4

## Goal

将抖音图文内容提取的图片理解模型从 SiliconFlow/Qwen VL 切换到 `TEXT_FALLBACK_*` 配置的 `gpt-5.4` 多模态模型，并阻止少页、跳页或合并页的模型结果被标记为成功。

## In Scope

- 图文内容提取 `extract_ordered_gallery_comic_content` 改为调用 `TEXT_FALLBACK_BASE_URL`、`TEXT_FALLBACK_API_KEY` 和 `TEXT_FALLBACK_MODEL`。
- 图文内容提取仍一次性按顺序传入全部图片公网 URL，不改成逐页调用。
- 模型返回结果必须包含连续 `第1页` 到 `第N页`，其中 `N` 等于下载图片数量。
- 页数不一致时内容提取失败，提示用户图片解析页数和下载图片数量不一致。
- 保留 SiliconFlow 音频转写和角色参考图外观理解链路，不做无关替换。
- 更新规格、内容提取设计、部署文档和进度记录。
- 单元测试覆盖 gpt-5.4 VL 调用和页数不一致失败。

## Out of Scope

- 不把 SiliconFlow/Qwen 作为 `gpt-5.4` 失败后的自动兜底。
- 不新增逐页重试、自动补页、自动合并或自动修复提取结果。
- 不自动重跑已经成功或失败的历史内容提取记录。
- 不改变视频音频转写、风格提示词提取、角色参考图描述或生图 Provider。

## Deliverables

- 后端图文内容提取服务改用 `TEXT_FALLBACK_*` OpenAI 兼容多模态调用。
- 图文提取结果页码连续性校验。
- 相关单元测试。
- 文档同步。

## Done Means

- 14 张图片如果模型只返回 12 页，内容提取记录应失败，并显示“图片解析出的页数（12）和下载图片数量（14）不一致”一类明确提示。
- 成功结果必须页码严格连续，避免污染后续 `提取分镜` 生图任务。
- 线上配置 `TEXT_FALLBACK_MODEL=gpt-5.4` 后，图文内容提取不再调用 Qwen VL。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_content_extraction_media_flow
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

## Risks / Notes

- 该变更依赖生产环境已经配置可用的 `TEXT_FALLBACK_*` 多模态模型；缺失时内容提取会明确失败。
- `TEXT_FALLBACK_*` 的命名来自既有文本兜底配置，但在图文内容提取和风格提示词提取中表示指定的 OpenAI 兼容 VL 主通道。

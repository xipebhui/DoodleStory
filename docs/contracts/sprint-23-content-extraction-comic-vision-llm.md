# Sprint 23 合同：内容提取漫画逐页识别与二次 LLM 整理

后续 Sprint 25 已取代本合同中的逐张视觉调用与二次 LLM 整理方案；当前实现以 Sprint 25 的整组图片顺序理解为准。

## 目标

将内容提取的图文图片处理从本地 OCR 调整为 SiliconFlow 视觉理解逐页提取漫画内容，并在图片识别后增加一次 SiliconFlow 文本 LLM 整理步骤，最终结果展示在详情弹窗的 `内容提取` 区域。

## 范围内

- 图文图片内容提取改为按图片顺序逐张调用 `SILICONFLOW_VISION_MODEL`。
- 图片识别提示词改为用户指定的漫画逐页完整提取要求，覆盖旁白、对话、内心 OS、画面描述和分格信息。
- 每张图片的视觉识别原始结果继续写入对应 `content_extraction_media.extracted_text`，便于排查。
- 全部图片识别结果合并后，调用 `SILICONFLOW_MODEL` 做二次整理。
- 二次 LLM 的系统提示词使用同一段漫画逐页完整提取要求。
- 二次 LLM 输出写入 `content_extractions.extracted_text`，前端详情弹窗的主结果区展示该字段。
- 前端内容提取页面的说明文案从“本地 OCR/提取文案”调整为“逐页识别漫画内容/内容提取”。
- 更新 `docs/spec.md`、`docs/design/content-extraction.md` 和 `docs/progress.md`。

## 范围外

- 不新增数据库字段记录二次 LLM 模型名。
- 不改变视频音频转写链路。
- 不改变图文故事总结字段和展示结构。
- 不引入本地 OCR 或其他视觉识别兜底。
- 不跳过识别失败的图片。
- 不新增外部队列、复杂状态机或新的环境变量。

## 完成标准

- 图文内容提取先逐张调用视觉模型，再调用文本 LLM，最终 `extracted_text` 为二次整理结果。
- 任意图片识别失败或二次 LLM 失败时，请求明确失败，不返回占位结果。
- 详情弹窗的 `内容提取` 区域展示最终结果。
- `backend/.venv/bin/python -m compileall backend/app`、`npm run build --prefix frontend`、`git diff --check` 和 `./scripts/check.sh` 通过，或在进度记录中说明未验证项。

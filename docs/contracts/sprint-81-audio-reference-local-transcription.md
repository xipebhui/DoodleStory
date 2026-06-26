# Sprint 81 合同：音频参考本地转写创建流程

## 目标

优化音频管理创建流程：用户上传参考音频后，前端自动调用后端本地 Whisper 转写参考文本；转写完成前不允许保存音频参考。音频参考创建时必须保存真实转写文本，避免后续 SiliconFlow 注册自定义音色时因为缺少参考文本失败。

## 背景

SiliconFlow `/uploads/audio/voice` 注册自定义音色需要参考音频对应文本。Sprint 80 已在视频任务 worker 中明确校验缺少参考文本会失败，但 Sprint 79 的音频管理 UI 仍允许用户手动留空参考文本，导致视频任务在音频生成阶段失败。

## 范围内

- 新增后端本地 Whisper 转写服务，默认使用最小模型。
- 新增音频参考转写 API：上传音频文件后返回转写文本。
- 转写结果必须统一转换为简体中文后再返回和保存。
- 音频参考创建 API 要求 `reference_text` 非空。
- 前端上传音频文件后自动转写，转写中禁用保存。
- 前端保存时只提交名称、描述、自动转写文本和音频文件。
- 前端不再暴露 Provider、模型、音色名等非必填高级字段。
- 更新规格和进度文档。

## 范围外

- 不做云端转写兜底。
- 不做用户手动编辑转写文本。
- 不做转写任务持久化、后台队列或取消。
- 不做音频裁剪、降噪或多语言手动选择。
- 不做已有缺少参考文本音频的批量修复。

## 完成标准

- 用户选择音频文件后，页面显示本地转写中状态。
- 转写失败时不能保存，错误信息可见。
- 转写成功后保存按钮可用，保存的音频参考包含 `reference_text`。
- 创建接口直接收到空 `reference_text` 时明确拒绝。
- 后端单测、编译、前端构建和全量检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

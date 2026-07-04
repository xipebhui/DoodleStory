# Sprint 87 合同：视频分辨率跟随画风比例

## 目标

修复最终图文视频统一按 `9:16` 输出的问题，让视频任务提交给图文视频服务的 episode resolution 跟随上游图片任务的 `style_aspect_ratio_snapshot`。

## 范围内

- 视频 episode 构建时读取上游图片任务的风格比例快照。
- 根据现有视频默认长边配置计算对应宽高，默认 `9:16` 仍输出 `1080x1920`，`16:9` 输出 `1920x1080`。
- 无法解析风格比例时明确失败，不静默回退到默认比例。
- 更新规格、进度和回归测试。

## 范围外

- 不改变图片生成比例、图片 Provider 参数或风格管理。
- 不改变图文视频服务协议字段名。
- 不重跑或回写已有视频任务。
- 不新增比例兜底、自动裁剪或补边策略。

## 完成标准

- 视频任务 episode 的 `resolution.width/height` 与上游图片任务风格比例一致。
- 已有 `9:16` 视频任务输出尺寸保持不变。
- 相关后端测试、编译检查和仓库检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_task_worker
backend/.venv/bin/python -m compileall backend/app
git diff --check
./scripts/check.sh
```

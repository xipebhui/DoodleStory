# Sprint 82 合同：音频参考速度、编辑与测试试听

## 目标

补齐音频管理的基础可用能力：音频参考可以设置产出语速；用户可以编辑名称、描述和语速；用户可以输入测试文本并用该音频参考生成一段试听音频；音频列表展示更紧凑，避免原生音频长条占据过多空间。

## 背景

Sprint 81 已经让音频参考上传时自动本地转写参考文本，解决 SiliconFlow 自定义音色注册缺少参考文本的问题。下一步需要让用户在音频库内验证音色和语速，并把语速作为后续视频任务生成旁白音频的稳定配置。

## 范围内

- `audio_references` 新增 `speech_speed`，默认 `1.0`，限制 `0.5 - 2.0`。
- `video_tasks` 新增 `voice_speed_snapshot`，创建视频任务时从音频参考快照语速。
- 视频任务生成旁白音频时使用 `voice_speed_snapshot`，而不是全局默认速度。
- 音频参考创建时支持设置语速。
- 音频参考编辑只允许更新名称、描述和语速，不允许替换参考音频文件、参考文本、Provider、模型或音色名。
- 音频参考测试接口接收测试文本，使用该音频参考注册/复用 voice，并按语速生成试听音频流。
- 前端音频管理支持创建语速、编辑语速、输入测试文本试听。
- 前端音频列表改成紧凑展示，不常驻长条原生播放器。

## 范围外

- 不保存测试试听音频资产。
- 不做测试历史记录。
- 不做参考音频文件替换。
- 不做测试文本模板管理。
- 不做多 Provider 或模型选择 UI。

## 完成标准

- 新建音频参考时能设置语速。
- 编辑音频参考时只能修改名称、描述和语速。
- 测试音频参考时，输入文本后能生成可播放音频。
- 视频任务旁白音频生成使用创建任务时快照的语速。
- 相关单测、迁移、前端构建和全量检查通过，或未运行项有明确说明。

## 验证

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_video_audio_tasks backend.tests.test_video_task_worker
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

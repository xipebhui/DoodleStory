# Sprint 50 合同：抖音样本 Skill 复用现有 VL 链路

## 目标

完善 `douyin-hot-sample-research` Skill，把下载后图片理解从“另行安排 VL 模型”的泛化建议，改为复用 DoodleStory 当前内容提取中的视觉模型链路，并明确轻量首尾页判断与全量故事文档提取的边界。

## 范围内

- 更新 Skill，说明 DoodleStory 已有 `extract_ordered_gallery_comic_content`、`apply_content_text_extraction` 和 `parse_extracted_storyboard` 链路。
- 增加 `preview_vl` 与 `full_story_document` 两种 VL 使用范围。
- 明确只看开头、结尾或中段转折时，只传对应图片窗口，不做全量故事提取。
- 明确只有样本被判定值得进入实验或任务创建时，才走完整图集的故事文档提取。
- 更新样本字段参考，增加 VL 范围、输入页码、结果类型、是否需要全量提取等记录字段。
- 更新 `docs/progress.md`。

## 范围外

- 不修改后端内容提取代码。
- 不新增 VL provider 或第二套图片理解实现。
- 不改 `douyin-downloader` 或 `douyin-import-service`。
- 不实现新的 API、定时任务或批量采集编排。

## 完成标准

- Skill 能明确指导后续 agent 使用现有 DoodleStory VL，而不是建议用户单独安排一套模型。
- Skill 能区分研究阶段的首尾页抽检和最终故事文档提取。
- 字段参考能记录 VL 输入范围和产物类型。
- 相关文档与 skill 校验通过。

## 验证

- 使用 `quick_validate.py` 校验 skill。
- 运行 `git diff --check`。
- 运行 `./scripts/check.sh` 或说明未运行原因。

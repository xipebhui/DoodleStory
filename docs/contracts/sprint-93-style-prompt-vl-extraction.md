# Sprint 93 合同：风格提示词多图 VL 提取

## Goal

降低风格创建和编辑时手写风格提示词的成本：用户提供至少 3 张风格参考图后，系统使用 Gemini VL 提取这些图片的共同视觉风格，并把结构化风格提示词填回风格表单供用户继续编辑和保存。

## In Scope

- 新增临时上传图片提取风格提示词接口，用于新建风格时在保存前从待上传参考图提取。
- 新增已保存风格参考图提取接口，用于编辑风格时从当前参考图提取。
- 两个入口都要求至少 3 张真实 PNG、JPEG 或 WebP 图片。
- VL 调用使用 LIO/OpenAI 兼容通道中的 Gemini 模型配置，不使用 SiliconFlow VL 兜底。
- 提取提示词使用用户指定的艺术评论家结构，并要求输出包含：
  - `【核心调性】`
  - `【色彩与光影特征】`
  - `【线条与肌理特征】`
  - `【构图与透视特征】`
  - `【风格迁移测试】`
- 前端风格抽屉新增 `从参考图提取` 辅助按钮，提取结果只填入 `style_prompt` 表单字段，不自动保存。

## Out of Scope

- 不在后台自动为所有历史风格补全提示词。
- 不新增风格提示词版本历史、审核流或提取任务持久化。
- 不对 Gemini VL 失败做模型降级、兼容回退或静默忽略。
- 不改变正式任务、风格测试或生图 Provider 的风格参考方式。

## Deliverables

- 后端 Gemini VL 风格提示词提取服务。
- 风格 API 提取入口。
- 前端风格抽屉交互更新。
- 单元测试覆盖至少 3 张图校验和已保存参考图调用顺序。
- 规格和进度记录更新。

## Done Means

- 用户在新建风格时选择至少 3 张参考图，可点击按钮生成结构化风格提示词。
- 用户在编辑风格时已有至少 3 张参考图，可点击按钮重新提取并覆盖表单中的提示词草稿。
- 少于 3 张参考图时前后端都明确提示，不调用 VL。
- Gemini VL 调用失败时返回明确错误，不自动切换到其它 VL 模型。

## Verification

```bash
PYTHONPATH=backend backend/.venv/bin/python -m unittest backend.tests.test_style_delete
backend/.venv/bin/python -m compileall backend/app
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

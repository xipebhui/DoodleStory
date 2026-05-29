# DoodleStory

[中文](README.zh-CN.md) | [English](README.en.md)

DoodleStory 是一个文本转图片的故事生成项目。它会把用户输入的原始文本切分成一组画面片段，再结合风格库、风格提示词和风格内配置的图片模型生成多张图片。

## 产品形态

- 用户系统：支持邮箱注册、登录、退出和找回密码；普通用户只能看到自己的任务，Admin 可以看到全部任务。
- 风格库：管理图片风格、参考图片、风格基础信息和风格提示词；provider、model 和默认参数由后台生成配置维护，不暴露给普通用户。
- 风格测试：输入一段测试文本，将测试文本和风格提示词组合后，用风格绑定的模型生成测试图，方便调试风格。
- 生成任务：用户输入原始文本，不改写原文；选择自动判断图片数量或固定图片数量；选择风格后提交生成。
- 结果处理：生成后支持图片点击放大，以及一键批量下载所有图片。

## Codex Harness

本仓库使用 `codex-project-template` 的 Codex 开发 harness，并已结合 DoodleStory 的业务进行适配。

开始较大实现工作前，请先阅读：

- [项目规格](docs/spec.md)
- [进度记录](docs/progress.md)
- [当前 Sprint 合同](docs/contracts/sprint-01-product-design.md)
- [产品设计](docs/design/README.md)
- [开发规范](docs/standards/)
- [参考：Harness design: Building long-running applications with LLMs](docs/references/harness-design-long-running-apps.md)

# Sprint 149：grokcli 显式生图 Provider

## Status

Complete。该合同作为传统生图链路的独立小切片交付，不修改或扩展 Durable Runtime 合同。

## 目标

把 `ele-yufo/grokcli` 作为第三种真实生图 Provider 接入当前图片服务，并允许 Native Agent
用户在对话提示词中明确指定 `Grok`、`QY` 或 `xgapi`。未指定时使用系统 `IMAGE_PROVIDER`；
任一 Provider 失败后都不得自动切换到另一个 Provider。

## 范围内

- 固定安装已验证的 `grokcli` commit，并通过其 OAuth 凭据调用订阅生图能力。
- 无参考图调用 `grokcli image`；1–3 张公网参考图调用 `grokcli image-edit`。
- 支持 grokcli 已声明的比例和 `1k` / `2k` 分辨率。
- CLI 输出在独立临时目录中生成，按真实图片 magic bytes 识别格式，保存后删除临时文件。
- 只对 grokcli 的网络/超时退出码做同 Provider 有界重试；认证、额度、内容策略和参数错误不重试。
- Native Agent `generate_image` 增加 `provider=default|grok|qy|xgapi`，并在图片、Tool 事件和 API
  中保存/返回实际 Provider。
- `IMAGE_PROVIDER=grok` 时，传统任务链路也可整体使用 Grok。
- Docker 镜像安装 grokcli，生产凭据目录使用 `/app/data/grokcli` 持久化。

## 范围外

- 不从自然语言在后端做关键词路由；Provider 选择由 Agent Tool 的结构化参数表达。
- 不把 Grok 作为 QY 或 xgapi 的失败兜底，也不反向兜底。
- 不在普通任务创建 UI 增加 Provider 控件；普通任务仍由部署级 `IMAGE_PROVIDER` 决定。
- 不迁移历史任务图片；历史 Native Agent 图片的 Provider 记为当时默认的 `qy`。
- 不保存、复制或提交 OAuth token。

## 验收标准

- 本机 `grokcli login` 和真实中文 3:4 生图成功，记录耗时、真实尺寸与格式。
- `provider=grok` 只调用 grokcli；`provider=qy|xgapi` 保持现有 adapter；`default` 使用配置值。
- Grok 有参考图时只允许 1–3 张公网 HTTP(S) URL，超限或非法 URL 明确失败。
- grokcli 未安装、未认证、超时、配额或内容拦截均产生明确错误，不静默切换 Provider。
- Native Agent API 和页面展示每张图片的实际 Provider。
- 定向测试、空库迁移、前端构建、`git diff --check` 和 `./scripts/check.sh` 通过。

## 验收结果

- 浏览器 OAuth 登录成功，账号状态有效；真实 CLI 3:4 生图约 7.5 秒，864×1152。
- 通过 DoodleStory adapter 真实验证纯文本生图约 7.36 秒、单参考图 image-edit 约 12.76 秒，
  两者均返回 864×1152 JPEG，临时文件自动清理。
- 51 项定向测试通过；`./scripts/check.sh` 通过 346 项后端测试、空库全量迁移、14 项前端
  测试、前端生产构建、Remotion TypeScript 和 5 项模板测试。

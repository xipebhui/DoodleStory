# Sprint 204：Paynes Creek 已验收成片正式登记与 YouTube 发布

状态：Implementation ready / awaiting clean-source real execution（用户已于 2026-08-15 明确授权选择低发布量频道并真实发布）

## Goal

把 Sprint 203 已验收的 Paynes Creek 英文无页脚成片，通过仓库既有的对象存储、
`NativeAgentVideo`、`PublishableVideo` 和 `YoutubePublishTask` 链路登记并提交到历史发布量最少的
正常 YouTube 频道，保留从本地验收记录到远程任务和 YouTube Video ID 的可审计关系。

## In scope

1. 读取发布服务的 17 个频道，并按“`status=normal`、已发布视频数量升序、Channel ID 升序”确定唯一目标。
2. 目标固定为本轮只读统计最少的 `Strandburg Behler`：
   `UCjOzKTQ7NzrNtkBbBYoCX_w`，统计时已有 40 条远程视频。
3. 新增一个有显式 `--preflight` / `--execute` 边界的一次性导入发布脚本：
   - 复验 Sprint 203 acceptance JSON、最终 MP4 路径、SHA-256、大小、时长、宽高、fps 和 codec；
   - 使用现有 `save_binary_file()` 把同一 MP4 写入当前对象存储；
   - 创建或幂等复用 `FileAsset`、明确标记为本地验收导入的 `NativeAgentConversation / Run / Video`；
   - 创建或幂等复用 `review_status=approved`、`contains_synthetic_media=true` 的 `PublishableVideo`；
   - 同步目标频道到本地，并通过现有 `create_youtube_publish_task()` 创建真实远程任务。
4. 发布元数据固定为：
   - 标题：`No Shipping Records: How Did Maya Salt Travel Inland?`
   - 可见性：`public`
   - 儿童内容：否；付费植入：否；合成媒体：是；通知订阅者：关闭；立即执行。
   - 描述和标签使用本合同对应脚本中冻结的英文考古说明，不扩大原视频事实结论。
5. 使用稳定幂等键；外部创建请求只允许一次，不自动重试，不因结果未知创建第二个任务。
6. 通过现有单任务状态接口手动获取结果；成功时记录 `youtube_video_id` 和 YouTube URL。
7. 写入不包含密钥或签名 URL 的执行报告，并更新 `docs/progress.md`。

## Out of scope

- 不重新生成、重编码或修改视频、旁白、字幕、图片、标题画面和证据等级。
- 不实施 Sprint 191 的通用 Evidence Pack / 四维不可变验收产品功能；本轮只接受 Sprint 203 的特定验收记录。
- 不新增数据库表、迁移、前端入口或第二套发布 HTTP 客户端。
- 不更换目标频道，不因频道题材与本片不一致而自动选择其他频道。
- 不开启订阅者通知，不自动轮询，不自动重试发布，不重复创建远程任务。
- 不修改或删除频道现有视频、账号资料和可见性。

## Done means

- 预检证明最终 MP4 bytes 与 Sprint 203 acceptance 完全一致，目标频道仍正常且仍是远程视频数最少者。
- 同一视频重复运行只复用既有本地资产、视频、可发布记录和发布任务，不产生第二次远程创建调用。
- OSS 公网 URL 可由发布平台读取；本地链路包含 `FileAsset → NativeAgentVideo → PublishableVideo → YoutubePublishTask`。
- 真实发布任务使用固定频道、标题、`public`、合成媒体披露和关闭通知参数。
- 远程任务进入成功终态并保存 YouTube Video ID / URL；若远程明确失败，则保存明确错误且不重建任务。
- 执行报告记录源文件 hash、目标频道、各本地 ID、远程任务 ID、终态和调用次数，不记录凭据或完整 OSS URL。

## Verification

```powershell
& backend/.venv/Scripts/python.exe -m unittest backend.tests.test_publish_reviewed_local_video
& backend/.venv/Scripts/python.exe -m compileall scripts backend/app
& backend/.venv/Scripts/python.exe scripts/publish_reviewed_local_video.py --preflight ...
./scripts/check.sh
git diff --check
```

真实执行前还必须确认：Git 来源 commit 与参数一致、worktree 无未提交修改、目标文件 hash 一致、
对象存储和发布服务配置完整、目标频道状态正常、同一视频和频道不存在既有发布任务。

## Handoff

- 成功后交付 YouTube URL、目标频道、远程任务 ID、本地追踪 ID 和审计报告路径。
- 如果远程任务仍在 `pending` / `running`，继续使用既有任务 ID 手动获取状态；不得再次提交。
- 本轮形成的特定导入脚本只服务已存在且有冻结 acceptance 的本地成片，不把任意本机 MP4 自动批准为可发布视频。

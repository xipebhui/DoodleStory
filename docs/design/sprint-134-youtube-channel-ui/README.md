# Sprint 134 YouTube 频道 UI 视觉基准

实施必须以当前 DoodleStory Agent Studio 为视觉事实来源，并对齐以下两张用户确认稿：

1. `01-channel-list.png`：频道账号列表、筛选、同步入口和 Agent Studio 导航。
2. `02-channel-publish-tasks.png`：频道详情、扁平数据摘要、Tab 和发布任务表格。

## Visual thesis

安静、克制的深色编辑工作台：墨黑背景、分层中性表面、偏白正文与单一暖橙操作色。

## Content plan

- 频道列表负责查找、比较、同步和进入详情。
- 频道详情负责理解一个频道，并按账号定义、发布任务、已发布视频、对标账号组织信息。
- 数据摘要使用一个扁平分隔带，不拆成彩色指标卡。

## Interaction thesis

- 列表同步和详情同步提供短促 loading 与结果反馈，不自动轮询。
- 行 hover、Tab 切换和详情进入使用当前产品已有的轻量颜色/边框过渡。
- 错误在对应频道或同步区域原位展示，不使用全屏阻塞。

## Hard constraints

- 复用现有 `agent-module-shell`、侧栏比例、字体层级、表格密度和按钮体系。
- 频道账号作为 Agent Studio 一级导航，仅 Admin 可见。
- 不使用白色卡片、蓝色主按钮、彩色 dashboard 卡片、营销横幅或右侧聊天抽屉。
- 不把两张稿中的演示账号、指标或任务当作 Mock 写入正式代码。

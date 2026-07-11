# Sprint 101 合同：恢复最后一张真人图片入口

## Goal

在前端创建图文任务时重新开放 `最后一张真人图片` 选项，让用户可以显式选择最后一个 panel 是否按真实摄影/真人自拍质感生成。

## In Scope

- 创建任务弹窗展示默认关闭的 `最后一张真人图片` checkbox。
- 普通图文任务创建时读取该 checkbox，并把 `last_panel_real_photo` 传给后端。
- DY 爆款复刻创建参数也读取同一个 checkbox，内容提取成功后自动创建的生成任务沿用用户选择。
- `去掉画面文字` 选项继续隐藏并固定为关闭。
- 更新规格、合同和进度记录。

## Out of Scope

- 不改后端 `last_panel_real_photo` 的生成逻辑。
- 不恢复 `去掉画面文字` 前端入口。
- 不改变默认行为；未勾选时仍为 `false`。

## Deliverables

- 前端创建弹窗入口和提交参数。
- 项目规格与进度记录同步。

## Done Means

- 用户创建任务时能看到 `最后一张真人图片` 开关。
- 勾选后请求 payload 中 `last_panel_real_photo=true`。
- 未勾选时请求 payload 中 `last_panel_real_photo=false`。
- `remove_image_text` 仍不暴露给普通创建入口。

## Verification

```bash
npm run build --prefix frontend
git diff --check
./scripts/check.sh
```

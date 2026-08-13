---
name: DoodleStory YouTube Research Boards
description: Evidence-led local reading surfaces for turning research claims into auditable media plans.
colors:
  marine-ink: "#102a33"
  marine-ink-soft: "#1f3b43"
  salt-paper: "#f4f6f1"
  sediment-bench: "#d8e4e5"
  sediment-deep: "#bfd1d2"
  registration-line: "#8ba5a7"
  direct-evidence: "#176c69"
  direct-evidence-pale: "#c5dfdc"
  reconstruction: "#a45f1c"
  reconstruction-pale: "#f0d4ad"
  blocked-claim: "#91342d"
  blocked-claim-pale: "#ebc4be"
typography:
  headline:
    fontFamily: "Segoe UI, Microsoft YaHei, PingFang SC, system-ui, sans-serif"
    fontSize: "clamp(2.8rem, 6.5vw, 6rem)"
    fontWeight: 700
    lineHeight: 0.98
    letterSpacing: "-0.04em"
  body:
    fontFamily: "Segoe UI, Microsoft YaHei, PingFang SC, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.68
  measure:
    fontFamily: "Cascadia Mono, SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: "0.76rem"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sharp: "0"
  chip: "999px"
spacing:
  xs: "8px"
  sm: "14px"
  md: "24px"
  lg: "48px"
components:
  evidence-chip:
    textColor: "{colors.direct-evidence}"
    rounded: "{rounded.chip}"
    padding: "3px 8px"
  frame-aperture:
    backgroundColor: "{colors.salt-paper}"
    textColor: "{colors.marine-ink}"
    rounded: "{rounded.sharp}"
  shot-ledger:
    backgroundColor: "{colors.sediment-bench}"
    textColor: "{colors.marine-ink}"
    rounded: "{rounded.sharp}"
---

# Design System: DoodleStory YouTube Research Boards

## Overview

**Creative North Star: "水下考古证据台"**

YouTube 研究板像研究人员把器物、柱位、地图和解释限制铺在冷光证据台上，同时用影片接触印样组织时间。
它服务的是阅读和审核：证据强度、镜头顺序与当前 Gate 必须先于气氛和装饰被看见。

页面不模仿古代现场，也不使用羊皮纸式“历史感”。视觉身份来自连续时间尺、清楚的登记线、平面证据几何
和严格的青绿 / 琥珀 / 红色语义，而不是通用仪表盘卡片。

**Key Characteristics:**

- 冷色实验台底面承载高密度中文阅读。
- 直接证据、支持性解释和禁止补全拥有稳定的语义颜色。
- 镜头是连续登记行，不是同尺寸卡片网格。
- 比例尺、时间码、字幕安全区和 Gate 都以真实制作约束出现。
- 页面自身无第三方图片依赖；几何图只解释证据关系，不伪装成历史复原。

## Colors

调色采用受控的全角色色板：深海墨线建立骨架，沉积蓝灰提供阅读底面，青绿只表示直接证据，矿物琥珀
表示重建或解释，红色只标记不能补全的主张。

### Primary

- **深海墨线**：大面积首屏、主要文字、轮廓和登记结构。
- **直接证据青绿**：A 级证据、稳定连接和通过状态。

### Secondary

- **矿物重建琥珀**：B 级解释、可能性、断续路线和有条件状态。
- **Gate 红**：禁止项、不通过状态和字幕禁区；不得成为历史对象的装饰色。

### Neutral

- **沉积证据台**：页面底面和连续镜头工作区。
- **盐白纸面**：16:9 画面孔、密集信息和高对比留白。
- **登记线**：分隔镜头、表格和时间带，不制造卡片阴影。

**The Evidence Color Rule.** 同一种颜色在所有研究板中保持同一种证据强度；不得为了页面更活泼而随机换色。

## Typography

**Headline Font:** 中文 Web 工作台字族

**Body Font:** 同一中文 Web 工作台字族

**Label/Mono Font:** Cascadia Mono 优先的等宽测量字族

**Character:** 这是 Read 模式的技术工作台。标题通过尺度与紧凑行高获得权重，不引入与正文冲突的仿古
展示字体；等宽字只用于时间码、Scene ID、来源 ID 和运动预设。

### Hierarchy

- **Headline**（700，流体尺度，0.98 行高）：首屏文档标题；中文与英文保持同一工作台语气。
- **Section heading**（700，流体尺度，约 1.05 行高）：划分视觉规格、运行 Gate 与预检。
- **Shot title**（700，流体尺度，约 1.18 行高）：一镜的唯一主张，控制在约 23 个中文字符宽。
- **Body**（400，16px，1.68 行高）：事实边界与制作说明，正文段落不超过约 68ch。
- **Measure**（400，约 0.76rem）：只承载时间、秒数、ID 和合法预设。

**The Measurement Rule.** 等宽体表示可测量或可追溯数据，不能当作“技术感”装饰整段正文。

## Layout

首屏使用不对称两列：内容命题占主要宽度，总体 Gate 作为窄列与其并置；五段机制链和 138 秒时间带横贯
整个底部。正文在宽屏采用 250px 证据图例栏加连续镜头登记区，单镜固定为时间戳、16:9 画面孔和主张
说明三列。镜头高度由内容决定，不强求等高。

1120px 以下移除图例栏粘性并压缩镜头列；820px 以下改为单列镜头、两列时间段和逐项运行账本；520px
以下所有色彩样本与状态区改为单列。任何断点都不允许页面级横向滚动。

主要间距来自 8 / 14 / 24 / 48px 级差。章节用 5px 顶部登记线与大段留白分隔，镜头之间只用 1px 线，
避免将每个信息块包成独立卡片。

## Elevation & Depth

该系统默认完全平面，不使用卡片阴影。深度由大面积墨色首屏、盐白画面孔、沉积底面和边界线的层级产生；
研究证据不应漂浮在装饰性阴影或玻璃层中。

**The Flat Evidence Rule.** 阴影不能替代证据分组；如果一个区域需要层级，先用底面、线和空间关系表达。

## Shapes

画面孔、镜头登记行、表格和状态区使用直角。圆角只保留给短小、非交互的证据等级标签，且固定为完整
胶囊形。16:9 画面孔两侧有黑色登记条；时间带与比例尺采用精确直线、断线和节点，不使用插画式手绘边缘。

## Components

### Evidence chips

- **Shape:** 小型完整胶囊，仅包裹 `A 直接证据`、`B 解释` 等短标签。
- **Color:** 标签文字和边框复用对应证据颜色，底面保持透明。
- **State:** 它是阅读标签，不伪装成可点击筛选器。

### Shot ledger

- **Structure:** 时间戳、16:9 几何孔、唯一主张与允许 / 禁止边界三部分。
- **Border:** 顶部证据色 5px，行间登记线 1px；无外层卡片、无阴影。
- **Responsive:** 移动端按时间戳、画面、主张顺序垂直展开。

### Frame aperture

- **Shape:** 固定 16:9、直角、1px 登记线，两侧 6px 墨色定位条。
- **Content:** 只放可精确描述的 SVG 几何；图片原生历史场景必须使用真实或生成的栅格资产，不能用 SVG 假画。
- **Safety:** 核心对象保持在中央 84% 与上方 70% 内。

### Evidence bounds

- **Structure:** `允许` 与 `禁止` 两格共边，禁止格使用浅红底；移动端上下堆叠。
- **Copy:** 每格只记录最容易造成事实漂移的 1–3 个约束。

### Runtime ledger

- **Desktop:** 四列比较要求、当前证据、Gate 与下一动作。
- **Mobile:** 每个要求改成四行标签—值账本，不让用户横向拖动小字号表格。

## Do's and Don'ts

### Do:

- **Do** 让每一镜只有一个主张，并把 F / S / R 来源 ID 放在同一阅读路径内。
- **Do** 用线型、断点、节点和实线 / 虚线差异表达直接证据与解释边界。
- **Do** 在移动端保持时间、画面、主张、边界和运动预设的原始顺序。
- **Do** 为键盘焦点提供高对比轮廓，并让跳转链接只在 `focus-visible` 时出现。

### Don't:

- **Don't** 使用仿旧纸张、宫殿金色、电影海报光影或装饰性民族纹样制造历史感。
- **Don't** 把镜头、状态或来源改成重复的圆角卡片网格。
- **Don't** 用颜色单独传达 Gate；始终同时写明直接证据、重建、有条件或不通过。
- **Don't** 用生成模型产生地图文字、证据标签或历史细节来替代语义化 HTML 与可回查来源。

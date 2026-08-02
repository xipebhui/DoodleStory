---
title: "YouTube 频道管理 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/youtube-channels/"
requestedUrl: "https://video.inboxlinks.top/api-docs/youtube-channels/"
siteName: "Video API 文档"
summary: "YouTube 频道的查询、修改与横幅设置"
adapter: "generic"
capturedAt: "2026-08-02T03:24:40.503Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## YouTube 频道管理

这一组接口用于管理系统内已绑定的 YouTube 频道信息（读取/修改/设置横幅）。YouTube 账号就是频道，它们一一对应，所以没有单独的账号接口。

常见用途：

- 获取可用频道列表，让用户选择要上传到哪个频道
- 修改频道展示信息（取决于系统支持字段）
- 上传/更新频道横幅图片
- 触发一次实时同步，刷新频道统计数据

---

## 获取所有 YouTube 频道

- **URL** ： `{服务器域名}/api/youtube/channel/v1/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/channel/v1/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["channel_id", "asc"]],
    "limit": 50
  }'
```

### YouTube 频道对象定义

```ts
type ChannelLink = {
  title: string; // 链接标题
  url: string; // 链接 URL
};

type YoutubeChannel = {
  youtube_account_id: string; // YouTube 账号 ID
  channel_id: string; // YouTube 频道 ID
  title: string | null; // 频道标题
  handle: string | null; // 频道句柄（@ 后面的部分）
  description: string | null; // 频道描述
  /** @deprecated 已停止更新（overview 接口升级后不再产出该字符串字段），改用 total_subscribers */
  subscribers: string | null;
  /** @deprecated 已停止更新（overview 接口升级后不再产出该字符串字段），改用 total_views */
  views: string | null;
  /** @deprecated 已停止更新（overview 接口升级后不再产出该字符串字段），改用 total_watch_time_hours */
  watch_time_hours: string | null;
  /** @deprecated 已停止更新，上游 overview 接口已不再返回该字段，无替代字段 */
  estimated_revenue: string | null;
  remark: string | null; // 备注
  email: string; // 对应的 Google 邮箱
  status: 'normal' | 'manual' | 'banned' | 'unknown'; // 账号状态，见下方取值说明
  last_sync_at: string | null; // 最后一次同步尝试的时间（成功/失败均更新）
  last_sync_error: string | null; // 最后一次同步错误（成功时为 null）
  last_sync_success_at: string | null; // 最后一次「成功」同步的时间（仅成功时更新）
  links: ChannelLink[]; // 频道外部链接
  avatar_url: string | null; // 频道头像图片 URL
  banner_url: string | null; // 频道横幅图片 URL
  // ── 以下字段来自频道最新汇总数据（left join，字段名与 /analytics/latest 接口一致）──
  total_subscribers: number | null; // 总订阅数
  total_views: number | null; // 总观看数
  total_watch_time_hours: number | null; // 总观看时长（小时，整数）
  total_subscribers_28d: number | null; // 近 28 天订阅数变化
  total_views_28d: number | null; // 近 28 天观看数
  total_watch_time_hours_28d: number | null; // 近 28 天观看时长（小时，整数）
  local_user_id: string | null; // 本地用户 ID，管理此频道的用户
  local_user_email: string | null; // 本地用户邮箱
};
```

`status` 是一个文本枚举（数据库以 TEXT 存储，不是数字），取值及含义：

| 取值 | 含义 |
| --- | --- |
| `normal` | 正常/可用 |
| `manual` | 需要人工介入处理（如登录异常等） |
| `banned` | 账号已被封禁（例如上传视频时检测到账号被封禁，系统会自动把状态置为该值） |
| `unknown` | 状态未知，尚未成功同步到最新账号状态 |

### 字段分组说明

| 分组 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| **基本信息** | `youtube_account_id` | `string` | YouTube 账号 ID |
|  | `channel_id` | `string` | YouTube 频道 ID |
|  | `title` | `string \| null` | 频道标题 |
|  | `handle` | `string \| null` | 频道句柄（@ 后面的部分） |
|  | `description` | `string \| null` | 频道描述 |
|  | `remark` | `string \| null` | 备注 |
|  | `email` | `string` | 对应的 Google 邮箱 |
|  | `status` | `'normal' \| 'manual' \| 'banned' \| 'unknown'` | 账号状态，见上方取值表 |
|  | `links` | `ChannelLink[]` | 频道外部链接（ `{ title, url }` 数组） |
|  | `avatar_url` | `string \| null` | 频道头像图片 URL |
|  | `banner_url` | `string \| null` | 频道横幅图片 URL，即使频道未自行设置横幅，也可能返回 YouTube 的系统默认横幅 URL，不代表频道一定已自定义横幅 |
| **已弃用字段** | `subscribers` | `string \| null` | @deprecated，改用 `total_subscribers` |
|  | `views` | `string \| null` | @deprecated，改用 `total_views` |
|  | `watch_time_hours` | `string \| null` | @deprecated，改用 `total_watch_time_hours` |
|  | `estimated_revenue` | `string \| null` | @deprecated，无替代字段 |
| **同步状态** | `last_sync_at` | `string \| null` | 最后一次同步尝试的时间（成功/失败均更新） |
|  | `last_sync_error` | `string \| null` | 最后一次同步错误（成功时为 `null` ） |
|  | `last_sync_success_at` | `string \| null` | 最后一次「成功」同步的时间（仅成功时更新） |
| **统计数据** （left join `youtube_channel_analytics_latest` ） | `total_subscribers` | `number \| null` | 总订阅数 |
|  | `total_views` | `number \| null` | 总观看数 |
|  | `total_watch_time_hours` | `number \| null` | 总观看时长（小时，整数） |
|  | `total_subscribers_28d` | `number \| null` | 近 28 天订阅数变化 |
|  | `total_views_28d` | `number \| null` | 近 28 天观看数 |
|  | `total_watch_time_hours_28d` | `number \| null` | 近 28 天观看时长（小时，整数） |
| **关联用户** | `local_user_id` | `string \| null` | 本地用户 ID，管理此频道的用户（未分配时为 `null` ） |
|  | `local_user_email` | `string \| null` | 本地用户邮箱（未分配时为 `null` ） |

### Response Body

`list` 接口返回通用的游标分页结构（与 [查找数据列表](https://video.inboxlinks.top/api-docs/crud/#%E6%9F%A5%E6%89%BE%E6%95%B0%E6%8D%AE%E5%88%97%E8%A1%A8) 一致）：

```ts
type ListChannelResponse = {
  datas: YoutubeChannel[]; // 本页频道数据
  total: number; // 符合条件的频道总数
  next: object | null; // 下一页游标，传入下次请求的 cursor 字段
  prev: object | null; // 上一页游标
};
```

---

## 查找单个频道详情

- **URL** ： `{服务器域名}/api/youtube/channel/v1/one`
- **Method** ： `GET`

通过 `channel_id` 查询单个频道详情，字段定义同上面的 `YoutubeChannel` 对象。

### Response Body

响应体直接是 `YoutubeChannel` 对象；若 `channel_id` 不存在，响应体为 `null` （HTTP 状态码仍为 `200` ）。

### curl 调用示例

```bash
curl -X GET 'https://video.inboxlinks.top/api/youtube/channel/v1/one?channel_id=CHANNEL_ID' \
  -H 'x-api-key: token'
```

---

## 获取 YPP 进度查询列表（YPP Milestone Progress List）

查询频道 YPP（YouTube Partner Program）里程碑进度（部分功能/全部功能）。

- **URL** ： `{服务器域名}/api/youtube/channel/v1/ypp/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

复用通用“ [查找数据列表](https://video.inboxlinks.top/api-docs/crud/#%E6%9F%A5%E6%89%BE%E6%95%B0%E6%8D%AE%E5%88%97%E8%A1%A8) “的分页查询结构（ `where/order/cursor/limit` ）。

### Response Body

```ts
type Progress = {
  now: number | null; // 当前进度数值
  now_str: string | null; // 当前进度字符串（格式化展示用）
  total: number | null; // 目标总数值
  total_str: string | null; // 目标总数字符串（格式化展示用）
  text: string | null; // 进度说明文本
  time: string | null; // 时间信息（如更新时间/预计达成时间等）
};

type OneMilestone = {
  subscribers: Progress; // 订阅者数里程碑进度（对象本身不为 null，内部字段可能为 null）
  watch_hours: Progress; // 观看时长（小时）里程碑进度
  views: Progress; // 观看次数里程碑进度
  uploads: Progress; // 上传数量里程碑进度
};

type MilestoneData = {
  partial: OneMilestone | null; // 开通部分功能 YPP 的里程碑数据
  full: OneMilestone | null; // 开通全部功能 YPP 的里程碑数据
};

type YppMilestoneView = {
  channel_id: string;
  last_sync_at: string | null; // 最后一次同步尝试的时间（成功/失败均更新）
  last_sync_error: string | null; // 最后一次同步错误（成功时为 null）
  last_sync_success_at: string | null; // 最后一次「成功」同步的时间（仅成功时更新）
  data: MilestoneData | null;
};
```

### 字段说明

| 类型 | 字段 | 类型 | 说明 |
| --- | --- | --- | --- |
| `Progress` | `now` | `number \| null` | 当前进度数值 |
|  | `now_str` | `string \| null` | 当前进度字符串（格式化展示用） |
|  | `total` | `number \| null` | 目标总数值 |
|  | `total_str` | `string \| null` | 目标总数字符串（格式化展示用） |
|  | `text` | `string \| null` | 进度说明文本 |
|  | `time` | `string \| null` | 时间信息（如更新时间/预计达成时间等） |
| `OneMilestone` | `subscribers` | `Progress` | 订阅者数里程碑进度，恒为对象（非 `null` ） |
|  | `watch_hours` | `Progress` | 观看时长（小时）里程碑进度，恒为对象 |
|  | `views` | `Progress` | 观看次数里程碑进度，恒为对象 |
|  | `uploads` | `Progress` | 上传数量里程碑进度，恒为对象 |
| `MilestoneData` | `partial` | `OneMilestone \| null` | 开通部分功能 YPP 的里程碑数据 |
|  | `full` | `OneMilestone \| null` | 开通全部功能 YPP 的里程碑数据 |
| `YppMilestoneView` | `channel_id` | `string` | YouTube 频道 ID |
|  | `last_sync_at` | `string \| null` | 最后一次同步尝试的时间（成功/失败均更新） |
|  | `last_sync_error` | `string \| null` | 最后一次同步错误（成功时为 `null` ） |
|  | `last_sync_success_at` | `string \| null` | 最后一次「成功」同步的时间（仅成功时更新） |
|  | `data` | `MilestoneData \| null` | 里程碑数据，见上方空值说明 |

`ypp/list` 同样返回通用游标分页结构： `{ datas: YppMilestoneView[]; total: number; next: object | null; prev: object | null }` 。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/channel/v1/ypp/list' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "where": null,
    "order": [["channel_id", "asc"]],
    "limit": 50
  }'
```

### 成功响应示例

```json
{
  "datas": [
    {
      "channel_id": "UCxxxxxxxxxxxxxxxx",
      "last_sync_at": "2026-01-01T12:00:00Z",
      "last_sync_error": null,
      "last_sync_success_at": "2026-01-01T12:00:00Z",
      "data": {
        "partial": {
          "subscribers": {
            "now": 120,
            "now_str": "120",
            "total": 500,
            "total_str": "500",
            "text": "订阅者进度（部分功能）",
            "time": "2026-01-01T12:00:00Z"
          },
          "watch_hours": {
            "now": 860,
            "now_str": "860 小时",
            "total": 3000,
            "total_str": "3,000 小时",
            "text": "观看时长进度（部分功能）",
            "time": "2026-01-01T12:00:00Z"
          },
          "views": {
            "now": null,
            "now_str": null,
            "total": null,
            "total_str": null,
            "text": null,
            "time": null
          },
          "uploads": {
            "now": null,
            "now_str": null,
            "total": null,
            "total_str": null,
            "text": null,
            "time": null
          }
        },
        "full": {
          "subscribers": {
            "now": 120,
            "now_str": "120",
            "total": 1000,
            "total_str": "1,000",
            "text": "订阅者进度（全部功能）",
            "time": "2026-01-01T12:00:00Z"
          },
          "watch_hours": {
            "now": 860,
            "now_str": "860 小时",
            "total": 4000,
            "total_str": "4,000 小时",
            "text": "观看时长进度（全部功能）",
            "time": "2026-01-01T12:00:00Z"
          },
          "views": {
            "now": null,
            "now_str": null,
            "total": null,
            "total_str": null,
            "text": null,
            "time": null
          },
          "uploads": {
            "now": null,
            "now_str": null,
            "total": null,
            "total_str": null,
            "text": null,
            "time": null
          }
        }
      }
    }
  ],
  "total": 1
}
```

---

## 修改 YouTube 频道信息

- **URL** ： `{服务器域名}/api/youtube/channel/v1/patch`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

```ts
interface ChannelPatch {
  handle: string; // 频道网址中 @ 后的部分
  title: string; // 频道标题
  description: string | null; // 频道描述
  remark: string | null; // 备注
  links: ChannelLink[]; // 频道链接
}

interface PatchRequest {
  ids: string[]; // channel_id 数组
  data: Partial<ChannelPatch>;
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `handle` | `string` | 频道网址中 @ 后的部分；修改频率受 YouTube 平台自身规则限制（如短期内多次修改），本接口不做本地频率校验，超限时以上游返回的错误为准 |
| `title` | `string` | 频道标题 |
| `description` | `string \| null` | 频道描述 |
| `remark` | `string \| null` | 备注（仅本系统内部使用，不会同步到 YouTube） |
| `links` | `ChannelLink[]` | 频道链接 |

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：一个 JSON 数字，表示本次实际修改的频道数量（即 `ids` 的长度），例如 `1` 。

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/channel/v1/patch' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "ids": ["UCxxxxxxxxxxxxxxxx"],
    "data": {
      "remark": "updated remark"
    }
  }'
```

---

## 设置频道横幅图片

设置 YouTube 频道横幅图片，推荐图片长宽比为 **17.7: 10** 。

- **URL** ： `{服务器域名}/api/youtube/channel/v1/update_banner`
- **Method** ： `POST`
- **Content-Type** ： `multipart/form-data`

### Query Parameters

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `channel_id` | string | 是 | YouTube 频道 ID |

### Form Data

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `image` | file | 是 | 横幅图片文件， **仅支持 JPG、PNG 格式，大小不超过 2MB** |

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### 错误响应

```json
{
  "errcode": "错误码",
  "error": "错误信息"
}
```

### 调用示例

```bash
curl -X POST \
  'https://video.inboxlinks.top/api/youtube/channel/v1/update_banner?channel_id=UCxxxxxxxxxxxxxxxx' \
  -H 'x-api-key: token' \
  -F 'image=@/path/to/banner.jpg'
```

---

## 设置频道头像

设置 YouTube 频道头像图片，用法与“设置频道横幅图片”完全一致。

- **URL** ： `{服务器域名}/api/youtube/channel/v1/update_avatar`
- **Method** ： `POST`
- **Content-Type** ： `multipart/form-data`

### Query Parameters

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `channel_id` | string | 是 | YouTube 频道 ID |

### Form Data

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `image` | file | 是 | 头像图片文件， **仅支持 JPG、PNG 格式，大小不超过 2MB** |

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### 错误响应

```json
{
  "errcode": "错误码",
  "error": "错误信息"
}
```

### 调用示例

```bash
curl -X POST \
  'https://video.inboxlinks.top/api/youtube/channel/v1/update_avatar?channel_id=UCxxxxxxxxxxxxxxxx' \
  -H 'x-api-key: token' \
  -F 'image=@/path/to/avatar.jpg'
```

---

## 刷新频道统计数据

触发一次实时同步，从上游拉取该频道最新的统计数据（总量、近 28 天变化量、近 28 天每日点位），写入 [频道分析数据](https://video.inboxlinks.top/api-docs/channel-analytics/) 对应的表。

### Request Body

```ts
type RefreshChannelStatsRequest = {
  channel_id: string; // YouTube 频道 ID
};
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容

### curl 调用示例

```bash
curl 'https://video.inboxlinks.top/api/youtube/channel/v1/refresh-stats' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "channel_id": "UCxxxxxxxxxxxxxxxx"
  }'
```
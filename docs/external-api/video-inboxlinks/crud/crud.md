---
title: "通用 CRUD 接口 | Video API 文档"
url: "https://video.inboxlinks.top/api-docs/crud/"
requestedUrl: "https://video.inboxlinks.top/api-docs/crud/"
siteName: "Video API 文档"
summary: "通用增删改查接口规范"
adapter: "generic"
capturedAt: "2026-08-02T03:24:33.310Z"
conversionMethod: "defuddle"
kind: "generic/article"
language: "zh"
---

## 通用 CRUD 接口

本章提供一组通用的“增删改查”接口说明，适用于多个资源类型（具体资源路径以实际为准）。

你可以把它理解成一套标准化的数据管理模式：

- **创建数据** ：新增一条记录，返回新记录对象
- **删除数据** ：按 `id` 数组删除
- **修改数据** ：按 `ids` 批量修改（patch）
- **查找数据列表** ：支持复杂条件（and/or/op）+ 排序 + 分页
- **全量或者断点拉取数据** ：用于大数据量场景的“游标/断点续拉”（key\_set）

---

## 创建数据

用于创建一条新的数据记录。

- **URL** ： `{资源URL前缀}/create`
- **Method** ： `POST`
- **Content-Type** ： `application/json`
- **认证** ：需在 Header 中携带 `x-api-key`

### Request Body

请求体内容是要创建的对象。例如：

```json
{
  "file_name": "example",
  "remark": "Example remark"
}
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：返回创建后的完整数据对象，包括生成的唯一标识等字段：

```json
{
  "id": "uuid",
  "create_time": "2023-11-28T12:34:56.789Z",
  "file_name": "example",
  "remark": "Example remark"
}
```

### 错误响应

- **HTTP 状态码** ： `4xx` / `5xx`
- **Body** （示例）：

```json
{
  "errcode": "FORBIDDEN",
  "error": "没有权限"
}
```

### 调用示例

```bash
curl 'https://video.inboxlinks.top/api/video/test/create' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "file_name": "example",
    "remark": "Example remark"
  }'
```

---

## 删除数据

用于批量删除指定 ID 的数据记录。

- **URL** ： `{资源URL前缀}/del`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

请求体为待删除 ID 数组，ID 可能是数字也可能是字符串类型，需要根据具体的接口定义确定。例如：

```json
["id1", "id2", "id3"]
```

### 成功响应

- **HTTP 状态码** ： `200 OK`
- **Body** ：无内容或空 JSON（视具体实现）

### 错误响应

- **HTTP 状态码** ：其他 HTTP 状态码
- **Body** ：

```json
{
  "errcode": "错误码",
  "error": "错误信息"
}
```

### 调用示例

```bash
curl 'https://video.inboxlinks.top/api/video/test/del' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '["uuid-1", "uuid-2"]'
```

---

## 修改数据

用于根据 ID 批量更新一组数据记录的部分字段（部分更新 / Patch）。

- **URL** ： `{资源URL前缀}/patch`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### Request Body

字段说明：

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `ids` | array | 是 | 要更新的数据唯一标识符数组 |
| `data` | object | 是 | 需要更新的字段键值对（部分字段） |

TypeScript 定义示例：

```ts
interface PatchRequest<T> {
  ids: string[] | number[];
  data: Partial<T>;
}
```

JSON 示例：

```json
{
  "ids": ["id1", "id2"],
  "data": {
    "remark": "new remark"
  }
}
```

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
curl '{资源URL前缀}/patch' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  --data-raw '{
    "ids": ["id1", "id2"],
    "data": {
      "remark": "new remark"
    }
  }'
```

---

## 查找数据列表

该接口用于按条件查询列表，并返回分页结果。它支持：

- 多条件组合（ `and` / `or` ）
- 多运算符（等于/不等于/包含/区间等，以类型 `Op` 为准）
- 排序（ `order` ）

示例（口头描述）：

- “找出 `status = enabled` 且 `id > 100` 的记录” → `{ "and": [ { "status": { "=": "enabled" } }, { "id": { ">": 100 } } ] }`
- “找出 `status = enabled` 或 `status = pending` 的记录” → `{ "or": [ { "status": { "=": "enabled" } }, { "status": { "=": "pending" } } ] }`
- **URL** ： `{资源URL前缀}/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### 查询参数结构定义

```ts
type Op =
  '=' | '!=' | 'LIKE' | 'NOT LIKE' | 'IS' | 'IS NOT' | '>' | '>=' | '<' | '<=' | 'IN' | 'NOT IN';

interface AndWhereBy {
  and: WhereBy[];
}

interface OrWhereBy {
  or: WhereBy[];
}

type OneWhereBy = {
  [field: string]: Partial<Record<Op, any>>;
};
// 示例: { "id": { ">=": 1 } } 或 { "status": { "=": "enabled" } }

type WhereBy = AndWhereBy | OrWhereBy | OneWhereBy;

type OrderBy = [string, 'asc' | 'desc' | 'asc nulls first' | 'desc nulls first'];

interface QueryParams {
  where: WhereBy | null; // 默认 null
  order: OrderBy[] | null; // 默认 [["id", "desc"]]
  limit: number | null; // 默认 10
  cursor: any | null; // 可选字段，分页查询的游标
}

interface PaginationDatas<T> {
  datas: T[]; // 数据列表
  total: number; // 总数
  next: any | null; // 下一页游标参数（如果有）
  prev: any | null; // 上一页游标参数（如果有）
}
```

### Request Body

请求体为 `QueryParams` 结构，例如：

```json
{
  "where": {
    "and": [
      { "id": { ">=": 1 } },
      {
        "or": [{ "status": { "=": "error" } }, { "status": { "=": "success" } }]
      }
    ]
  },
  "order": [
    ["name", "asc"],
    ["id", "desc"]
  ],
  "limit": 10
}
```

### Response Body

返回 `PaginationDatas<T>` 结构：

```json
{
  "datas": [
    {
      "id": 1,
      "name": "xxx"
    }
  ],
  "total": 100,
  "next": {}
}
```

### 调用示例

```bash
curl -X POST \
  http://localhost:3000/api/v1/xxx/list \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  -d '{
    "where": {
      "and": [
        { "id": { ">=": 1 } },
        {
          "or": [
            { "status": { "=": "error" } },
            { "status": { "=": "success" } }
          ]
        }
      ]
    },
    "order": [
      ["name", "asc"],
      ["id", "desc"]
    ],
    "limit": 10
  }'
```

---

## 全量或者游标拉取数据

该接口用于 **全量拉取** 或 **游标续拉** ，更适合大数据量场景：

- 更稳定（数据插入/删除时不容易翻页错乱）
- 更适合做“从上一次拉取位置继续拉”的同步任务
- **URL** ： `{资源URL前缀}/list`
- **Method** ： `POST`
- **Content-Type** ： `application/json`

### 查询参数结构定义

```ts
interface QueryParams {
  /**
   * 游标（来自服务端上一次响应中的 next 或 prev）
   * 回传时必须原样传回（不要解析/手改）
   */
  cursor: any | null;

  where: WhereBy | null; // 默认 null
  order: OrderBy[] | null; // 默认 [["id","desc"]]
  limit: number | null; // 默认 10；当前期望最大拉取数量
}

interface PaginationDatas<T> {
  datas: T[]; // 数据列表
  total: number; // 总数
  next: any | null; // 下一页的 key_set 游标；如果没有下一页，则为 null
  prev: any | null; // 上一页的 key_set 游标；如果没有上一页，则为 null
}
```

### Request Body

- **首次请求（从头开始拉取）** ：携带 `where` 与 `order` ，以及 `limit` 。此时不传 `cursor` （或传 `null` ）。
- **后续请求（翻页/断点续拉）** ：需要带上 `cursor` ：
	- 拉取下一页： `cursor = 上一次响应里的 next`
		- 拉取上一页： `cursor = 上一次响应里的 prev`
		- 此时 `where` 与 `order` 也需要和上次的请求完全一致。

首次请求示例：

```json
{
  "where": {
    "and": [
      { "id": { ">=": 1 } },
      {
        "or": [{ "status": { "=": "error" } }, { "status": { "=": "success" } }]
      }
    ]
  },
  "order": [
    ["name", "asc"],
    ["id", "desc"]
  ],
  "limit": 10
}
```

### Response Body

返回 `PaginationDatas<T>` 结构：

```json
{
  "datas": [
    {
      "id": 1,
      "name": "xxx"
    }
  ],
  "next": {},
  "prev": {},
  "total": 1
}
```

### 游标拉取流程说明（全量/断点续拉）

推荐的“断点续拉”流程（适合做同步器/批处理）：

1. 初始化： `cursor = null`
2. 循环拉取：
	- 请求：携带 `cursor: null` （如果 `cursor` 为空则表示从头开始）
		- 响应：返回 `datas` + `next` （以及可能的 `prev` ）
3. 处理数据：
	- 逐条处理 `datas`
		- 成功后暂存“下一页游标”（即 `next` ，例如保存到数据库/文件/缓存）
4. 更新游标：
	- `cursor = next`
5. 结束条件：
	- 当服务器返回的 `next` 为空

### 调用示例

```bash
curl -X POST \
  http://localhost:3000/api/v1/xxx/list \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: token' \
  -d '{
    "where": {
      "and": [
        { "id": { ">=": 1 } },
        {
          "or": [
            { "status": { "=": "error" } },
            { "status": { "=": "success" } }
          ]
        }
      ]
    },
    "order": [
      ["name", "asc"],
      ["id", "desc"]
    ],
    "limit": 10
  }'
```

---

## 获取单个数据

通过 ID 获取单条数据详情。

### Query Parameters

| 参数名 | 类型 | 必填 | 描述 |
| --- | --- | --- | --- |
| `id` 或接口约定的字段 | string / number | 是 | 数据 ID |

### 调用示例

```bash
curl -X GET '{资源URL前缀}/one?id=1' \
  -H 'x-api-key: token'
```

### 响应示例

```json
{
  "id": 1,
  "name": "xxx"
}
```
# 图片生成接口参考

> 当前生图接入以 `docs/api_v3.md` 为准。本文件保留历史 XG/SiliconFlow 接入资料用于排查旧任务，不再作为新模型路由的权威文档。

用于 DoodleStory 风格测试和任务 panel 生图。

## 环境变量

```env
SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
XG_API_KEY=
XG_API_BASE_URL=https://api.xgapi.top
XG_IMAGE_MODEL=gpt-image-2
XG_IMAGE_ASPECT_RATIO=9:16
```

## SiliconFlow 图片生成接口

以下模型精确命中时走 SiliconFlow：

- `Qwen/Qwen-Image-Edit-2509`
- `Qwen/Qwen-Image-Edit`
- `baidu/ERNIE-Image-Turbo`
- `Qwen/Qwen-Image`

```text
POST https://api.siliconflow.cn/v1/images/generations
```

请求：

- `application/json`
- `Authorization: Bearer <SILICONFLOW_API_KEY>`
- 文本提示字段：`prompt`
- 模型字段：`model`
- `Qwen/Qwen-Image-Edit-2509` 不传 `image_size`，最多传 `image`、`image2`、`image3`
- `Qwen/Qwen-Image-Edit` 不传 `image_size`，最多传 `image`
- `Qwen/Qwen-Image` 使用官方推荐 `image_size`，并传 `cfg=4`
- `baidu/ERNIE-Image-Turbo` 使用与画面比例对应的 `image_size`

响应：

- `images[0].url` 是短期有效 URL
- 后端必须立即下载图片并写入 `file_assets`
- 前端不得直接使用 SiliconFlow 返回的短期 URL

## XG 图片编辑接口

```text
POST https://api.xgapi.top/v1/images/edits
```

请求：

- `multipart/form-data`
- `Authorization: Bearer <XG_API_KEY>`
- 多张参考图使用重复字段 `image[]`
- 文本提示字段：`prompt`
- 模型字段：`model`
- 比例字段：`aspect_ratio=9:16`
- 返回字段：`response_format=url`

## curl 示例

```bash
curl https://api.xgapi.top/v1/images/edits \
  -H "Authorization: Bearer YOUR_XG_API_KEY" \
  -H "Accept: application/json" \
  -F "model=gpt-image-2" \
  -F "prompt=Use the reference images to keep the same character identity and outfit, bright clinic scene, no text, no watermark." \
  -F "aspect_ratio=9:16" \
  -F "response_format=url" \
  -F "image[]=@/absolute/path/ref1.png" \
  -F "image[]=@/absolute/path/ref2.png" \
  -F "image[]=@/absolute/path/ref3.png"
```

## Python requests 示例

```python
import requests

url = "https://api.xgapi.top/v1/images/edits"
api_key = "YOUR_XG_API_KEY"

files = [
    ("image[]", ("ref1.png", open("/absolute/path/ref1.png", "rb"), "image/png")),
    ("image[]", ("ref2.png", open("/absolute/path/ref2.png", "rb"), "image/png")),
    ("image[]", ("ref3.png", open("/absolute/path/ref3.png", "rb"), "image/png")),
]

data = {
    "model": "gpt-image-2",
    "prompt": "Use the reference images to keep the same character identity and outfit, bright clinic scene, no text, no watermark.",
    "aspect_ratio": "9:16",
    "response_format": "url",
}

resp = requests.post(
    url,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    },
    data=data,
    files=files,
    timeout=300,
)

print(resp.status_code)
print(resp.text)
```

## 落库规则

- 风格测试只生成一张测试图。
- 任务中每个 panel 只生成一张图。
- 返回 URL 后，后端必须下载图片并写入 `file_assets`。
- 图片必须保存 9:16 输出，不在前端拉伸或裁剪破坏比例。
- provider 错误必须写入 `style_tests`、`generated_images` 或 `generation_tasks` 的错误字段。

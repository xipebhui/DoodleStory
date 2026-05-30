# XG 图片生成接口参考

用于 DoodleStory 风格测试和任务 panel 生图。

## 环境变量

```env
XG_API_KEY=
XG_API_BASE_URL=https://api.xgapi.top
XG_IMAGE_MODEL=gpt-image-2
XG_IMAGE_ASPECT_RATIO=9:16
```

## 接口

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

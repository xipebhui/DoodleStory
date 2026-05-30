# SiliconFlow LLM 接口参考

用于 DoodleStory 的两个文本生成步骤：

1. 故事语义切分：原始故事 -> 有序 panels。
2. Panel 生图 prompt：原始故事 + 风格提示词 + panel 文本 -> 静态画面描述。

## 环境变量

```env
SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_TEXT_MODEL=deepseek-ai/DeepSeek-V3.2
```

## 调用约定

SiliconFlow 文档提供 OpenAI SDK 兼容调用方式：

```python
from openai import OpenAI

client = OpenAI(
    api_key=SILICONFLOW_API_KEY,
    base_url="https://api.siliconflow.cn/v1",
)

response = client.chat.completions.create(
    model=SILICONFLOW_TEXT_MODEL,
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
    ],
    response_format={"type": "json_object"},
)
```

## 输出要求

必须要求 JSON 输出，不能依赖自然语言解析。

故事切分输出：

```json
{
  "panels": [
    {
      "order": 1,
      "text": "原始故事中的片段"
    }
  ]
}
```

Panel prompt 输出：

```json
{
  "prompts": [
    {
      "order": 1,
      "prompt": "主体、动作、场景、静态画面状态"
    }
  ]
}
```

## 规则

- 不改写 `generation_tasks.original_text`。
- 固定数量模式必须输出对应数量 panels。
- 自动数量模式按语义切分，约 10 个中文字符一段只是启发，不是硬规则。
- 生成 prompt 必须强调遵守风格提示词，不能和风格冲突。
- JSON 解析失败、数量不匹配、缺字段都应使步骤失败并写入数据库错误字段。

参考文档：https://api-docs.siliconflow.cn/docs/userguide/capabilities/text-generation

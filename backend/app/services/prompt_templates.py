import re
from pathlib import Path

PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


class PromptTemplateError(ValueError):
    pass


def read_prompt_template(name: str) -> str:
    return (PROMPT_ROOT / name).read_text(encoding="utf-8")


def render_prompt_template(name: str, values: dict[str, object]) -> str:
    template = read_prompt_template(name)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise PromptTemplateError(f"Prompt 模板变量缺失：{key}")
        value = values[key]
        return "" if value is None else str(value)

    rendered = PLACEHOLDER_PATTERN.sub(replace, template)
    missing = PLACEHOLDER_PATTERN.findall(rendered)
    if missing:
        raise PromptTemplateError(f"Prompt 模板仍有未渲染变量：{', '.join(sorted(set(missing)))}")
    return rendered.strip()

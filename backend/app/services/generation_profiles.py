import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


class GenerationProfileError(Exception):
    pass


class GenerationProfileConfigError(GenerationProfileError):
    pass


class UnknownGenerationProfileError(GenerationProfileError):
    pass


@dataclass(frozen=True)
class GenerationProfile:
    key: str
    llm_provider: str
    llm_model: str
    image_provider: str
    image_model: str
    aspect_ratio: str


REQUIRED_PROFILE_FIELDS = ("llm_provider", "llm_model", "image_provider", "image_model", "aspect_ratio")


def _read_required_string(key: str, raw_profile: dict[str, Any], field: str) -> str:
    value = raw_profile.get(field)
    if not isinstance(value, str) or not value.strip():
        raise GenerationProfileConfigError(f"生成配置 {key} 缺少必填字段 {field}")
    return value.strip()


@lru_cache
def get_generation_profiles() -> dict[str, GenerationProfile]:
    settings = get_settings()
    if not settings.generation_profiles_json.strip():
        return {}

    try:
        raw = json.loads(settings.generation_profiles_json)
    except json.JSONDecodeError as exc:
        raise GenerationProfileConfigError("GENERATION_PROFILES_JSON 不是合法 JSON") from exc

    if not isinstance(raw, dict):
        raise GenerationProfileConfigError("GENERATION_PROFILES_JSON 必须是对象结构")

    profiles: dict[str, GenerationProfile] = {}
    for key, raw_profile in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise GenerationProfileConfigError("生成配置 Key 必须是非空字符串")
        if not isinstance(raw_profile, dict):
            raise GenerationProfileConfigError(f"生成配置 {key} 必须是对象结构")

        cleaned_key = key.strip()
        values = {field: _read_required_string(cleaned_key, raw_profile, field) for field in REQUIRED_PROFILE_FIELDS}
        profiles[cleaned_key] = GenerationProfile(key=cleaned_key, **values)

    return profiles


def get_generation_profile(key: str) -> GenerationProfile:
    profiles = get_generation_profiles()
    cleaned_key = key.strip()
    profile = profiles.get(cleaned_key)
    if profile is None:
        raise UnknownGenerationProfileError(f"生成配置 Key 未配置：{cleaned_key}")
    return profile


def validate_generation_profile_key(key: str) -> None:
    get_generation_profile(key)

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re


DEFAULT_SKILL_ROOT = Path(__file__).resolve().parents[1] / "agent_skills"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SKILL_FILE_BYTES = 64 * 1024
MAX_SKILL_COUNT = 32
MAX_SKILL_DESCRIPTION_CHARS = 500
FRONTMATTER_FIELDS = {"name", "description", "version"}


class SkillRegistryError(RuntimeError):
    pass


class SkillNotFoundError(SkillRegistryError):
    pass


@dataclass(frozen=True)
class SkillPackage:
    name: str
    description: str
    version: int
    content_hash: str
    instructions: str

    def catalog_item(self) -> dict[str, str | int]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "content_hash": self.content_hash,
        }


def _parse_frontmatter(content: str, *, source: Path) -> dict[str, str]:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise SkillRegistryError(f"Skill 缺少起始 frontmatter: {source.name}")
    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise SkillRegistryError(f"Skill frontmatter 未闭合: {source.name}") from exc
    if closing_index == 1:
        raise SkillRegistryError(f"Skill frontmatter 不能为空: {source.name}")

    values: dict[str, str] = {}
    for line in lines[1:closing_index]:
        key, separator, raw_value = line.partition(":")
        key = key.strip()
        value = raw_value.strip()
        if not separator or not key or not value:
            raise SkillRegistryError(f"Skill frontmatter 行格式错误: {source.name}")
        if key not in FRONTMATTER_FIELDS:
            raise SkillRegistryError(f"Skill frontmatter 包含未支持字段 {key}: {source.name}")
        if key in values:
            raise SkillRegistryError(f"Skill frontmatter 字段重复 {key}: {source.name}")
        values[key] = value

    missing = FRONTMATTER_FIELDS.difference(values)
    if missing:
        raise SkillRegistryError(
            f"Skill frontmatter 缺少字段 {', '.join(sorted(missing))}: {source.name}"
        )
    return values


class SkillRegistry:
    def __init__(
        self,
        root: Path | str = DEFAULT_SKILL_ROOT,
        *,
        max_skill_file_bytes: int = MAX_SKILL_FILE_BYTES,
        max_skill_count: int = MAX_SKILL_COUNT,
    ):
        self.root = Path(root).resolve()
        self.max_skill_file_bytes = max_skill_file_bytes
        self.max_skill_count = max_skill_count
        self._packages = self._scan()

    def _scan(self) -> dict[str, SkillPackage]:
        if not self.root.is_dir():
            raise SkillRegistryError(f"Runtime Skill 根目录不存在: {self.root}")
        directories = sorted(path for path in self.root.iterdir() if path.is_dir())
        if len(directories) > self.max_skill_count:
            raise SkillRegistryError(
                f"Runtime Skill 数量超过上限 {self.max_skill_count}: {len(directories)}"
            )

        packages: dict[str, SkillPackage] = {}
        for directory in directories:
            if directory.is_symlink():
                raise SkillRegistryError(f"Runtime Skill 目录不能是符号链接: {directory.name}")
            directory_name = directory.name
            if not SKILL_NAME_PATTERN.fullmatch(directory_name):
                raise SkillRegistryError(f"Runtime Skill 目录名不合法: {directory_name}")
            skill_path = directory / "SKILL.md"
            if not skill_path.is_file():
                raise SkillRegistryError(f"Runtime Skill 缺少 SKILL.md: {directory_name}")
            if skill_path.is_symlink():
                raise SkillRegistryError(f"Runtime SKILL.md 不能是符号链接: {directory_name}")
            resolved_skill_path = skill_path.resolve()
            try:
                resolved_skill_path.relative_to(self.root)
            except ValueError as exc:
                raise SkillRegistryError(f"Runtime Skill 路径越界: {directory_name}") from exc

            size = resolved_skill_path.stat().st_size
            if size <= 0 or size > self.max_skill_file_bytes:
                raise SkillRegistryError(
                    f"Runtime Skill 文件大小必须在 1..{self.max_skill_file_bytes} 字节: "
                    f"{directory_name}"
                )
            try:
                content_bytes = resolved_skill_path.read_bytes()
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SkillRegistryError(
                    f"Runtime Skill 必须使用 UTF-8 编码: {directory_name}"
                ) from exc

            frontmatter = _parse_frontmatter(content, source=resolved_skill_path)
            name = frontmatter["name"]
            if name in packages:
                raise SkillRegistryError(f"Runtime Skill name 重复: {name}")
            if name != directory_name:
                raise SkillRegistryError(
                    f"Runtime Skill name 必须与目录名一致: {name} != {directory_name}"
                )
            description = frontmatter["description"]
            if len(description) > MAX_SKILL_DESCRIPTION_CHARS:
                raise SkillRegistryError(
                    f"Runtime Skill description 超过 {MAX_SKILL_DESCRIPTION_CHARS} 字符: {name}"
                )
            raw_version = frontmatter["version"]
            if not raw_version.isdigit() or int(raw_version) <= 0:
                raise SkillRegistryError(f"Runtime Skill version 必须是正整数: {name}")

            packages[name] = SkillPackage(
                name=name,
                description=description,
                version=int(raw_version),
                content_hash=f"sha256:{hashlib.sha256(content_bytes).hexdigest()}",
                instructions=content,
            )
        return packages

    def catalog(self) -> list[dict[str, str | int]]:
        return [self._packages[name].catalog_item() for name in sorted(self._packages)]

    def load(self, skill_name: str) -> SkillPackage:
        if not SKILL_NAME_PATTERN.fullmatch(skill_name):
            raise SkillNotFoundError("Skill name 不合法或未注册")
        package = self._packages.get(skill_name)
        if package is None:
            raise SkillNotFoundError(f"Skill 未注册: {skill_name}")
        return package

    def catalog_instructions(self) -> str:
        lines = [
            "可用 Runtime Skill catalog（这里只包含元数据，不包含 Skill 正文）：",
        ]
        for item in self.catalog():
            lines.append(
                f"- {item['name']} v{item['version']} "
                f"({item['content_hash']}): {item['description']}"
            )
        lines.append(
            "只有在任务需要某个 Skill 时才调用只读 load_skill，并使用精确 skill_name；"
            "不得猜测文件路径、绝对路径或未注册 Skill。"
        )
        return "\n".join(lines)


_runtime_registry: SkillRegistry | None = None


def initialize_runtime_skill_registry(
    root: Path | str = DEFAULT_SKILL_ROOT,
) -> SkillRegistry:
    global _runtime_registry
    _runtime_registry = SkillRegistry(root)
    return _runtime_registry


def get_runtime_skill_registry() -> SkillRegistry:
    global _runtime_registry
    if _runtime_registry is None:
        _runtime_registry = SkillRegistry()
    return _runtime_registry


def reset_runtime_skill_registry_for_tests() -> None:
    global _runtime_registry
    _runtime_registry = None

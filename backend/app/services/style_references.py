from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FileAsset, GenerationTask, Style, StyleReferenceImage, TaskStyleReferenceImage
from app.models.enums import StyleReferenceMode
from app.services.image_generation import ImageProviderConfigError, ImageReference


@dataclass(frozen=True)
class StyleReferencePack:
    references: list[ImageReference]
    notes: list[str]
    style_count: int


def is_prompt_reference_mode(mode: StyleReferenceMode | str | None) -> bool:
    return (mode or StyleReferenceMode.prompt) == StyleReferenceMode.prompt


def is_image_reference_mode(mode: StyleReferenceMode | str | None) -> bool:
    return (mode or StyleReferenceMode.prompt) == StyleReferenceMode.image


def public_style_reference_url(asset: FileAsset) -> str:
    url = (asset.public_url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ImageProviderConfigError("参考图模式要求风格参考图提供可公开访问的 HTTP(S) URL")
    return url


def ordered_style_reference_images(style: Style) -> list[StyleReferenceImage]:
    return sorted(style.reference_images, key=lambda item: item.display_order)


def build_style_reference_pack_from_assets(
    assets: list[FileAsset],
    *,
    start_index: int = 1,
) -> StyleReferencePack:
    references: list[ImageReference] = []
    notes: list[str] = []
    for offset, asset in enumerate(assets):
        reference_index = start_index + offset
        references.append(ImageReference(url=public_style_reference_url(asset)))
        notes.append(f"风格参考（参考图{reference_index}）")
    return StyleReferencePack(references=references, notes=notes, style_count=len(references))


def build_style_reference_pack_from_style(
    style: Style,
    *,
    start_index: int = 1,
) -> StyleReferencePack:
    if is_prompt_reference_mode(style.style_reference_mode):
        return StyleReferencePack(references=[], notes=[], style_count=0)

    assets = [reference.asset for reference in ordered_style_reference_images(style)]
    if not assets:
        raise ImageProviderConfigError("参考图模式下必须至少上传一张风格参考图")
    return build_style_reference_pack_from_assets(assets, start_index=start_index)


def snapshot_task_style_reference_images(*, db: Session, task: GenerationTask, style: Style) -> None:
    existing = db.scalars(
        select(TaskStyleReferenceImage).where(TaskStyleReferenceImage.task_id == task.id)
    ).all()
    for reference in existing:
        db.delete(reference)
    db.flush()

    if is_prompt_reference_mode(style.style_reference_mode):
        return

    style_reference_images = ordered_style_reference_images(style)
    if not style_reference_images:
        raise ImageProviderConfigError("参考图模式下必须至少上传一张风格参考图")

    for order, reference in enumerate(style_reference_images, start=1):
        public_style_reference_url(reference.asset)
        db.add(
            TaskStyleReferenceImage(
                task_id=task.id,
                asset_id=reference.asset_id,
                reference_order=order,
            )
        )


def build_task_style_reference_pack(
    task: GenerationTask,
    *,
    start_index: int = 1,
) -> StyleReferencePack:
    if is_prompt_reference_mode(task.style_reference_mode_snapshot):
        return StyleReferencePack(references=[], notes=[], style_count=0)

    sorted_references = sorted(task.style_reference_images, key=lambda item: item.reference_order)
    if not sorted_references:
        raise ImageProviderConfigError("任务缺少风格参考图快照")

    assets = [reference.asset for reference in sorted_references]
    return build_style_reference_pack_from_assets(assets, start_index=start_index)

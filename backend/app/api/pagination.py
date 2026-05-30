from dataclasses import dataclass

from fastapi import HTTPException, Query, status


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit


def get_pagination(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> Pagination:
    if cursor is None:
        return Pagination(limit=limit, offset=0)

    try:
        offset = int(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分页 cursor 不合法") from exc

    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分页 cursor 不合法")

    return Pagination(limit=limit, offset=offset)


def build_page(limit: int, offset: int, item_count: int) -> dict[str, int | str | bool | None]:
    has_more = item_count > limit
    return {
        "limit": limit,
        "next_cursor": str(offset + limit) if has_more else None,
        "has_more": has_more,
    }

from datetime import datetime, timedelta, timezone
import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.schemas.common import (
    ApiData,
    ApiList,
    PageInfo,
    api_datetime_iso,
)


class NestedTimestampRead(BaseModel):
    created_at: datetime
    entries: list[dict[str, datetime]]


class ApiDatetimeSerializationTests(unittest.TestCase):
    def test_api_data_marks_naive_database_datetime_as_utc(self) -> None:
        response = ApiData[NestedTimestampRead](
            data=NestedTimestampRead(
                created_at=datetime(2026, 7, 28, 7, 0),
                entries=[{"finished_at": datetime(2026, 7, 28, 7, 30)}],
            )
        )

        payload = json.loads(response.model_dump_json())

        self.assertEqual("2026-07-28T07:00:00Z", payload["data"]["created_at"])
        self.assertEqual(
            "2026-07-28T07:30:00Z",
            payload["data"]["entries"][0]["finished_at"],
        )

    def test_api_data_converts_aware_datetime_to_utc(self) -> None:
        china_timezone = timezone(timedelta(hours=8))
        response = ApiData[NestedTimestampRead](
            data=NestedTimestampRead(
                created_at=datetime(
                    2026,
                    7,
                    28,
                    15,
                    0,
                    tzinfo=china_timezone,
                ),
                entries=[],
            )
        )

        payload = json.loads(response.model_dump_json())

        self.assertEqual("2026-07-28T07:00:00Z", payload["data"]["created_at"])

    def test_api_list_and_sse_datetime_share_utc_contract(self) -> None:
        response = ApiList[NestedTimestampRead](
            items=[
                NestedTimestampRead(
                    created_at=datetime(2026, 7, 28, 7, 0),
                    entries=[],
                )
            ],
            page=PageInfo(limit=1, next_cursor=None, has_more=False),
        )

        payload = json.loads(response.model_dump_json())

        self.assertEqual("2026-07-28T07:00:00Z", payload["items"][0]["created_at"])
        self.assertEqual(
            "2026-07-28T07:00:00Z",
            api_datetime_iso(datetime(2026, 7, 28, 7, 0)),
        )

    def test_fastapi_response_model_preserves_utc_marker(self) -> None:
        app = FastAPI()

        @app.get("/timestamp", response_model=ApiData[NestedTimestampRead])
        def timestamp() -> ApiData[NestedTimestampRead]:
            return ApiData(
                data=NestedTimestampRead(
                    created_at=datetime(2026, 7, 28, 7, 0),
                    entries=[],
                )
            )

        response = TestClient(app).get("/timestamp")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            "2026-07-28T07:00:00Z",
            response.json()["data"]["created_at"],
        )


if __name__ == "__main__":
    unittest.main()

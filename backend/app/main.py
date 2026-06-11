from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, auth, characters, content_extractions, credits, style_tests, styles, tasks
from app.api.errors import http_exception_handler, validation_exception_handler
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.task_worker import init_task_queue, recover_queued_tasks, shutdown_task_queue

settings = get_settings()
configure_logging(settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(title="DoodleStory API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.on_event("startup")
    async def startup() -> None:
        content_extractions.recover_interrupted_content_extractions()
        init_task_queue()
        await recover_queued_tasks()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await shutdown_task_queue()

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(styles.router, prefix="/api/v1")
    app.include_router(style_tests.router, prefix="/api/v1")
    app.include_router(characters.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(content_extractions.router, prefix="/api/v1")
    app.include_router(assets.router, prefix="/api/v1")
    app.include_router(credits.router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

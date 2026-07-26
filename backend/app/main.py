from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import agent_skills, audio_references, assets, auth, characters, content_extractions, credits, native_agent, style_tests, styles, tasks, video_tasks
from app.api.errors import http_exception_handler, validation_exception_handler
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.task_worker import init_task_queue, recover_queued_tasks, shutdown_task_queue
from app.services.video_task_worker import init_video_task_queue, recover_video_tasks, shutdown_video_task_queue
from app.services.agent_observability import initialize_agent_observability
from app.services.agent_skill_registry import initialize_runtime_skill_registry
from app.services.agent_skill_management import initialize_system_agent_skills

settings = get_settings()
configure_logging(settings.log_level)


def mount_frontend_dist(app: FastAPI, frontend_dist: Path) -> None:
    frontend_dist = frontend_dist.resolve()
    index_path = frontend_dist / "index.html"
    if not index_path.is_file():
        raise RuntimeError(f"DOODLESTORY_FRONTEND_DIST does not contain index.html: {frontend_dist}")

    @app.get("/{spa_path:path}", include_in_schema=False)
    def frontend_spa(spa_path: str) -> FileResponse:
        candidate = (frontend_dist / spa_path).resolve()
        try:
            candidate.relative_to(frontend_dist)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)


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
        initialize_runtime_skill_registry()
        initialize_system_agent_skills()
        initialize_agent_observability(settings)
        content_extractions.recover_interrupted_content_extractions()
        styles.recover_interrupted_style_tests()
        init_task_queue()
        init_video_task_queue()
        await recover_queued_tasks()
        await recover_video_tasks()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await shutdown_task_queue()
        await shutdown_video_task_queue()

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(styles.router, prefix="/api/v1")
    app.include_router(style_tests.router, prefix="/api/v1")
    app.include_router(characters.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(video_tasks.router, prefix="/api/v1")
    app.include_router(audio_references.router, prefix="/api/v1")
    app.include_router(content_extractions.router, prefix="/api/v1")
    app.include_router(assets.router, prefix="/api/v1")
    app.include_router(credits.router, prefix="/api/v1")
    app.include_router(agent_skills.router, prefix="/api/v1")
    app.include_router(native_agent.router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.frontend_dist_path:
        mount_frontend_dist(app, settings.frontend_dist_path)

    return app


app = create_app()

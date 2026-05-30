from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, auth, styles, tasks
from app.core.config import get_settings
from app.core.database import Base, engine
from app.models import entities

settings = get_settings()


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)

    app = FastAPI(title="DoodleStory API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(styles.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(assets.router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

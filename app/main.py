from fastapi import FastAPI

from app.api.routes.documents import router as documents_router
from app.api.routes.rag import router as rag_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(documents_router, prefix=settings.api_v1_prefix)
    app.include_router(rag_router, prefix=settings.api_v1_prefix)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

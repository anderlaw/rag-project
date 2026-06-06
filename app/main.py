from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.rag import router as rag_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    # 创建app实例，并设置标题和调试模式
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    # 两个router 一个是文档模块，一个是RAG模块
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(documents_router, prefix=settings.api_v1_prefix)
    app.include_router(rag_router, prefix=settings.api_v1_prefix)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}
    # 返回应用实例
    return app


app = create_app()

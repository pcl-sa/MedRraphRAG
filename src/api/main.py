"""FastAPI application entry point.

Usage:
    python -m src.api.main
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="MedGraphRAG API",
        description="Medical GraphRAG Q&A System",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes.chat import router as chat_router
    from .routes.trace import router as trace_router
    app.include_router(chat_router)
    app.include_router(trace_router)

    @app.on_event("startup")
    async def startup():
        print(f"  Starting MedGraphRAG API on {settings.server_host}:{settings.server_port}")

    @app.on_event("shutdown")
    async def shutdown():
        from .dependencies import _graph_retriever
        if _graph_retriever:
            _graph_retriever.close()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug_mode,
    )

import time
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from gitlab_chatbot.routes.chatbot.route import router as chatbot_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_app() -> FastAPI:
    app = FastAPI(
        title="GitLab Chatbot API",
        description="A chatbot service for GitLab documentation using RAG and Gemini LLM",
        version="1.0.0",
        docs_url="/chatbot/docs",
        redoc_url="/chatbot/redoc",
        openapi_url="/chatbot/openapi.json",
    )

    app.include_router(chatbot_router, prefix="/api/v1/chatbot", tags=["chatbot"])
    return app


def add_middlewares(app: FastAPI):
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Replace with specific domains in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


app = initialize_app()
add_middlewares(app)


@app.get("/")
async def root():
    return {"message": "GitLab Chatbot API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    logger.info("Starting GitLab Chatbot API server...")
    import uvicorn

    uvicorn.run(
        "gitlab_chatbot.__main__:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable, Deque, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lexnusa.agent.router import route_query
from lexnusa.rag import answer

AnswerFunction = Callable[..., str]


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    use_llm: bool = True
    use_reranker: bool = False


class QueryPlanResponse(BaseModel):
    route: str
    queries: list[str]


class ChatResponse(BaseModel):
    answer: str
    plan: QueryPlanResponse


class SlidingWindowLimiter:
    def __init__(self, requests: int = 30, window_seconds: int = 60) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self.events: defaultdict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        events = self.events[key]
        while events and events[0] <= now - self.window_seconds:
            events.popleft()
        if len(events) >= self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Terlalu banyak permintaan. Coba lagi sebentar.",
            )
        events.append(now)


def create_app(
    *,
    answer_function: AnswerFunction = answer,
    index_dir: Path | None = None,
    static_dir: Path | None = None,
    rate_limit: int | None = None,
) -> FastAPI:
    app = FastAPI(
        title="LexNusa API",
        version="0.1.0",
        description="API pencarian regulasi Indonesia dengan sitasi sumber resmi.",
    )
    configured_index = index_dir or Path(os.getenv("LEXNUSA_INDEX_DIR", "data/qdrant"))
    configured_static = static_dir or Path(__file__).with_name("web")
    limiter = SlidingWindowLimiter(
        requests=rate_limit or int(os.getenv("LEXNUSA_RATE_LIMIT", "30"))
    )

    def authorize(request: Request, x_api_key: Optional[str] = Header(default=None)) -> None:
        expected = os.getenv("LEXNUSA_API_KEY")
        if expected and x_api_key != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key tidak valid.")
        client = request.client.host if request.client else "unknown"
        limiter.check(x_api_key or client)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(authorize)])
    def chat(payload: ChatRequest) -> ChatResponse:
        question = " ".join(payload.question.split())
        plan = route_query(question)
        result = answer_function(
            question,
            configured_index,
            use_llm=payload.use_llm,
            backend="qdrant",
            use_reranker=payload.use_reranker,
        )
        return ChatResponse(
            answer=result,
            plan=QueryPlanResponse(route=plan.route.value, queries=list(plan.queries)),
        )

    if configured_static.exists():
        assets = configured_static / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/", include_in_schema=False)
        def home() -> FileResponse:
            return FileResponse(configured_static / "index.html")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "lexnusa.api:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )

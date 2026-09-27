from __future__ import annotations

import json
import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.graph.build import build_default
from app.graph.runner import CrewRunner, Event
from app.scenarios import SCENARIOS
from app.tools.tickets import list_tickets

log = logging.getLogger("triage_crew")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = None


class ResumeRequest(BaseModel):
    approved: bool
    edits: dict[str, str] | None = None
    note: str | None = None


def _sse(event: Event) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"


def create_app(settings: Settings | None = None, persistent: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        graph, deps = build_default(settings, persistent=persistent)
        app.state.runner = CrewRunner(graph)
        app.state.deps = deps
        log.info("Triage Crew ready (llm=%s)", deps.llm.name)
        yield
        deps.store.close()

    app = FastAPI(title="Triage Crew API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
    )

    active: set[str] = set()
    active_lock = threading.Lock()

    def stream(thread_id: str, events: Iterator[Event]) -> StreamingResponse:
        if thread_id in active:
            raise HTTPException(409, "This thread is already running.")

        def body() -> Iterator[str]:
            with active_lock:
                active.add(thread_id)
            try:
                yield _sse({"type": "thread", "thread_id": thread_id})
                for event in events:
                    yield _sse(event)
            except Exception as exc:
                log.exception("Crew run failed")
                yield _sse({"type": "error", "message": str(exc)})
            finally:
                with active_lock:
                    active.discard(thread_id)
                yield _sse({"type": "done"})

        return StreamingResponse(
            body(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def runner() -> CrewRunner:
        return app.state.runner

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "llm_provider": app.state.deps.llm.name}

    @app.get("/api/scenarios")
    def scenarios() -> list[dict[str, str]]:
        return SCENARIOS

    @app.post("/api/chat")
    def chat(req: ChatRequest) -> StreamingResponse:
        thread_id = req.thread_id or uuid.uuid4().hex
        if runner().pending_approval(thread_id):
            raise HTTPException(409, "Resolve the pending approval before sending a new message.")
        return stream(thread_id, runner().start(thread_id, req.message))

    @app.post("/api/threads/{thread_id}/resume")
    def resume(thread_id: str, req: ResumeRequest) -> StreamingResponse:
        if not runner().pending_approval(thread_id):
            raise HTTPException(409, "This thread has no pending approval.")
        return stream(thread_id, runner().resume(thread_id, req.model_dump()))

    @app.get("/api/threads/{thread_id}")
    def thread(thread_id: str) -> dict[str, Any]:
        return runner().history(thread_id)

    @app.get("/api/tickets")
    def tickets() -> list[dict[str, Any]]:
        return list_tickets(app.state.deps.store)

    return app


app = create_app()

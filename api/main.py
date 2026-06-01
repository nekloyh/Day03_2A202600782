"""
FastAPI server for the Research Gap Analyzer ReAct Agent.
Provides REST endpoints and WebSocket for real-time trace streaming.
"""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Ensure the repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from api.models import ProviderInfo, RunRequest, RunResponse, TraceEvent
from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider
from src.telemetry.metrics import tracker
from src.tools.output_writer import write_research_artifacts
from src.tools.research_tools import (
    compare_and_find_gaps,
    extract_evidence_cards,
    search_papers,
)

# ---------------------------------------------------------------------------
# In-memory store for run results
# ---------------------------------------------------------------------------
RUN_STORE: Dict[str, RunResponse] = {}

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections for trace streaming."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)

    def disconnect(self, websocket: WebSocket, run_id: str):
        if run_id in self.active_connections:
            self.active_connections[run_id] = [
                ws for ws in self.active_connections[run_id] if ws is not websocket
            ]
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def send_event(self, run_id: str, event: Dict[str, Any]):
        if run_id not in self.active_connections:
            return
        data = json.dumps(event, default=str, ensure_ascii=False)
        dead = []
        for ws in self.active_connections[run_id]:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, run_id)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Intercepting logger to capture events for WebSocket
# ---------------------------------------------------------------------------

class TraceCapture:
    """Captures telemetry events and forwards them to WebSocket clients."""

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.run_id: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_context(self, run_id: str, loop: asyncio.AbstractEventLoop):
        self.run_id = run_id
        self._loop = loop
        self.events = []

    def capture(self, event_type: str, data: Dict[str, Any]):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            "data": data,
        }
        self.events.append(event)
        if self._loop and self.run_id:
            asyncio.run_coroutine_threadsafe(
                manager.send_event(self.run_id, event),
                self._loop,
            )


trace_capture = TraceCapture()


# ---------------------------------------------------------------------------
# Monkey-patch the global logger to also capture events
# ---------------------------------------------------------------------------

from src.telemetry.logger import logger as _original_logger

_original_log_event = _original_logger.log_event


def _patched_log_event(event_type: str, data: Dict[str, Any]):
    _original_log_event(event_type, data)
    trace_capture.capture(event_type, data)


_original_logger.log_event = _patched_log_event


# ---------------------------------------------------------------------------
# Scripted provider (imported from demo script)
# ---------------------------------------------------------------------------

from scripts.run_research_gap_demo import (
    ScriptedProvider,
    build_llm_provider,
    build_research_tools,
    scripted_success_responses,
)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Research Gap Analyzer API",
    description="API for the ReAct Agent Research Gap Analyzer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/providers")
async def list_providers() -> List[ProviderInfo]:
    """List all available LLM providers with their status."""
    providers = [
        ProviderInfo(
            name="scripted",
            display_name="Scripted (Demo)",
            available=True,
            requires_key=False,
        ),
        ProviderInfo(
            name="mimo",
            display_name="Xiaomi MiMo",
            available=bool(os.getenv("MIMO_API_KEY")),
            requires_key=True,
            env_var="MIMO_API_KEY",
        ),
        ProviderInfo(
            name="openai",
            display_name="OpenAI GPT-4o",
            available=bool(os.getenv("OPENAI_API_KEY")),
            requires_key=True,
            env_var="OPENAI_API_KEY",
        ),
        ProviderInfo(
            name="google",
            display_name="Google Gemini",
            available=bool(os.getenv("GEMINI_API_KEY")),
            requires_key=True,
            env_var="GEMINI_API_KEY",
        ),
        ProviderInfo(
            name="local",
            display_name="Local (Phi-3 GGUF)",
            available=Path(
                os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
            ).exists(),
            requires_key=False,
        ),
    ]
    return providers


@app.post("/api/run")
async def run_agent(request: RunRequest) -> RunResponse:
    """Run the ReAct agent with the given configuration."""
    run_id = str(uuid.uuid4())[:8]
    loop = asyncio.get_event_loop()
    trace_capture.set_context(run_id, loop)
    tracker.session_metrics.clear()

    output_dir = REPO_ROOT / "outputs" / f"run_{run_id}"

    try:
        result = await asyncio.to_thread(
            _run_agent_sync,
            topic=request.topic,
            provider=request.provider.value,
            offline=request.offline,
            max_steps=request.max_steps,
            output_dir=output_dir,
        )
    except Exception as exc:
        response = RunResponse(
            run_id=run_id,
            status="error",
            final_answer=f"Agent error: {exc}",
            trace=[TraceEvent(**e) for e in trace_capture.events],
            metrics=list(tracker.session_metrics),
        )
        RUN_STORE[run_id] = response
        return response

    # Check if artifacts exist
    artifacts = None
    report = output_dir / "gap_analysis_report.md"
    if report.exists():
        artifacts = {
            "gap_analysis_report": (output_dir / "gap_analysis_report.md").read_text(encoding="utf-8")
            if (output_dir / "gap_analysis_report.md").exists() else None,
            "comparison_matrix": (output_dir / "comparison_matrix.md").read_text(encoding="utf-8")
            if (output_dir / "comparison_matrix.md").exists() else None,
            "evidence_cards": (output_dir / "evidence_cards.json").read_text(encoding="utf-8")
            if (output_dir / "evidence_cards.json").exists() else None,
        }

    status = "completed" if "Max steps exceeded" not in (result or "") else "max_steps_exceeded"
    response = RunResponse(
        run_id=run_id,
        status=status,
        final_answer=result,
        trace=[TraceEvent(**e) for e in trace_capture.events],
        metrics=list(tracker.session_metrics),
        artifacts=artifacts,
    )
    RUN_STORE[run_id] = response

    # Send completion event via WebSocket
    await manager.send_event(run_id, {
        "timestamp": datetime.utcnow().isoformat(),
        "event": "RUN_COMPLETE",
        "data": {"run_id": run_id, "status": status},
    })

    return response


def _run_agent_sync(
    topic: str,
    provider: str,
    offline: bool,
    max_steps: int,
    output_dir: Path,
) -> str:
    """Synchronous agent execution (runs in thread pool)."""
    llm = build_llm_provider(provider, topic=topic)
    tools = build_research_tools(topic=topic, offline=offline, output_dir=output_dir)
    agent = ReActAgent(
        llm=llm,
        tools=tools,
        max_steps=max_steps,
        required_tools_before_final=["write_outputs"],
    )
    user_input = (
        f"Analyze research gaps for: {topic}. "
        "Use the available tools in this order unless a runtime observation says otherwise: "
        "search_papers, extract_evidence_cards, compare_and_find_gaps, write_outputs. "
        "Do not provide Final Answer until write_outputs returns artifact_paths."
    )
    return agent.run(user_input)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Retrieve results of a previous run."""
    if run_id not in RUN_STORE:
        return JSONResponse(status_code=404, content={"error": "Run not found"})
    return RUN_STORE[run_id]


@app.get("/api/runs")
async def list_runs():
    """List all runs."""
    return [
        {
            "run_id": run_id,
            "status": run.status,
            "final_answer": (run.final_answer or "")[:100],
            "trace_count": len(run.trace),
            "metrics_count": len(run.metrics),
        }
        for run_id, run in RUN_STORE.items()
    ]


# ---------------------------------------------------------------------------
# WebSocket for real-time trace streaming
# ---------------------------------------------------------------------------


@app.websocket("/ws/trace/{run_id}")
async def trace_websocket(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time trace event streaming."""
    await manager.connect(websocket, run_id)
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id)


# ---------------------------------------------------------------------------
# Serve frontend static files (after build)
# ---------------------------------------------------------------------------

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

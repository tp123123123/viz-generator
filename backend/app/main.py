from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import RUNS_DIR
from .jobs import accept_job, create_job, get_job, revise_job
from .llm import LLMNotConfigured, require_llm

app = FastAPI(title="Self-iterating Viz")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/runs", StaticFiles(directory=str(RUNS_DIR)), name="runs")


class ReviseBody(BaseModel):
    feedback: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs")
async def post_job(prompt: str = Form(...), file: UploadFile = File(...)):
    try:
        require_llm()
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = await file.read()
    try:
        state = create_job(prompt, data, file.filename or "data.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return state.to_public()


@app.get("/api/jobs/{job_id}")
def get_job_api(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="作业不存在")
    return state.to_public()


@app.post("/api/jobs/{job_id}/accept")
def post_accept(job_id: str):
    try:
        return accept_job(job_id).to_public()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/revise")
def post_revise(job_id: str, body: ReviseBody):
    try:
        require_llm()
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return revise_job(job_id, body.feedback).to_public()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

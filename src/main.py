from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from pathlib import Path
import uuid
import asyncio
import os
import httpx
import time
from datetime import datetime

from renderer import take_screenshot, generate_pdf

STORAGE_PATH = Path(os.getenv("STORAGE_PATH", "/data"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "2"))
RENDER_TIMEOUT = int(os.getenv("RENDER_TIMEOUT", "30"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Demo rate limiting: max 5 requests per minute per IP
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 5      # requests per window
rate_limits = {}        # ip -> [timestamps]

# Ensure storage exists
STORAGE_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SnapForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency semaphore
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# In-memory job store (replace with Redis for scale)
jobs = {}

class ScreenshotRequest(BaseModel):
    url: HttpUrl
    format: str = "png"          # png | jpeg | webp
    full_page: bool = True
    width: int = 1280
    height: int = 720
    webhook_url: str | None = None

class PDFRequest(BaseModel):
    url: HttpUrl
    width: int = 1280
    height: int = 720
    webhook_url: str | None = None

class JobStatus(BaseModel):
    id: str
    status: str          # pending | processing | done | error
    type: str            # screenshot | pdf
    url: str
    created_at: str
    completed_at: str | None = None
    result_url: str | None = None
    error: str | None = None

async def notify_webhook(job: dict):
    if not job.get("webhook_url"):
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {}
            if WEBHOOK_SECRET:
                headers["X-Webhook-Secret"] = WEBHOOK_SECRET
            await client.post(job["webhook_url"], json=job, headers=headers)
    except Exception:
        pass  # Fire-and-forget

async def process_screenshot(job_id: str, req: ScreenshotRequest):
    async with semaphore:
        job = jobs[job_id]
        job["status"] = "processing"
        
        ext = req.format if req.format in ("png", "jpeg", "webp") else "png"
        filename = f"{job_id}.{ext}"
        output_path = STORAGE_PATH / filename
        
        try:
            await asyncio.wait_for(
                take_screenshot(
                    url=str(req.url),
                    output_path=output_path,
                    format=ext,
                    full_page=req.full_page,
                    width=req.width,
                    height=req.height
                ),
                timeout=RENDER_TIMEOUT
            )
            
            job["status"] = "done"
            job["completed_at"] = datetime.utcnow().isoformat()
            job["result_url"] = f"/files/{filename}"
            
        except asyncio.TimeoutError:
            job["status"] = "error"
            job["error"] = "Render timeout"
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
        
        await notify_webhook(job)

async def process_pdf(job_id: str, req: PDFRequest):
    async with semaphore:
        job = jobs[job_id]
        job["status"] = "processing"
        
        filename = f"{job_id}.pdf"
        output_path = STORAGE_PATH / filename
        
        try:
            await asyncio.wait_for(
                generate_pdf(
                    url=str(req.url),
                    output_path=output_path,
                    width=req.width,
                    height=req.height
                ),
                timeout=RENDER_TIMEOUT
            )
            
            job["status"] = "done"
            job["completed_at"] = datetime.utcnow().isoformat()
            job["result_url"] = f"/files/{filename}"
            
        except asyncio.TimeoutError:
            job["status"] = "error"
            job["error"] = "Render timeout"
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
        
        await notify_webhook(job)

async def check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    if client_ip in rate_limits:
        rate_limits[client_ip] = [t for t in rate_limits[client_ip] if now - t < RATE_LIMIT_WINDOW]
        if len(rate_limits[client_ip]) >= RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Max 5 requests per minute. Join waitlist for full access: https://snapforge.io"
            )
    else:
        rate_limits[client_ip] = []
    
    rate_limits[client_ip].append(now)

@app.post("/screenshot", response_model=JobStatus)
async def create_screenshot(req: ScreenshotRequest, background_tasks: BackgroundTasks, request: Request):
    await check_rate_limit(request)
    
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    job = {
        "id": job_id,
        "status": "pending",
        "type": "screenshot",
        "url": str(req.url),
        "created_at": now,
        "completed_at": None,
        "result_url": None,
        "error": None,
        "webhook_url": req.webhook_url
    }
    jobs[job_id] = job
    
    background_tasks.add_task(process_screenshot, job_id, req)
    
    return JSONResponse(content=job, status_code=202)

@app.post("/pdf", response_model=JobStatus)
async def create_pdf(req: PDFRequest, background_tasks: BackgroundTasks, request: Request):
    await check_rate_limit(request)
    
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    job = {
        "id": job_id,
        "status": "pending",
        "type": "pdf",
        "url": str(req.url),
        "created_at": now,
        "completed_at": None,
        "result_url": None,
        "error": None,
        "webhook_url": req.webhook_url
    }
    jobs[job_id] = job
    
    background_tasks.add_task(process_pdf, job_id, req)
    
    return JSONResponse(content=job, status_code=202)

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/files/{filename}")
async def get_file(filename: str):
    file_path = STORAGE_PATH / filename
    # Security: prevent path traversal
    try:
        file_path.resolve().relative_to(STORAGE_PATH.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)

@app.get("/health")
async def health():
    return {"status": "ok", "queue_size": len(jobs)}
